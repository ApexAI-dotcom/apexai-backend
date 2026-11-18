"""
Circuits de karting en France, depuis OpenStreetMap (API Overpass).

Pourquoi OSM d'abord : c'est une base ouverte (licence ODbL), faite pour être
réutilisée, avec une politique d'usage claire (quelques requêtes par jour,
identification). Conditions à respecter si on affiche ces données :
mention « © les contributeurs d'OpenStreetMap » et, si on republie la base
dérivée, la partager sous la même licence (ODbL).

Une seule requête par collecte, résultat gardé 7 jours en cache.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable, List
from urllib.parse import urlencode

SOURCE = "osm_circuits"
ENDPOINT = "https://overpass-api.de/api/interpreter"
ATTRIBUTION = "© les contributeurs d'OpenStreetMap (ODbL)"
QUERY = (
    '[out:json][timeout:90];'
    'area["ISO3166-1"="FR"][admin_level=2]->.fr;'
    '(way["sport"="karting"](area.fr);relation["sport"="karting"](area.fr);node["sport"="karting"](area.fr););'
    'out tags center;'
)


def _length(tags: dict):
    raw = (tags.get("length") or "").lower().replace(",", ".").replace("m", "").strip()
    try:
        v = float(raw.replace("k", "")) * (1000 if "k" in raw else 1)
        return int(v) if 200 <= v <= 3000 else None
    except ValueError:
        return None


def parse_overpass(payload: str | dict) -> List[dict]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out, seen = [], set()
    for el in data.get("elements") or []:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lng = el.get("lon", (el.get("center") or {}).get("lon"))
        if not name or lat is None or lng is None:
            continue  # un tracé sans nom ne sert à rien pour l'app
        key = (name.lower(), round(lat, 2), round(lng, 2))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "source": SOURCE,
            "source_id": f"osm:{el.get('type')}/{el.get('id')}",
            "name": name,
            "lat": round(float(lat), 6),
            "lng": round(float(lng), 6),
            "city": tags.get("addr:city"),
            "postal_code": tags.get("addr:postcode"),
            "website": tags.get("website") or tags.get("contact:website"),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "surface": tags.get("surface"),
            "track_length_m": _length(tags),
            "kind": tags.get("leisure") or tags.get("amenity"),
            "attribution": ATTRIBUTION,
            "collected_at": now,
        })
    out.sort(key=lambda r: r["name"])
    return out


def collect(fetcher) -> Iterable[dict]:
    url = f"{ENDPOINT}?{urlencode({'data': QUERY})}"
    yield from parse_overpass(fetcher.get(url, max_age_h=24 * 7))
