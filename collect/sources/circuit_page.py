"""
Fiche d'un circuit, lue sur le site du circuit lui-même (page d'accueil ou
page « contact » publique).

Analyse avec Scrapling (scrapling.parser.Selector) :
  1. données structurées schema.org (JSON-LD) quand le site en publie : nom,
     adresse, coordonnées GPS, téléphone d'accueil, site ;
  2. sinon balises Open Graph / meta ;
  3. longueur de piste repérée dans le texte (« piste de 1 200 m »).

Seules les informations de l'établissement sont gardées (jamais un nom de
personne, jamais un email nominatif). Les URL à lire sont dans
collect/sources/circuits_seed.json, ajoutées à la main après vérification
des conditions du site.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from scrapling.parser import Selector

SOURCE = "circuit_page"
_PLACE_TYPES = {"sportsactivitylocation", "localbusiness", "place", "organization", "sportsclub", "stadiumorarena", "touristattraction"}
_LEN = re.compile(r"(?:piste|tracé|circuit)[^.]{0,40}?(\d[\d\s. ]{2,6})\s?(?:m\b|mètres)", re.I)


def _ld_objects(page: Selector):
    for node in page.css('script[type="application/ld+json"]'):
        raw = (node.text or "").strip()
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, dict):
                if "@graph" in obj:
                    stack.extend(obj["@graph"])
                yield obj


def _first(*vals) -> Optional[str]:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return re.sub(r"\s+", " ", v).strip()
    return None


def parse_circuit(html: str, url: str) -> Optional[dict]:
    page = Selector(html, url=url)
    rec = {"source": SOURCE, "url": url, "name": None, "address": None, "postal_code": None,
           "city": None, "lat": None, "lng": None, "phone": None, "track_length_m": None}
    for obj in _ld_objects(page):
        types = obj.get("@type")
        types = {t.lower() for t in (types if isinstance(types, list) else [types]) if isinstance(t, str)}
        if not types & _PLACE_TYPES:
            continue
        rec["name"] = rec["name"] or _first(obj.get("name"))
        addr = obj.get("address")
        if isinstance(addr, dict):
            rec["address"] = rec["address"] or _first(addr.get("streetAddress"))
            rec["postal_code"] = rec["postal_code"] or _first(addr.get("postalCode"))
            rec["city"] = rec["city"] or _first(addr.get("addressLocality"))
        geo = obj.get("geo")
        if isinstance(geo, dict):
            try:
                rec["lat"] = rec["lat"] or float(geo.get("latitude"))
                rec["lng"] = rec["lng"] or float(geo.get("longitude"))
            except (TypeError, ValueError):
                pass
        rec["phone"] = rec["phone"] or _first(obj.get("telephone"))
    if not rec["name"]:
        og = page.css('meta[property="og:site_name"]::attr(content)').get() or page.css("title::text").get()
        rec["name"] = _first(og)
    text = " ".join(t.strip() for t in page.css("body *::text").getall() if t and t.strip())
    m = _LEN.search(text)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        if digits and 300 <= int(digits) <= 3000:
            rec["track_length_m"] = int(digits)
    if not rec["name"]:
        return None
    rec["collected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return rec


def collect(fetcher, seed: list[dict]) -> Iterable[dict]:
    for entry in seed:
        url = entry.get("url")
        if not url:
            continue
        rec = parse_circuit(fetcher.get(url, max_age_h=24 * 7), url)
        if rec:
            rec["circuit_key"] = entry.get("key")
            yield rec
