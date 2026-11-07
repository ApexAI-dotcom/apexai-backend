# -*- coding: utf-8 -*-
"""
Contexte du pilote : niveau d'accès, kart (Mon Kart), réglage, pneus.

Tout est facultatif. Un champ inconnu reste None et les principes qui en
dépendent passent à leur version générique ou se taisent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Niveaux d'analyse. « team » a les droits de « racer ».
TIERS = ("visitor", "rookie", "racer")
TIER_RANK = {"visitor": 0, "rookie": 1, "racer": 2, "team": 2}
# Conseils affichés par niveau (hors encarts de contexte et hors aperçu verrouillé).
TIER_QUOTAS = {"visitor": 3, "rookie": 5, "racer": 6}
TIER_LABEL = {"visitor": "Sans compte", "rookie": "Compte gratuit", "racer": "Racer"}


def normalize_tier(tier: Optional[str]) -> str:
    t = (tier or "visitor").strip().lower()
    if t in ("team", "pro"):
        return "racer"
    return t if t in TIER_RANK else "rookie"


def _f(v) -> Optional[float]:
    try:
        x = float(str(v).replace(",", "."))
        return x
    except (TypeError, ValueError):
        return None


def _i(v) -> Optional[int]:
    x = _f(v)
    return int(round(x)) if x is not None else None


# Régime de bout de ligne droite visé (tr/min) et plage utile, par famille de
# moteur. Valeurs usuelles de préparateurs, utilisées seulement pour nommer la
# cible : les conseils de démultiplication s'appuient d'abord sur ce que le
# moteur du pilote fait réellement dans ses données.
ENGINE_FAMILIES = [
    (r"micro", {"label": "Rotax Micro Max", "top": 12000, "cooling": "liquide"}),
    (r"mini ?max|rotax mini", {"label": "Rotax Mini Max", "top": 12800, "cooling": "liquide"}),
    (r"junior", {"label": "moteur Junior", "top": 13500, "cooling": "liquide"}),
    (r"dd2", {"label": "Rotax DD2", "top": 13800, "cooling": "liquide", "gearbox": True}),
    (r"rotax|max evo|fr125", {"label": "Rotax Max", "top": 13800, "cooling": "liquide"}),
    (r"x30", {"label": "IAME X30", "top": 15500, "cooling": "liquide"}),
    (r"ka100", {"label": "IAME KA100", "top": 16000, "cooling": "air"}),
    (r"kz|r1|r2|rvx|kz10", {"label": "moteur KZ", "top": 14000, "cooling": "liquide", "gearbox": True}),
    (r"rok", {"label": "Vortex ROK", "top": 14000, "cooling": "liquide"}),
    (r"gx|kx21|4 ?t", {"label": "moteur 4 temps", "top": None, "cooling": "air"}),
]


@dataclass
class KartContext:
    engine_model: Optional[str] = None
    engine: Dict[str, Any] = field(default_factory=dict)       # famille + specs catalogue
    tire_model: Optional[str] = None
    tire: Optional[Dict[str, Any]] = None                      # composant catalogue
    chassis: Optional[str] = None
    driver_weight_kg: Optional[float] = None
    cold_front: Optional[float] = None
    cold_rear: Optional[float] = None
    hot_front: Optional[float] = None
    hot_rear: Optional[float] = None
    sprocket_front: Optional[int] = None
    sprocket_rear: Optional[int] = None
    track_rear_mm: Optional[float] = None
    setup_name: Optional[str] = None
    setup_circuit: Optional[str] = None

    @property
    def has_kart(self) -> bool:
        return bool(self.engine_model or self.tire_model or self.chassis)

    @property
    def has_setup(self) -> bool:
        return any(v is not None for v in (self.cold_front, self.cold_rear, self.sprocket_rear))

    @property
    def ratio(self) -> Optional[float]:
        if self.sprocket_front and self.sprocket_rear:
            return self.sprocket_rear / self.sprocket_front
        return None


def _engine_family(model: Optional[str]) -> Dict[str, Any]:
    m = (model or "").lower()
    for pat, fam in ENGINE_FAMILIES:
        if re.search(pat, m):
            return dict(fam)
    return {}


# Abaque de la base composants (pressions à froid, cible à chaud, en bar), par
# gomme. Sert de repli quand la base n'est pas joignable (tests, banc d'essai).
COMPOUND_PRESSURES = {
    "soft": {"dry": (0.55, 0.70), "damp": (0.70, 0.90), "hot": (0.80, 0.95)},
    "medium": {"dry": (0.60, 0.80), "damp": (0.75, 0.95), "hot": (0.85, 1.00)},
    "hard": {"dry": (0.65, 0.85), "damp": (0.80, 1.00), "hot": (0.90, 1.05)},
    "wet": {"wet": (1.00, 1.20), "damp": (0.90, 1.10), "hot": (1.15, 1.35)},
}
_COMPOUND_HINTS = [
    (r"\bw\d|wet|pluie|rain|bleu w|k1w|blanc wt", "wet"),
    (r"xm3|blanc|soft|svb|svc|prime|\bs\b", "soft"),
    (r"sl4|rouge sl|medium|k2m|jaune|yds|d5", "medium"),
    (r"xh3|vert|hard|k2h|rouge sh|d2", "hard"),
]


def _compound_of(label: str) -> Optional[str]:
    lo = label.lower()
    for pat, comp in _COMPOUND_HINTS:
        if re.search(pat, lo):
            return comp
    return None


def _match_tire(label: Optional[str]) -> Optional[Dict[str, Any]]:
    if not label:
        return None
    comp = None
    try:
        from src.api.advisor_service import match_tire_component
        from src.api.kart_service import KartService
        comp = match_tire_component(label, KartService.get_catalog_components("tire") or [])
    except Exception:
        comp = None
    # La marque seule ne suffit pas (« Vega Blanc XM3 » n'est pas « Vega Cadetti ») :
    # il faut au moins un mot du nom de la gomme en commun.
    if comp:
        lab = set(re.sub(r"[^a-z0-9 ]", " ", label.lower()).split())
        name = set(re.sub(r"[^a-z0-9 ]", " ", (comp.get("name") or "").lower()).split())
        if not (lab & name):
            comp = None
    specs = dict((comp or {}).get("specs") or {})
    compound = (specs.get("compound") or _compound_of(label) or "").lower() or None
    table = COMPOUND_PRESSURES.get(compound or "")
    cold = specs.get("cold_pressure_bar") or ({k: list(v) for k, v in table.items() if k != "hot"} if table else {})
    hot = specs.get("target_hot_bar") or (list(table["hot"]) if table else None)
    if not compound and not cold:
        return None
    name = " ".join(x for x in ((comp or {}).get("brand"), (comp or {}).get("name")) if x) or label
    return {"name": name, "compound": compound, "cold": cold, "hot": hot,
            "source": "base composants" if comp else "abaque ApexAI"}


def build_kart_context(raw: Optional[Dict[str, Any]]) -> Optional[KartContext]:
    """
    `raw` : profil Mon Kart + réglage (clés de kart_profiles / kart_setups, ou
    forme courte du banc d'essai). Retourne None si rien d'exploitable.
    """
    if not raw:
        return None
    setup = dict(raw.get("setup") or {})
    prof_setup = raw.get("setup_json") or {}
    k = KartContext()
    k.engine_model = raw.get("engine_model") or None
    k.engine = _engine_family(k.engine_model)
    k.tire_model = setup.get("tire_model") or raw.get("tires_model") or raw.get("tire_model") or None
    if k.tire_model and k.tire_model.lower() == "standard":
        k.tire_model = None
    k.tire = _match_tire(k.tire_model)
    k.chassis = " ".join(x for x in (raw.get("chassis_brand") or prof_setup.get("chassis_brand"),
                                      raw.get("chassis_model") or prof_setup.get("chassis_model")) if x) or None
    k.driver_weight_kg = _f(setup.get("driver_weight") or raw.get("driver_weight_kg"))
    k.cold_front = _f(setup.get("cold_pressure_front") or setup.get("front_pressure") or prof_setup.get("pressure_f"))
    k.cold_rear = _f(setup.get("cold_pressure_rear") or setup.get("rear_pressure") or prof_setup.get("pressure_r"))
    k.hot_front = _f(setup.get("hot_pressure_front"))
    k.hot_rear = _f(setup.get("hot_pressure_rear"))
    k.sprocket_front = _i(setup.get("sprocket_front"))
    k.sprocket_rear = _i(setup.get("sprocket_rear") or setup.get("sprocket_teeth"))
    k.track_rear_mm = _f(setup.get("track_width_rear") or setup.get("rear_track_width"))
    k.setup_name = (setup.get("setup_name") or "").strip() or None
    k.setup_circuit = setup.get("circuit") or None
    if not k.has_kart and not k.has_setup:
        return None
    return k


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_kart_context(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Lit Mon Kart, les réglages enregistrés et le train de pneus monté. Le
    réglage de la séance est choisi ensuite (select_setup), une fois le
    circuit connu. Jamais bloquant : None en cas de souci.
    """
    try:
        from src.api.kart_service import supabase
        if not supabase or not user_id:
            return None
        prof = supabase.table("kart_profiles").select("*").eq("user_id", user_id).limit(1).execute().data
        prof = prof[0] if prof else {}
        setups = (supabase.table("kart_setups").select("*, circuits(name)").eq("user_id", user_id)
                  .order("created_at", desc=True).limit(30).execute().data) or []
        tires = (supabase.table("kart_tire_sets").select("*").eq("user_id", user_id)
                 .eq("is_mounted", True).limit(5).execute().data) or []
    except Exception:
        return None
    raw = {k: prof.get(k) for k in ("engine_model", "tires_model", "driver_weight_kg", "setup_json", "updated_at")}
    sp = prof.get("setup_json") or {}
    raw["chassis_brand"] = sp.get("chassis_brand")
    raw["chassis_model"] = sp.get("chassis_model")
    for s_ in setups:
        s_["circuit"] = ((s_.get("circuits") or {}) or {}).get("name")
        s_.pop("circuits", None)
    raw["setups"] = setups
    dry_mounted = next((t for t in tires if not t.get("is_rain")), None)
    if dry_mounted:
        raw["mounted_tire"] = dry_mounted.get("custom_model") or dry_mounted.get("component_id")
    return raw


def select_setup(raw: Optional[Dict[str, Any]], circuit_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Réglage du même circuit s'il existe, sinon le plus récent. Retourne une copie de `raw`."""
    if not raw:
        return raw
    out = dict(raw)
    setups = list(raw.get("setups") or [])
    chosen = None
    cn = _norm(circuit_name)
    if cn:
        for s_ in setups:
            name = _norm(s_.get("circuit"))
            if name and (cn in name or name in cn or cn[:5] == name[:5]):
                chosen = s_
                break
    chosen = chosen or (setups[0] if setups else None)
    if chosen and not out.get("setup"):
        out["setup"] = chosen
    if not (out.get("setup") or {}).get("tire_model") and raw.get("mounted_tire"):
        out["tires_model"] = raw["mounted_tire"]
    return out


def kart_cache_key(raw: Optional[Dict[str, Any]]) -> str:
    """Empreinte courte du contexte kart : le cache d'analyse en dépend."""
    if not raw:
        return "nokart"
    import hashlib
    import json
    return hashlib.sha1(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()[:12]
