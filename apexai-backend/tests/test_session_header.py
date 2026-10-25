"""
Lecture de l'en-tête des exports RaceStudio : les deux formats CSV.

RaceStudio exporte en « MoTeC CSV File » ou en « AiM CSV File », et les deux
n'écrivent pas les passages sur la ligne de la même façon. L'ancien lecteur ne
connaissait que le premier : sur un export AiM CSV il ne retenait qu'un seul
passage, et toute la séance suivante devenait un « tour » de plusieurs minutes,
rejeté avec « le meilleur temps calculé (391 s) est incohérent ». Tous les
exports AiM CSV échouaient.

Données entièrement synthétiques : aucun fichier de pilote dans le dépôt.
"""
import pytest

from src.core.session_header import read_beacon_markers, read_session_header

CROSSINGS = [48.911, 93.082, 136.086, 178.629]
DURATION = 219.5


def _aim_csv(tmp_path, markers, duration=DURATION, session="CircuitTest", name="aim.csv"):
    """Export « AiM CSV File » : un champ par marqueur, fin de séance incluse."""
    seg = []
    prev = 0.0
    for m in markers:
        d = m - prev
        seg.append(f'"{int(d // 60)}:{d % 60:06.3f}"')
        prev = m
    lines = [
        '"Format","AiM CSV File"',
        f'"Session","{session}"',
        '"Vehicle","KART"',
        '"Racer","PILOTE"',
        '"Championship",""',
        '"Comment",""',
        '"Date","Sunday, January 4, 2026"',
        '"Time","9:00 AM"',
        '"Sample Rate","20"',
        f'"Duration","{duration}"',
        '"Segment","Session"',
        '"Beacon Markers",' + ",".join(f'"{m}"' for m in markers),
        '"Segment Times",' + ",".join(seg),
        "",
        '"Time","GPS Speed","GPS Latitude","GPS Longitude"',
        '"s","km/h","deg","deg"',
        "0.000,0.0,45.0,5.0",
    ]
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def _motec_csv(tmp_path, markers, duration=DURATION, venue="Circuit Test", name="motec.csv"):
    """Export « MoTeC CSV File » : tous les marqueurs dans un seul champ."""
    lines = [
        '"Format","MoTeC CSV File","","","Workbook"',
        f'"Venue","{venue}","","","Worksheet"',
        '"Vehicle","","","","Vehicle Desc"',
        '"Driver","PILOTE","","","Engine ID"',
        '"Device","AiM Ported"',
        '"Comment","","","","Session",""',
        '"Log Date","01/04/2026","","","Origin Time","0","s"',
        '"Log Time","09:00:00","","","Start Time","0","s"',
        '"Sample Rate","20","Hz","","End Time","219.5","s"',
        f'"Duration","{duration}","s","","Start Distance"',
        '"Range","entire outing","","","End Distance"',
        '"Beacon Markers","' + " ".join(str(m) for m in markers) + '"',
        "",
        "",
        '"Time","GPS Speed","GPS Latitude","GPS Longitude"',
        '"s","m/s","deg","deg"',
        "0.000,0.0,45.0,5.0",
    ]
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


# ── Le défaut corrigé ───────────────────────────────────────────────────────

def test_aim_csv_reads_every_crossing(tmp_path):
    """Le cas qui échouait : tous les passages, pas seulement le premier."""
    path = _aim_csv(tmp_path, CROSSINGS + [DURATION])
    assert read_beacon_markers(path) == CROSSINGS


def test_aim_csv_session_end_is_not_a_crossing(tmp_path):
    """La fin de séance, écrite comme dernier marqueur, n'est pas un passage.

    La garder ferait du dernier tronçon — un tour de rentrée partiel — un tour
    complet chronométré au millième, et créerait un tour vide après lui.
    """
    path = _aim_csv(tmp_path, CROSSINGS + [DURATION])
    assert DURATION not in read_beacon_markers(path)


def test_aim_csv_without_session_end_keeps_all(tmp_path):
    """Si le dernier marqueur n'est pas la fin de séance, il reste un passage."""
    path = _aim_csv(tmp_path, CROSSINGS, duration=DURATION)
    assert read_beacon_markers(path) == CROSSINGS


def test_aim_csv_gaps_match_device_segment_times(tmp_path):
    """L'écart entre deux passages doit valoir le chrono du boîtier.

    C'est la vérification qui compte : si elle tient, les tours découpés par
    ApexAI sont exactement ceux du boîtier.
    """
    path = _aim_csv(tmp_path, CROSSINGS + [DURATION])
    h = read_session_header(path)
    b = h["beacon_markers"]
    gaps = [round(b[k] - b[k - 1], 3) for k in range(1, len(b))]
    device = [round(t, 3) for t in h["segment_times_s"][1:len(b)]]
    assert gaps == device


def test_aim_csv_circuit_comes_from_session(tmp_path):
    """L'AiM CSV écrit le circuit sous « Session » : il était perdu."""
    path = _aim_csv(tmp_path, CROSSINGS + [DURATION], session="CarpentrasK")
    assert read_session_header(path)["circuit_name"] == "CarpentrasK"


# ── Aucune régression sur le format qui marchait ────────────────────────────

def test_motec_unchanged(tmp_path):
    """Le MoTeC doit donner exactement ce qu'il donnait avant."""
    path = _motec_csv(tmp_path, CROSSINGS)
    h = read_session_header(path)
    assert h["beacon_markers"] == CROSSINGS
    assert h["format"] == "MoTeC CSV File"
    assert h["circuit_name"] == "Circuit Test"
    assert h["duration_s"] == pytest.approx(DURATION)


def test_motec_session_word_is_not_taken_for_circuit(tmp_path):
    """En MoTeC, « Session » apparaît en milieu de ligne : jamais un circuit."""
    path = _motec_csv(tmp_path, CROSSINGS, venue="")
    assert read_session_header(path)["circuit_name"] is None


def test_markers_are_returned_sorted(tmp_path):
    """Un export qui liste les passages en désordre donne la même découpe."""
    path = _aim_csv(tmp_path, [CROSSINGS[2], CROSSINGS[0], CROSSINGS[3], CROSSINGS[1]])
    assert read_beacon_markers(path) == CROSSINGS


# ── Robustesse ──────────────────────────────────────────────────────────────

def test_missing_file_never_raises(tmp_path):
    """Un en-tête illisible ne doit pas bloquer l'analyse : repli sur le GPS."""
    h = read_session_header(str(tmp_path / "absent.csv"))
    assert h["beacon_markers"] == [] and h["format"] is None


def test_file_without_header_returns_empty(tmp_path):
    """Un CSV brut, sans métadonnées, laisse la détection GPS travailler."""
    p = tmp_path / "brut.csv"
    p.write_text("Time,Speed,Lat,Lon\n0,0,45,5\n1,10,45.0001,5\n", encoding="utf-8")
    assert read_beacon_markers(str(p)) == []


def test_data_loader_delegates_to_the_same_reader(tmp_path):
    """data_loader et l'API lisent la même source : une seule réponse possible."""
    from src.core.data_loader import _extract_beacon_markers

    path = _aim_csv(tmp_path, CROSSINGS + [DURATION])
    assert _extract_beacon_markers(path) == read_beacon_markers(path) == CROSSINGS
