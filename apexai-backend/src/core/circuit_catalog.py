#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Base des circuits de karting de France (lecture seule, en mémoire).

Le fichier src/data/circuit_catalog.json est produit par scripts/circuits/ du
dépôt front (annuaire FFSA « Où pratiquer » + tracés OpenStreetMap, © ses
contributeurs, ODbL). On le charge une fois : recherche par nom / commune /
département, fiche détaillée, et reconnaissance du circuit d'une session à
partir de ses points GPS.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DATA = Path(__file__).resolve().parents[1] / "data" / "circuit_catalog.json"
SUMMARY_KEYS = (
    "slug", "name", "city", "postal_code", "department_code", "department", "region", "lat", "lon",
    "indoor", "surface", "width_m", "length_m", "trace_status", "corners_count", "hairpins_count",
    "medium_count", "fast_corners_count", "website", "osm_url", "source",
)


def _norm(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": None, "circuits": []}
    for c in data.get("circuits", []):
        c["_search"] = _norm(" ".join(str(c.get(k) or "") for k in ("name", "city", "department", "department_code", "region"))
                             + " " + " ".join(s.get("name", "") for s in c.get("ffsa_structures") or []))
        c["rotation"] = rotation_of(c.get("centerline") or [])
    return data


def version() -> Optional[str]:
    return _load().get("version")


def all_circuits() -> List[Dict[str, Any]]:
    return _load().get("circuits", [])


def summary(c: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: c.get(k) for k in SUMMARY_KEYS}
    out["rotation"] = c.get("rotation")
    out["ffsa"] = [s.get("name") for s in (c.get("ffsa_structures") or [])][:3]
    out["has_trace"] = bool(c.get("centerline"))
    return out


def detail(c: Dict[str, Any]) -> Dict[str, Any]:
    out = summary(c)
    out["corners"] = c.get("corners") or []
    out["centerline"] = c.get("centerline") or []
    out["ffsa_structures"] = c.get("ffsa_structures") or []
    out["phone"] = c.get("phone")
    out["attribution"] = "© contributeurs OpenStreetMap" if c.get("centerline") else None
    return out


def get(slug: str) -> Optional[Dict[str, Any]]:
    return next((c for c in all_circuits() if c.get("slug") == slug), None)


def search(q: str = "", dept: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Recherche tolérante (accents, tirets) ; les tracés complets d'abord."""
    terms = _norm(q).split()
    rank = {"complet": 0, "fermé hors gabarit": 1, "partiel": 2, "à dessiner": 3}
    hits = []
    for c in all_circuits():
        if dept and (c.get("department_code") or "") != dept:
            continue
        if terms and not all(t in c["_search"] for t in terms):
            continue
        starts = 0 if terms and _norm(c.get("name")).startswith(terms[0]) else 1
        hits.append((starts, rank.get(c.get("trace_status"), 9), c.get("name") or "", c))
    hits.sort(key=lambda h: h[:3])
    return [h[3] for h in hits[: max(1, min(limit, 100))]]


def _dist_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[1] - b[1]) * k, a[0] - b[0]) * 111195.0


def rotation_of(line: Sequence[Sequence[float]]) -> Optional[str]:
    """Sens de rotation du tracé (aire signée) : « horaire » ou « anti-horaire »."""
    if len(line) < 10:
        return None
    lat0 = sum(p[0] for p in line) / len(line)
    k = math.cos(math.radians(lat0))
    area = 0.0
    for (a, b), (c, d) in zip(line, list(line[1:]) + [line[0]]):
        area += (b * k) * c - (d * k) * a
    # x = lon, y = lat : aire positive = sens trigonométrique (anti-horaire)
    return "anti-horaire" if area > 0 else "horaire"


def match_points(points: Iterable[Tuple[float, float]], max_m: float = 1500.0) -> Optional[Dict[str, Any]]:
    """
    Circuit de la session : le plus proche du centre de ses points GPS. Si
    plusieurs pistes partagent le site, on garde celle dont le tracé colle le
    mieux aux points (distance médiane point → tracé).
    """
    pts = [(float(a), float(b)) for a, b in points if a is not None and b is not None and not (math.isnan(a) or math.isnan(b))]
    if len(pts) < 20:
        return None
    step = max(1, len(pts) // 300)
    pts = pts[::step]
    clat = sum(p[0] for p in pts) / len(pts)
    clon = sum(p[1] for p in pts) / len(pts)
    near = []
    for c in all_circuits():
        if c.get("lat") is None:
            continue
        d = _dist_m((clat, clon), (c["lat"], c["lon"]))
        if d <= max_m:
            near.append((d, c))
    if not near:
        return None

    def fit(c: Dict[str, Any]) -> float:
        line = c.get("centerline") or []
        if len(line) < 10:
            return float("inf")
        sample = pts[:: max(1, len(pts) // 60)]
        ds = sorted(min(_dist_m(p, (q[0], q[1])) for q in line) for p in sample)
        return ds[len(ds) // 2]

    scored = sorted(((fit(c), d, c) for d, c in near), key=lambda x: (x[0], x[1]))
    best_fit, best_d, best = scored[0]
    if best_fit == float("inf"):
        best_d, best = min(near, key=lambda x: x[0])
    out = summary(best)
    out["distance_m"] = round(best_d)
    out["trace_fit_m"] = None if best_fit == float("inf") else round(best_fit, 1)
    # Correspondance sûre : tracé à moins de 15 m des points de la session
    out["confident"] = best_fit != float("inf") and best_fit <= 15.0
    return out


GENERIC = {"kart", "karting", "circuit", "piste", "track", "de", "du", "des", "la", "le", "les", "d", "l", "raceway", "club"}


def _tokens(name: str) -> List[str]:
    # « CarpentrasK » -> carpentras, k ; « Ales Kart » -> ales, kart
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name or "")
    return [t for t in _norm(spaced).split() if len(t) >= 3 and t not in GENERIC]


def match_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Circuit le plus probable pour un nom tel que l'écrit le boîtier (« SoloKart »,
    « CarpentrasK », « Ales Kart »). Sert aux anciennes analyses sans tracé GPS :
    tous les mots distinctifs du nom doivent se retrouver dans le nom ou la
    commune de la fiche, sinon aucune correspondance.
    """
    toks = _tokens(name)
    if not toks:
        return None
    best = None
    for c in all_circuits():
        name_words = _norm(c.get("name")).split() + [w for s in c.get("ffsa_structures") or [] for w in _norm(s.get("name")).split()]
        city_words = _norm(c.get("city")).split()

        def hit(t: str, words: List[str]) -> bool:
            return any(w.startswith(t) or (len(w) >= 4 and t.startswith(w)) for w in words)

        if not all(hit(t, name_words + city_words) for t in toks):
            continue
        in_name = sum(1 for t in toks if hit(t, name_words))
        score = (-in_name, 0 if c.get("centerline") else 1, 0 if c.get("trace_status") == "complet" else 1)
        if best is None or score < best[0]:
            best = (score, c)
    return best[1] if best else None
