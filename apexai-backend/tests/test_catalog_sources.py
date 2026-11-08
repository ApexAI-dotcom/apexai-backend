"""Base des composants : l'app ne sert que des données du constructeur, sourcées."""

from src.core import component_catalog as compcat


def test_maintenance_is_manufacturer_only_with_a_due_date():
    for it in compcat.catalog_items().values():
        for m in it.get("maintenance") or []:
            assert m["kind"] == "constructeur", (it["id"], m)
            assert str(m.get("interval") or "").strip(), (it["id"], m)


def test_no_driver_hearsay_is_served():
    for it in compcat.catalog_items().values():
        assert all(s["type"] not in ("retour pilotes", "base ApexAI") for s in it.get("sources") or []), it["id"]
        assert "pilote" not in (it.get("notes") or "").lower(), it["id"]


def test_life_is_backed_by_a_manufacturer_document():
    for it in compcat.catalog_items().values():
        if it.get("default_life") is not None:
            ref = it.get("life_ref")
            assert ref and ref.get("url"), it["id"]


def test_dd2_has_no_invented_interval():
    dd2 = compcat.catalog_items()["rotax-dd2"]
    assert dd2["default_life"] is None
    assert {m["element"] for m in dd2["maintenance"]} == {"Huile de boîte", "Filtre à air"}
