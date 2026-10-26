#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Base des circuits de karting de France (API).

  GET  /api/catalog/circuits?q=&dept=&limit=   recherche (fiches résumées)
  GET  /api/catalog/circuits/{slug}             fiche complète avec le tracé
  POST /api/catalog/circuits/match-names        tracés des circuits d'après leur nom
                                                (anciennes analyses sans GPS)
  POST /api/catalog/circuits/match-points       circuit d'après des points GPS

Tracés © contributeurs OpenStreetMap (ODbL) : l'attribution accompagne
chaque fiche qui porte un tracé.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core import circuit_catalog as cc

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
