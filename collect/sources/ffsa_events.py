"""
Calendrier officiel FFSA Karting (Championnats et Coupes de France).

Source : la page publique https://www.ffsakarting.org/evenement charge ses
données depuis /ajax/events (JSON public, sans compte). On lit ce même JSON :
c'est ce que le navigateur de n'importe quel visiteur reçoit, et c'est plus
stable que l'HTML. Aucune donnée personnelle : lieu, date, compétition,
catégories, lien.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Iterable, List

BASE = "https://www.ffsakarting.org"
SOURCE = "ffsa_events"


def _iso(d: str) -> str | None:
    try:
        return datetime.strptime(d.strip(), "%d.%m.%Y").date().isoformat()
    except (ValueError, AttributeError):
        return None


def parse_events(payload: str | dict, season: int) -> List[dict]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not data.get("success"):
        return []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for ev in data.get("data") or []:
        day = _iso(ev.get("date", ""))
        place = (ev.get("place") or "").strip()
        if not day or not place:
            continue
        url = ev.get("url") or ""
        out.append({
            "source": SOURCE,
            "source_id": f"ffsa:{ev.get('id')}",
            "season": season,
            "date": day,
            "place": place,
            "competition": (ev.get("competition") or "").strip(),
            "categories": [c.strip() for c in ev.get("categories") or [] if c and c.strip()],
            "url": url if url.startswith(BASE) else None,
            "collected_at": now,
        })
    out.sort(key=lambda r: r["date"])
    return out


def seasons_to_fetch(filters_payload: str | dict, today: date | None = None) -> List[int]:
    """Saison en cours, plus la suivante si la fédération l'a déjà publiée."""
    data = json.loads(filters_payload) if isinstance(filters_payload, str) else filters_payload
    years = set((data.get("data") or {}).get("years") or [])
    y = (today or date.today()).year
    return [s for s in (y, y + 1) if s in years] or sorted(years, reverse=True)[:1]


def collect(fetcher, today: date | None = None) -> Iterable[dict]:
    filters = fetcher.get(f"{BASE}/ajax/events/filters", max_age_h=24)
    for season in seasons_to_fetch(filters, today):
        yield from parse_events(fetcher.get(f"{BASE}/ajax/events?year={season}", max_age_h=12), season)
