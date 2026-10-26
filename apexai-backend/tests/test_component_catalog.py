"""Base des composants : fusion avec kart_components, recherche, correspondance."""

from src.core import component_catalog as cc

DB = [
    {"id": "rotax-dd2", "category": "engine", "brand": "Rotax", "name": "Max DD2", "subcategory": "125 DD2",
     "default_life": 15, "life_unit": "hours", "specs": {"weight_kg": 21}, "active": True},
    {"id": "vega-rouge-sl4", "category": "tire", "brand": "Vega", "name": "Rouge SL4", "subcategory": "Medium",
     "default_life": 200, "life_unit": "laps", "specs": {"cold_pressure_bar": {"dry": [0.6, 0.8]}}, "active": True},
]


def test_merge_keeps_db_names_and_adds_sourced_data():
    items = {c["id"]: c for c in cc.merge(DB)}
    dd2 = items["rotax-dd2"]
    assert dd2["name"] == "Max DD2" and dd2["in_db"] is True
    assert dd2["default_life"] == 25  # retour pilotes : révision vers 25 h
    assert dd2["specs"]["weight_kg"] == 21
    assert any(m["kind"] == "retour pilotes" for m in dd2["maintenance"])
    sl4 = items["vega-rouge-sl4"]
    assert sl4["specs"]["cold_pressure_bar"] and sl4["specs"]["price_eur_set"] == 205
    # Fiches absentes de la table : servies, mais marquées hors base
    assert items["vega-xh4"]["in_db"] is False
    assert items["tm-kz-r3"]["category"] == "engine"
    assert len(items) > 200


def test_search_and_match():
    items = cc.merge(DB)
    names = [f"{h['brand']} {h['name']}" for h in cc.search(items, "xh4")]
    assert any("XH4" in n for n in names)
    assert all(h["category"] == "tire" for h in cc.search(items, "vega", "tire"))
    assert cc.match(items, "Rotax Max DD2", "engine")["id"] == "rotax-dd2"
    assert cc.match(items, "Vega Rouge SL4", "tire")["id"] == "vega-rouge-sl4"
    assert cc.match(items, "LeCont LOH", "tire")["id"] == "lecont-loh"
    assert cc.match(items, "Bidule inconnu", "tire") is None


def test_compact_has_no_internal_keys():
    item = cc.compact(cc.merge(DB)[0])
    assert "_search" not in item and "maintenance" not in item
