"""
Import natif des fichiers AiM RaceStudio (.xrk / .xrz).

Le .xrk est converti vers le CSV « MoTeC CSV File » que le pipeline lit déjà.
Ces tests utilisent une session SYNTHÉTIQUE (aucune donnée de pilote dans le
dépôt) injectée à la place du parseur libxrk, plus un test sur un vrai fichier
quand XRK_SAMPLE pointe vers un .xrk local :

    XRK_SAMPLE=/chemin/session.xrk python -m pytest tests/test_xrk_import.py -v
"""
import asyncio
import os
import sys

import numpy as np
import pytest

pa = pytest.importorskip("pyarrow")
libxrk = pytest.importorskip("libxrk")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from libxrk import LogFile  # noqa: E402

from src.core.data_loader import robust_load_telemetry  # noqa: E402
from src.core.xrk_loader import XrkImportError, is_xrk_filename, normalize_upload, xrk_to_motec_csv  # noqa: E402


def _channel(name, timecodes_ms, values, units=""):
    schema = pa.schema([
        pa.field("timecodes", pa.int64()),
        pa.field(name, pa.float64(), metadata={b"units": units.encode(), b"interpolate": b"True"}),
    ])
    return pa.table(
        {"timecodes": pa.array(timecodes_ms, pa.int64()), name: pa.array(values, pa.float64())},
        schema=schema,
    )


def _synthetic_log(with_gps=True):
    """Session de 6 tours sur un ovale de ~40 s : 1 tour de sortie, 4 complets, 1 de rentrée."""
    lap_ms = 40_000
    out_ms = 15_000
    total_ms = out_ms + 4 * lap_ms + 25_000
    t25 = np.arange(0, total_ms, 40, dtype=np.int64)  # 25 Hz
    t20 = np.arange(0, total_ms, 50, dtype=np.int64)  # 20 Hz
    phase = 2 * np.pi * (t25 - out_ms) / lap_ms
    lat = 47.5 + 0.0012 * np.sin(phase)
    lon = -1.8 + 0.0020 * np.cos(phase)
    speed = 20.0 + 3.0 * np.sin(2 * phase)

    channels = {}
    if with_gps:
        channels["GPS Latitude"] = _channel("GPS Latitude", t25, lat, "deg")
        channels["GPS Longitude"] = _channel("GPS Longitude", t25, lon, "deg")
        channels["GPS Speed"] = _channel("GPS Speed", t25, speed, "m/s")
    channels["RPM"] = _channel("RPM", t20, 9000 + 2000 * np.sin(2 * np.pi * t20 / 7000.0), "rpm")
    channels["Water Temp"] = _channel("Water Temp", t20, 50 + t20 / 60000.0, "C")
    channels["Temp TC 1"] = _channel("Temp TC 1", t20, np.full(t20.size, np.inf), "C")  # capteur débranché
    channels["Jackshaft"] = _channel("Jackshaft", t20, np.zeros(t20.size), "rpm")  # capteur absent
    channels["TimePulseTick"] = _channel("TimePulseTick", t20, np.arange(t20.size, dtype=float), "ms")
    channels["GPS_LateralAcc"] = _channel("GPS_LateralAcc", t25, 1.2 * np.sin(phase), "g")

    ends = [out_ms + i * lap_ms for i in range(0, 5)]
    laps = pa.table({
        "num": pa.array([0, 1, 2, 3, 4, 5], pa.int32()),
        "start_time": pa.array([0] + ends[:4] + [ends[4]], pa.int64()),
        "end_time": pa.array(ends + [total_ms], pa.int64()),
        "lap_type": pa.array(["out", "full", "full", "full", "full", "in"]),
    })
    meta = {"Driver": 'Pilote "Test", Jr', "Vehicle": "kart", "Venue": "Circuit, de Test",
            "Log Date": "10/18/2026", "Log Time": "10:00:00"}
    return LogFile(channels=channels, laps=laps, metadata=meta, file_name="synthetic.xrk"), ends


@pytest.fixture
def fake_xrk(monkeypatch):
    log, ends = _synthetic_log()
    monkeypatch.setattr(libxrk, "aim_xrk", lambda *_a, **_k: log)
    return log, ends


def test_is_xrk_filename():
    assert is_xrk_filename("session.XRK") and is_xrk_filename("a.xrz")
    assert not is_xrk_filename("session.csv") and not is_xrk_filename(None) and not is_xrk_filename("")


def test_conversion_header_matches_racestudio_csv(fake_xrk):
    _, ends = fake_xrk
    lines = xrk_to_motec_csv(b"ignored").decode("utf-8").split("\n")

    assert lines[0].startswith('"Format","MoTeC CSV File"')
    assert lines[4] == '"Device","AiM XRK"'
    # 14 lignes d'en-tête (skiprows=14 dans data_loader), puis noms de colonnes, puis unités
    assert lines[12] == "" and lines[13] == ""
    assert lines[14].startswith('"Time","GPS Latitude","GPS Longitude","GPS Speed"')
    assert lines[15].startswith('"s","deg","deg","m/s"')

    # Virgules et guillemets retirés des valeurs d'en-tête (le parseur de services.py découpe sur ',')
    assert lines[1].split(",")[1] == '"Circuit  de Test"'
    assert "Pilote  Test  Jr" in lines[3]

    # Beacon Markers = passages sur la ligne : début des tours 1..5 (le dernier = fin du tour 4)
    beacon_line = next(l for l in lines[:14] if l.startswith('"Beacon Markers"'))
    markers = [float(x) for x in beacon_line.replace('"', "").split(",")[1].split()]
    assert markers == [t / 1000.0 for t in ends]


def test_unusable_channels_are_dropped_and_gps_renamed(fake_xrk):
    header = xrk_to_motec_csv(b"ignored").decode("utf-8").split("\n")[14]
    assert '"Temp TC 1"' not in header          # valeurs infinies : capteur débranché
    assert '"Jackshaft"' not in header          # constant : capteur absent
    assert '"TimePulseTick"' not in header      # canal interne du logger
    assert '"RPM"' in header and '"Water Temp"' in header
    assert '"GPS LatAcc"' in header and "GPS_LateralAcc" not in header


def test_converted_csv_loads_in_existing_pipeline(fake_xrk, tmp_path):
    path = tmp_path / "converted.csv"
    path.write_bytes(xrk_to_motec_csv(b"ignored"))
    result = robust_load_telemetry(str(path))
    assert result["success"], result.get("error")
    df = result["data"]
    assert {"latitude", "longitude", "speed", "time", "rpm", "water temp"} <= set(df.columns)
    assert 47.49 < df["latitude"].dropna().iloc[5] < 47.51
    assert df["speed"].dropna().max() > 50  # m/s converti en km/h (~23 m/s -> ~83 km/h)
    assert result["diagnostics"]["device"] == "AiM (fichier .xrk natif)"


def test_garbage_bytes_raise_readable_error():
    with pytest.raises(XrkImportError, match="illisible"):
        xrk_to_motec_csv(b"ceci n'est pas un fichier xrk" * 50)


def test_xrk_without_gps_is_rejected(monkeypatch):
    log, _ = _synthetic_log(with_gps=False)
    monkeypatch.setattr(libxrk, "aim_xrk", lambda *_a, **_k: log)
    with pytest.raises(XrkImportError, match="GPS"):
        xrk_to_motec_csv(b"ignored")


def test_normalize_upload_converts_xrk_and_passes_csv_through(fake_xrk):
    content, name = asyncio.run(normalize_upload(b"binaire", "Session Auxence.XRK"))
    assert name == "Session Auxence.csv" and content.startswith(b'"Format","MoTeC CSV File"')

    raw = b'"Time","GPS Latitude"\n'
    assert asyncio.run(normalize_upload(raw, "export.csv")) == (raw, "export.csv")


def test_upload_validation_accepts_xrk_but_not_other_extensions():
    from src.api.utils import validate_csv_file

    class _Upload:
        def __init__(self, filename, content):
            self.filename, self._content = filename, content

        async def read(self):
            return self._content

        async def seek(self, _pos):
            return 0

    blob = b"<hCNF\x00" + b"\x00" * 4000  # binaire : ni décodage UTF-8 ni heuristique GPS texte
    assert asyncio.run(validate_csv_file(_Upload("session.xrk", blob))) is None
    assert asyncio.run(validate_csv_file(_Upload("session.xrz", blob))) is None
    assert "Extension invalide" in asyncio.run(validate_csv_file(_Upload("session.exe", blob)))


@pytest.mark.skipif(not os.environ.get("XRK_SAMPLE"), reason="XRK_SAMPLE non défini (fichier réel local)")
def test_real_xrk_file_runs_through_pipeline(tmp_path):
    with open(os.environ["XRK_SAMPLE"], "rb") as f:
        csv_bytes = xrk_to_motec_csv(f.read())
    path = tmp_path / "real.csv"
    path.write_bytes(csv_bytes)
    result = robust_load_telemetry(str(path))
    assert result["success"], result.get("error")
    assert result["diagnostics"]["channels"]["required_missing"] == []
