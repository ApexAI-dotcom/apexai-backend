#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Base des composants de karting (saison 2026-2027, lecture seule).

Le fichier src/data/component_catalog.json est produit par
scripts/composants/catalog.py du dépôt front : manuels constructeurs,
règlements 2026, listes d'homologation CIK-FIA et retours de pilotes, chaque
fiche avec ses sources. On le fusionne avec la table kart_components :

- une ligne de la table garde son identifiant et son nom (profils et trains
  de pneus y font référence) et reçoit les compléments de la base (usages,
  homologation, sources, entretien, durée avant révision sourcée) ;
- une fiche absente de la table est servie telle quelle (in_db = False) :
  elle ne peut pas servir de clé étrangère, d'où le repli en saisie libre
  pour les trains de pneus.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DATA = Path(__file__).resolve().parents[1] / "data" / "component_catalog.json"

# Champs renvoyés dans les listes (les sources et l'entretien détaillés restent dans la fiche)
LIST_KEYS = (
    "id", "category", "category_label", "brand", "name", "subcategory", "specs", "default_life", "life_unit",
    "active", "in_db", "uses", "aliases", "homologation", "source_types", "season", "has_maintenance",
)


def _norm(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": None, "categories": {}, "components": []}


def version() -> Optional[str]:
    return _load().get("version")


def categories() -> Dict[str, str]:
    return dict(_load().get("categories") or {})


def all_categories() -> set:
    return set(categories()) | {"engine", "tire", "brake", "chassis", "carburetor", "axle"}


def catalog_items() -> Dict[str, Dict[str, Any]]:
    return {c["id"]: c for c in _load().get("components", [])}


def merge(db_rows: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Table kart_components + base sourcée, une fiche par identifiant."""
    cat = catalog_items()
    labels = categories()
    out: Dict[str, Dict[str, Any]] = {}
    for row in db_rows or []:
        item = dict(row)
        extra = cat.get(item.get("id")) or {}
        item["specs"] = {**(item.get("specs") or {}), **(extra.get("specs") or {})}
        if extra.get("default_life") is not None:
            item["default_life"], item["life_unit"] = extra["default_life"], extra.get("life_unit")
        item["subcategory"] = item.get("subcategory") or extra.get("subcategory")
        for k in ("uses", "aliases", "homologation", "notes", "maintenance", "sources", "source_types", "season"):
            item[k] = extra.get(k) if extra.get(k) else ([] if k in ("uses", "aliases", "maintenance", "sources", "source_types") else None)
        item["in_db"] = True
        out[item["id"]] = item
    for cid, extra in cat.items():
        if cid in out or not extra.get("name") or not extra.get("brand"):
            continue
        item = {k: v for k, v in extra.items() if k not in ("in_db_seed",)}
        item["active"] = True
        item["in_db"] = False
        out[cid] = item
    items = list(out.values())
    for it in items:
        it["category_label"] = labels.get(it.get("category"), it.get("category"))
        it["has_maintenance"] = bool(it.get("maintenance"))
        it["_search"] = _norm(" ".join(
            [str(it.get(k) or "") for k in ("brand", "name", "subcategory", "homologation", "category_label")]
            + list(it.get("aliases") or []) + list(it.get("uses") or [])
        ))
    order = list(labels) or []
    items.sort(key=lambda c: (order.index(c["category"]) if c.get("category") in order else 99,
                              (c.get("brand") or "").lower(), (c.get("name") or "").lower()))
    return items


def compact(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: item.get(k) for k in LIST_KEYS}


def public(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in item.items() if not k.startswith("_")}


FEATURED = ("ffsa", "eurocup", "rotax")


def search(items: List[Dict[str, Any]], q: str = "", category: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """Recherche tolérante : tous les mots tapés doivent se retrouver dans la fiche.
    D'abord les fiches dont la marque, le nom ou un alias contient les mots, puis
    celles qui ne les ont que dans leurs usages (catégorie, championnat). Sans
    recherche, les pièces des catégories françaises et des séries passent en tête."""
    terms = _norm(q).split()
    hits = []
    for it in items:
        if category and it.get("category") != category:
            continue
        hay = it.get("_search") or ""
        if terms and not all(t in hay for t in terms):
            continue
        core = _norm(" ".join([str(it.get("brand") or ""), str(it.get("name") or "")] + list(it.get("aliases") or [])))
        in_core = 0 if terms and all(t in core for t in terms) else 1
        name = _norm(f"{it.get('brand')} {it.get('name')}")
        starts = 0 if terms and (name.startswith(terms[0]) or _norm(it.get("name")).startswith(terms[0])) else 1
        featured = 0 if any(f in _norm(" ".join(it.get("uses") or [])) for f in FEATURED) else 1
        sourced = 0 if (it.get("source_types") and it["source_types"] != ["base ApexAI"]) else 1
        hits.append((in_core, starts, featured, sourced, it))
    hits.sort(key=lambda h: h[:4])
    return [h[4] for h in hits[: max(1, min(limit, 300))]]


def match(items: List[Dict[str, Any]], label: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fiche la plus proche d'un libellé libre (« Rotax Max DD2 », « Vega Rouge SL4 »)."""
    target = set(_norm(label).split())
    if not target:
        return None
    best, best_key = None, (0.0, 0)
    for it in items:
        if category and it.get("category") != category:
            continue
        names = [f"{it.get('brand') or ''} {it.get('name') or ''}"] + [f"{it.get('brand') or ''} {a}" for a in it.get("aliases") or []]
        for n in names:
            cand = set(_norm(n).split())
            if not cand:
                continue
            # Jaccard : le libellé exact l'emporte sur une variante plus longue (X30 / X30 Junior)
            score = len(target & cand) / len(target | cand)
            key = (score, 1 if it.get("in_db") else 0)
            if key > best_key:
                best, best_key = it, key
    return best if best_key[0] >= 0.5 else None
