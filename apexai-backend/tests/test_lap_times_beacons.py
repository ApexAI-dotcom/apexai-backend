"""
Les temps au tour doivent correspondre au chrono du boîtier.

Le temps d'un tour était déduit de max(time) − min(time) sur les points
échantillonnés. Après le sous-échantillonnage à 6 000 points, ni le premier ni
le dernier point d'un tour ne tombent sur la ligne : il manque un intervalle de
mesure à chaque extrémité. Sur une séance réelle, le meilleur tour sortait à
50,037 s contre 50,209 s au chrono AiM — un pilote qui compare avec son écran
voit l'écart tout de suite et cesse de croire le reste.

Quand les passages sur la ligne sont connus, le temps d'un tour complet est
exactement l'écart entre deux passages. Ces tests l'imposent, et vérifient
qu'en leur absence rien ne change.
"""
import math

import numpy as np
import pytest

from src.api.services import _beacon_lap_times, _parse_laps_sync


# Passages sur la ligne choisis pour donner des tours de durées distinctes,
# qu'aucun arrondi ne pourrait confondre.
BEACONS = [10.0, 60.5, 110.25, 161.0]
EXPECTED = {1: 50.5, 2: 49.75, 3: 50.75}


class _Attrs:
    """Minimum d'un DataFrame pour `_beacon_lap_times` : son `.attrs`."""

    def __init__(self, attrs):
        self.attrs = attrs


def _synthetic_motec_csv(beacons, duration_s=200.0, rate_hz=25.0):
    """
    CSV « MoTeC CSV File » synthétique : en-tête de 14 lignes puis un tour
    circulaire parcouru à vitesse constante. Aucune donnée de pilote réelle.
    """
    n = int(duration_s * rate_hz)
    t = np.arange(n) / rate_hz
    # Boucle fermée d'environ 50 m de rayon : de quoi faire travailler la
    # géométrie sans dépendre d'un tracé réel.
    ang = 2.0 * math.pi * (t / 50.0)
    lat = 45.0 + (50.0 / 111_320.0) * np.sin(ang)
    lon = 5.0 + (50.0 / (111_320.0 * math.cos(math.radians(45.0)))) * np.cos(ang)
    speed = np.full(n, 15.0)  # m/s, comme un export RaceStudio

    head = [
        '"Format","MoTeC CSV File","","","Workbook"',
        '"Venue","Circuit Test","","","Worksheet"',
        '"Vehicle","kart test","","","Vehicle Desc"',
        '"Driver","Pilote Test","","","Engine ID"',
        '"Device","AiM XRK"',
        '"Comment","","","","Session",""',
        '"Log Date","01/01/2026","","","Origin Time","0","s"',
        '"Log Time","12:00:00","","","Start Time","0","s"',
        f'"Sample Rate","{rate_hz:.0f}","Hz","","End Time","{duration_s:.3f}","s"',
        f'"Duration","{duration_s:.3f}","s","","Start Distance"',
        '"Range","entire outing","","","End Distance"',
        '"Beacon Markers","' + " ".join(f"{b:.3f}" for b in beacons) + '"',
        "",
        "",
        '"Time","GPS Latitude","GPS Longitude","GPS Speed"',
        '"s","deg","deg","m/s"',
    ]
    rows = [
        f"{t[i]:.3f},{lat[i]:.7f},{lon[i]:.7f},{speed[i]:.3f}" for i in range(n)
    ]
    return "\n".join(head + rows) + "\n"


def _write(tmp_path, beacons, name="session.csv"):
    path = tmp_path / name
    path.write_text(_synthetic_motec_csv(beacons), encoding="utf-8")
    return str(path)


# ── Le calcul lui-même ──────────────────────────────────────────────────────

def test_complete_lap_time_equals_beacon_interval():
    """Un tour complet dure exactement ce qui sépare deux passages."""
    got = _beacon_lap_times(_Attrs({"beacon_markers": BEACONS}))
    assert got == EXPECTED


def test_partial_laps_get_no_beacon_time():
    """Le tour 0 et le dernier sont tronqués : aucun chrono exact possible.

    Avec 4 passages, seuls les tours 1 à 3 sont encadrés. Le tour 0 commence
    avant le premier passage et le tour 4 finit après le dernier.
    """
    got = _beacon_lap_times(_Attrs({"beacon_markers": BEACONS}))
    assert 0 not in got
    assert len(BEACONS) not in got


def test_beacons_are_sorted_before_use():
    """Un fichier qui liste les passages en désordre donne le même résultat."""
    shuffled = [BEACONS[2], BEACONS[0], BEACONS[3], BEACONS[1]]
    assert _beacon_lap_times(_Attrs({"beacon_markers": shuffled})) == EXPECTED


@pytest.mark.parametrize("attrs", [
    {},
    {"beacon_markers": []},
    {"beacon_markers": [42.0]},          # un seul passage : aucun tour encadré
    {"beacon_markers": ["x", None]},     # valeurs illisibles
    {"beacon_markers": [10.0, 10.0]},    # deux passages confondus
])
def test_no_usable_beacons_changes_nothing(attrs):
    """Sans passages exploitables, le calcul historique doit reprendre la main."""
    assert _beacon_lap_times(_Attrs(attrs)) == {}


def test_non_finite_beacons_are_ignored():
    """Un NaN dans l'en-tête ne doit pas produire un chrono absurde."""
    got = _beacon_lap_times(_Attrs({"beacon_markers": [10.0, float("nan"), 60.5]}))
    assert got == {1: 50.5}


# ── Bout en bout, à travers la route /parse-laps ────────────────────────────

def test_parse_laps_reports_exact_times(tmp_path):
    """Les chronos renvoyés au pilote sont ceux des passages, au millième."""
    laps = _parse_laps_sync(_write(tmp_path, BEACONS), BEACONS)
    by_num = {l["lap_number"]: l["lap_time_seconds"] for l in laps}
    for lap, expected in EXPECTED.items():
        assert lap in by_num, f"tour {lap} absent"
        assert abs(by_num[lap] - expected) < 1e-3, (
            f"tour {lap} : {by_num[lap]} s au lieu de {expected} s"
        )


def test_partial_laps_stay_flagged(tmp_path):
    """Les tours tronqués restent signalés comme non représentatifs.

    Leur durée n'a pas de sens pour comparer : les exclure de l'affichage est
    ce qui empêche un tour de rentrée de passer pour le meilleur tour.
    """
    laps = _parse_laps_sync(_write(tmp_path, BEACONS), BEACONS)
    by_num = {l["lap_number"]: l for l in laps}
    assert by_num[0]["is_outlier"] is True
    last = max(by_num)
    assert by_num[last]["is_outlier"] is True


def test_without_beacons_behaviour_is_unchanged(tmp_path):
    """Sans passages, on retombe sur la mesure des points échantillonnés.

    Le chrono y est forcément un peu court — c'est le comportement historique,
    et le seul possible quand la ligne n'est pas connue.
    """
    path = tmp_path / "sans_beacons.csv"
    content = _synthetic_motec_csv(BEACONS).replace(
        '"Beacon Markers","' + " ".join(f"{b:.3f}" for b in BEACONS) + '"',
        '"Beacon Markers",""',
    )
    path.write_text(content, encoding="utf-8")

    laps = _parse_laps_sync(str(path), [])
    assert laps, "aucun tour détecté sans beacons"
    # Aucun tour ne doit tomber pile sur un écart entre passages : ce serait le
    # signe que les beacons ont été utilisés alors qu'ils étaient absents.
    times = [l["lap_time_seconds"] for l in laps]
    for expected in EXPECTED.values():
        assert not any(abs(t - expected) < 1e-9 for t in times), (
            f"{expected} s retrouvé sans beacons : la bascule fuit"
        )
