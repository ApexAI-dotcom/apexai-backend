#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Base des circuits de karting de France (API).

  GET  /api/catalog/circuits?q=&dept=&limit=   recherche (fiches résumées)
  GET  /api/catalog/circuits/{slug}             fiche complète avec le tracé
  POST /api/catalog/circuits/match-names        tracés des circuits d'après leur nom
                                                (anciennes analyses sans GPS)
  POST /api/catalog/circuits/match-points       circuit d'après des points GPS

Base des composants 2026-2027 (table kart_components + fiches sourcées) :

  GET  /api/catalog/parts?q=&category=&limit=   recherche
  GET  /api/catalog/parts/match?label=&category= fiche la plus proche d'un libellé
  GET  /api/catalog/parts/{id}                  fiche complète (entretien, sources)

Tracés © contributeurs OpenStreetMap (ODbL) : l'attribution accompagne
chaque fiche qui porte un tracé.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core import circuit_catalog as cc
from src.core import component_catalog as compcat

from .auth import get_current_user

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/circuits")
async def search_circuits(q: str = "", dept: Optional[str] = None, limit: int = 20):
    return {"version": cc.version(), "circuits": [cc.summary(c) for c in cc.search(q, dept, limit)]}


@router.get("/circuits/{slug}")
async def circuit_detail(slug: str, current_user: str = Depends(get_current_user)):
    c = cc.get(slug)
    if not c:
        raise HTTPException(status_code=404, detail="Circuit introuvable.")
    return {"circuit": cc.detail(c)}


class NamesIn(BaseModel):
    names: List[str] = Field(default_factory=list, max_length=60)


@router.post("/circuits/match-names")
async def match_names(payload: NamesIn, current_user: str = Depends(get_current_user)):
    out: Dict[str, Any] = {}
    for n in payload.names[:60]:
        c = cc.match_name(n)
        if c:
            d = cc.summary(c)
            d["centerline"] = c.get("centerline") or []
            out[n] = d
    return {"matches": out}


class PointsIn(BaseModel):
    lat: List[float] = Field(default_factory=list, max_length=5000)
    lon: List[float] = Field(default_factory=list, max_length=5000)


@router.post("/circuits/match-points")
async def match_points(payload: PointsIn, current_user: str = Depends(get_current_user)):
    return {"circuit": cc.match_points(zip(payload.lat, payload.lon))}


def _parts(category: Optional[str] = None):
    from .kart_service import KartService

    return KartService.get_catalog_components(category)


@router.get("/parts")
async def search_parts(q: str = "", category: Optional[str] = None, limit: int = 40):
    items = _parts(category)
    hits = compcat.search(items, q, category, limit)
    counts: Dict[str, int] = {}
    for it in items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1
    return {
        "version": compcat.version(),
        "categories": compcat.categories(),
        "counts": counts,
        "total": len(items),
        "parts": [compcat.compact(h) for h in hits],
    }


@router.get("/parts/match")
async def match_part(label: str, category: Optional[str] = None):
    hit = compcat.match(_parts(category), label, category)
    return {"part": compcat.public(hit) if hit else None}


@router.get("/parts/{part_id}")
async def part_detail(part_id: str):
    hit = next((c for c in _parts() if c.get("id") == part_id), None)
    if not hit:
        raise HTTPException(status_code=404, detail="Pièce introuvable.")
    return {"part": compcat.public(hit)}
