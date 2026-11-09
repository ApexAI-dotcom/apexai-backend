"""Import Alfano (ADA) : export « Excel » et zip brut donnent la même séance."""

import asyncio
import io
import math
import zipfile

import numpy as np
import pytest

from src.core.alfano_loader import (
    AlfanoImportError,
    LEAD_S,
    alfano_excel_to_motec_csv,
    alfano_zip_to_motec_csv,
    is_alfano_excel,
    is_alfano_zip,
)
from src.core.session_header import read_session_header
from src.core.xrk_loader import XrkImportError, normalize_upload

LAT0, LON0 = 41.566096, 44.949769
LAPS_S = [30.0, 29.5, 29.8]


def _lap_points(n, lap):
    """Un ovale de ~400 m : positions, vitesses (≈ 48 km/h), G et cap."""
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    r = 64.0
    lat = LAT0 + (r * np.sin(a)) / 111_000
    lon = LON0 + (r * (1 - np.cos(a))) / (111_000 * math.cos(math.radians(LAT0)))
    speed = 48 + 6 * np.cos(2 * a) + lap * 0.1
    head = (np.degrees(a) + 90) % 360
    return lat, lon, speed, head


def _excel(t1_max=0.0, t2_max=0.0, thousands=True):
    cols = "Lap;Time Lap;Strip;Time Strip;Absolute Time;Time;RPM;Speed GPS;T1;T2;Gf. X;Gf. Y;Orientation;Speed rear;Lat.;Lon.;Altitude;UTC time : 170245.00"
    lines = [cols]
    for k, dur in enumerate(LAPS_S):
        n = int(dur * 10)
        lat, lon, sp, hd = _lap_points(n, k)
        for i in range(n):
            rpm = 12000 + i
            rpm_s = f"{rpm // 1000},{rpm % 1000:03d}" if thousands else str(rpm)
            first = i == 0
            lines.append(";".join([
                str(k + 1) if first else "", f"{dur}" if first else "", "1" if first else "", f"{dur}" if first else "",
                "0", f"{i / 10:.1f}", rpm_s, f"{sp[i]:.1f}",
                f"{t1_max * i / n:.1f}", f"{t2_max * i / n:.1f}",
                "-0.9", "0.5", str(int(hd[i] * 100)), "0", f"{lat[i]:.7f}", f"{lon[i]:.7f}", "406", "",
            ]))
    return ("\n".join(lines) + "\n").encode()


def _zip(extra_partial=True, egt=0):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        stem = "ALFANO6_LAP_SN8448_301025_17H02_Nikoloz__P__RUSTAVI__25_10_25_3_2950"
        laps = list(LAPS_S) + ([8.0] if extra_partial else [])
        for k, dur in enumerate(laps):
            n = int(dur * 10)
            lat, lon, sp, hd = _lap_points(n, k)
            rows = ["Partiel,RPM,Speed GPS,T1,T2,Gf. X,Gf. Y,Orientation,Speed rear,Lat.,Lon.,Altitude"]
            for i in range(n):
                rows.append(",".join(str(v) for v in [
                    1, 12000 + i, int(sp[i] * 10), 350, int(egt * 10 * i / n), 910, 1050, int(hd[i] * 100), 0,
                    f"{lat[i] * 1e6:.2f}", f"{lon[i] * 1e6:.2f}", 4060,
                ]))
            z.writestr(f"LAP_{k + 1}_{stem}.csv", "\n".join(rows) + "\n")
        summary = [
            "30-10-2025,17:02,03,8448,*P* RUSTAVI  25/10/25,Nikoloz,01,',01,'',20,ALFANO 6,END",
            "lap,time lap,time partiel 1,Min RPM,Max RPM,max EGT",
        ] + [f"{k + 1},{int(d * 1000)},{int(d * 1000)},7000,13600,{egt * 10 if k == 0 else 0}" for k, d in enumerate(LAPS_S)]
        z.writestr(f"{stem[12:]}.csv".replace("LAP_", ""), "\n".join(summary) + "\n")
        z.writestr("projection_orthogonale2023.csv",
                   f"Latitude reference;{LAT0};0\nlongitude reference;{LON0};0\norientation reference;129;0\n")
    return buf.getvalue()


def _channels(csv_bytes):
    lines = csv_bytes.decode().splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith('"Time"'))
    return [c.strip('"') for c in lines[i].split(",")], lines


def _write(tmp_path, b, name="s.csv"):
    p = tmp_path / name
    p.write_bytes(b)
    return str(p)


def test_detection():
    assert is_alfano_excel(_excel())
    assert is_alfano_zip(_zip())
    assert not is_alfano_excel(b'"Format","AiM CSV File"\n')
    assert not is_alfano_zip(b"PK\x03\x04garbage")


def test_excel_laps_and_channels(tmp_path):
    out = alfano_excel_to_motec_csv(_excel(), "Excel_SN894_090624_11H58_RENAUD__P__SOUCY_13_5105.csv")
    h = read_session_header(_write(tmp_path, out))
    # Le tour 1 de l'Alfano est un tour chronométré : son début doit être vu.
    assert h["beacon_markers"][0] == pytest.approx(LEAD_S)
    laps = np.diff(h["beacon_markers"])
    assert laps == pytest.approx(LAPS_S, abs=1e-3)
    assert h["circuit_name"] == "SOUCY"
    assert h["driver"] == "Renaud"
    cols, lines = _channels(out)
    assert {"GPS Latitude", "GPS Longitude", "GPS Speed", "RPM", "GPS Heading", "GPS LatAcc", "GPS LonAcc"} <= set(cols)
    start = next(k for k, l in enumerate(lines) if l.startswith('"Time"'))
    row = lines[start + 4].replace('"', "").split(",")
    rec = dict(zip(cols, row))
    assert float(rec["RPM"]) == 12000          # « 12,000 » = milliers, pas 12,0
    assert 0 <= float(rec["GPS Heading"]) < 360  # centièmes de degré ramenés en degrés
    assert float(rec["GPS LonAcc"]) == pytest.approx(-0.5)  # Gf. Y > 0 au freinage → LonAcc < 0


def test_t1_t2_never_become_water_temp():
    cols, _ = _channels(alfano_excel_to_motec_csv(_excel(t1_max=60.0, t2_max=600.0)))
    assert "Alfano T1" in cols          # 60 °C : capteur inconnu, laissé neutre
    assert "Exhaust Temp" in cols       # 600 °C : forcément l'échappement
    assert not any("water" in c.lower() or "eau" in c.lower() for c in cols)
    cols0, _ = _channels(alfano_excel_to_motec_csv(_excel()))
    assert not any(c.startswith("Alfano T") for c in cols0)  # voies vides : absentes


def test_zip_matches_excel_and_drops_partial_lap(tmp_path):
    z = alfano_zip_to_motec_csv(_zip(extra_partial=True, egt=540))
    hz = read_session_header(_write(tmp_path, z, "z.csv"))
    hx = read_session_header(_write(tmp_path, alfano_excel_to_motec_csv(_excel()), "x.csv"))
    assert hz["beacon_markers"] == pytest.approx(hx["beacon_markers"], abs=1e-3)
    assert hz["circuit_name"] == "RUSTAVI"
    assert hz["driver"] == "Nikoloz"
    cols, lines = _channels(z)
    assert "Exhaust Temp" in cols  # max proche du « max EGT » du résumé
    assert "Alfano T1" in cols     # 35 °C constant : neutre
    # Le tour interrompu (sans chrono dans le résumé) n'est pas importé.
    last_t = float(lines[-1].split(",")[0].strip('"'))
    assert last_t <= hz["beacon_markers"][-1] + 0.01
    head = "\n".join(lines[:8])
    assert f"Ligne de départ Alfano {LAT0:.6f} {LON0:.6f} 129.0" in head


def test_zip_without_gps_is_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("LAP_1_X.csv", "Partiel,RPM,Speed GPS,Lat.,Lon.\n" + "\n".join("1,9000,500,0,0" for _ in range(50)))
    with pytest.raises(AlfanoImportError):
        alfano_zip_to_motec_csv(buf.getvalue())


def test_normalize_upload_routes_alfano():
    csv_bytes, name = asyncio.run(normalize_upload(_zip(), "seance.zip"))
    assert name == "seance.csv" and csv_bytes.startswith(b'"Format","MoTeC CSV File"')
    csv_bytes, name = asyncio.run(normalize_upload(_excel(), "Excel_SN1.csv"))
    assert csv_bytes.startswith(b'"Format","MoTeC CSV File"')
    with pytest.raises(XrkImportError):
        asyncio.run(normalize_upload(b"PK\x03\x04" + b"0" * 2000, "photos.zip"))
