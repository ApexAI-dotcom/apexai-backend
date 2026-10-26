from src.core import circuit_catalog as cc


def test_catalog_loads_and_searches():
    assert len(cc.all_circuits()) > 300
    hits = cc.search("solokart")
    assert hits and hits[0]["city"] == "Plesse"
    assert all(h["department_code"] == "44" for h in cc.search("", dept="44"))


def test_names_written_by_devices_match_the_right_circuit():
    assert cc.match_name("SoloKart")["city"] == "Plesse"
    assert cc.match_name("CarpentrasK")["city"] == "Carpentras"
    assert cc.match_name("LebretK") is None
    assert cc.match_name("Circuit Importé") is None


def test_session_points_match_the_track():
    c = cc.get("solokart-plesse")
    line = c["centerline"]
    m = cc.match_points([(p[0] + 0.00001, p[1]) for p in line] * 3)
    assert m["slug"] == "solokart-plesse" and m["confident"]
    assert cc.match_points([(48.0, 2.0)] * 50) is None


def test_rotation_is_read_from_the_trace():
    assert cc.rotation_of(cc.get("solokart-plesse")["centerline"]) in ("horaire", "anti-horaire")
