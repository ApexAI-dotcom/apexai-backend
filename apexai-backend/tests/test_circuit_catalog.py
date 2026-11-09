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


def test_corner_count_ignores_flat_out_kinks():
    """Citykart Sautron : 15 inflexions sur le tracé, 10 vrais virages."""
    from src.core import circuit_catalog as cc
    c = next(x for x in cc.all_circuits() if x["name"] == "Citykart")
    s = cc.summary(c)
    assert s["corners_count"] == 10
    assert s["kinks_count"] == 5
    assert s["hairpins_count"] + s["medium_count"] + s["fast_corners_count"] == s["corners_count"]


def test_alfano_tracks_are_in_the_catalog():
    """Séances Alfano : Soucy (fiche FFSA recalée sur la piste), Rustavi, Vihti, Martensville."""
    assert cc.match_name("SOUCY")["slug"] == "sens-espace-karting-soucy"
    assert cc.match_name("RUSTAVI INTERNATIONAL MOTORPARK")["country"] == "GE"
    assert cc.match_name("VIHTI KARTING")["country"] == "FI"
    for slug in ("sens-espace-karting-soucy", "rustavi-international-motorpark-karting", "vihti-karting", "martensville-speedway-karting"):
        c = cc.get(slug)
        m = cc.match_points([(p[0] + 0.00001, p[1]) for p in c["centerline"]] * 3)
        assert m["slug"] == slug and m["confident"], slug
        # Tracé mesuré au GPS d'une séance : pas attribué à OpenStreetMap.
        assert "OpenStreetMap" not in cc.detail(c)["attribution"]
    osm = next(c for c in cc.all_circuits() if "OSM" in (c.get("source") or "") and c.get("centerline"))
    assert "OpenStreetMap" in cc.detail(osm)["attribution"]
