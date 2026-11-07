# -*- coding: utf-8 -*-
"""
Moteur de coaching « pilote pro » : faits → principes → sélection par niveau.

Niveaux (source unique : context.TIER_QUOTAS) :
  - sans compte : 3 conseils, tirés des seules mesures de la séance ;
  - compte gratuit : 5 conseils ; s'y ajoutent le type de chaque virage (base
    circuits), le moteur (courbe mesurée, eau), les pneus, la régularité et un
    conseil de style quand le même levier revient sur plusieurs virages ;
  - Racer : 6 conseils ; s'y ajoutent Mon Kart et le réglage (pressions selon
    la gomme, démultiplication en dents, voie arrière) et un plan pour la
    prochaine séance.
Les niveaux inférieurs reçoivent en plus un aperçu verrouillé d'un conseil
qu'ils débloqueraient (le constat, sans la consigne).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from . import fmt as F
from .context import TIER_LABEL, TIER_QUOTAS, TIER_RANK, build_kart_context, normalize_tier
from .facts import corner_facts, session_facts
from .principles import CORNER_PRINCIPLES, SESSION_PRINCIPLES, STYLE_LEVERS, Ctx, Finding

ENGINE_VERSION = "pro-1"
MAX_PER_CORNER = 2
SESSION_SLOTS = {"visitor": 0, "rookie": 1, "racer": 2}


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _info_items(conditions, track_condition, track_temperature, laps_analyzed, laps_used) -> List[Dict[str, Any]]:
    cond = (track_condition or "dry").lower()
    labels = {"dry": "Sec", "damp": "Humide", "wet": "Mouillée", "rain": "Pluie"}
    temp = f" {F.num(track_temperature)} °C" if track_temperature is not None else ""
    items = [{
        "priority": 0, "category": "info", "impact_seconds": 0.0, "corner": None,
        "message": f"{laps_analyzed} {F.plural(laps_analyzed, 'tour retenu', 'tours retenus')} — {labels.get(cond, 'Sec')}{temp}.",
        "explanation": ("Les tours de sortie et de rentrée des stands, ainsi que les tours ralentis (trafic, drapeau), "
                        f"sont écartés : ils fausseraient la comparaison. Les temps perdus annoncés sont mesurés sur ces "
                        f"{laps_analyzed} tour(s). {conditions.summary()}"),
        "difficulty": "facile",
    }]
    notes = {
        "damp": ("Piste humide", "Adhérence réduite d'environ 15 %. Évite les bords de piste et les zones à l'ombre, "
                                 "où l'eau reste. Anticipe les freinages."),
        "wet": ("Piste mouillée", "Priorité à la régularité : chaque erreur coûte plus cher à faible adhérence. Sors de "
                                  "la trajectoire sèche, freine roues droites et évite vibreurs et zones peintes."),
        "rain": ("Conditions pluvieuses", "Les vitesses de référence ne sont plus exploitables : travaille la fluidité, "
                                          "la vision et la trajectoire de pluie (hors de la gomme). Anticipe nettement les freinages."),
    }
    if cond in notes:
        t, b = notes[cond]
        items.append({"priority": 0, "category": "info", "impact_seconds": 0.0, "corner": None,
                      "message": t, "explanation": b, "difficulty": "facile"})
    return items


def _to_item(f: Finding, corners_by_id: Dict[int, Any], locked: bool = False,
             teaser_tier: Optional[str] = None) -> Dict[str, Any]:
    cf = corners_by_id.get(f.corner) if f.corner is not None else None
    head = f"{cf.head} — {_cap(f.headline)}" if cf else _cap(f.headline)
    lapref = ""
    if cf and cf.best_lap_here and f.family not in ("reglage", "pneus", "moteur") and f.principle != "sortie":
        lapref = f" Ton meilleur passage ici : tour {cf.best_lap_here}."
    body = " ".join(x for x in (f.fact, f.action, f.check) if x) + f.gain_txt() + lapref
    item = {
        "priority": 0, "category": f.category, "impact_seconds": round(float(f.impact_s or 0.0), 3),
        "corner": f.corner, "message": head, "explanation": body.strip(), "difficulty": f.difficulty,
        "principle": f.principle, "family": f.family, "fact": f.fact, "action": f.action, "check": f.check,
        "tier_required": f.min_tier,
    }
    if locked:
        need = teaser_tier or f.min_tier
        item.update({
            "locked": True, "tier_required": need,
            "explanation": "", "action": "", "check": "",
            "teaser": ("Avec un compte gratuit : 2 conseils de plus, reliés au circuit, au moteur et aux pneus."
                       if need == "rookie" else (f.teaser or "Débloque ce conseil avec Racer, relié à ton kart.")),
        })
    return item


EXIT_BASED = {"sortie", "moteur_plage"}


def _basis(f: Finding) -> str:
    """Mesure sur laquelle repose le temps annoncé : le virage entier, ou la relance qui suit."""
    return "relance" if f.principle in EXIT_BASED else "virage"


def _per_corner_filter(findings: List[Finding]) -> List[Finding]:
    """
    Au plus deux conseils par virage : un sur le virage lui-même, un sur la
    relance. Deux conseils qui s'appuient sur le même temps perdu diraient la
    même chose avec d'autres mots.
    """
    out, seen = [], {}
    for f in sorted(findings, key=lambda x: x.rank_s, reverse=True):
        if f.corner is None:
            out.append(f)
            continue
        prev = seen.setdefault(f.corner, [])
        if len(prev) >= MAX_PER_CORNER:
            continue
        if any(_basis(p) == _basis(f) or (p.lever and p.lever == f.lever) for p in prev):
            continue
        prev.append(f)
        out.append(f)
    return out


def _style(findings: List[Finding], x: Ctx) -> Optional[Finding]:
    by_lever: Dict[str, Dict[int, float]] = {}
    for f in findings:
        if f.corner is None or f.impact_s < 0.03:
            continue
        levers = [f.lever] + list(f.extra.get("levers") or [])
        # Le régime suit la vitesse : c'est une conséquence, pas un geste. On ne
        # le retient comme style que s'il est le seul levier du virage.
        if len(set(levers) - {"regime", None}) > 0:
            levers = [lv for lv in levers if lv != "regime"]
        for lv in set(levers):
            if lv in STYLE_LEVERS:
                by_lever.setdefault(lv, {})
                by_lever[lv][f.corner] = max(by_lever[lv].get(f.corner, 0.0), f.impact_s)
    best = max(by_lever.items(), key=lambda kv: (len(kv[1]), sum(kv[1].values())), default=None)
    if not best or len(best[1]) < 3:
        return None
    lv, corners = best
    ids = sorted(corners)
    total = sum(corners.values())
    phrase, action = STYLE_LEVERS[lv]
    fact = (f"Le même constat revient aux virages {', '.join(str(i) for i in ids[:-1])} et {ids[-1]} : "
            f"ensemble, {F.sec(total)} par tour.")
    return Finding("style", "style", "style", None, f"ton style : {phrase}", fact, action,
                   "Repère : c'est une habitude de pilotage, travaille-la sur tout le tour plutôt que virage par virage.",
                   impact_s=0.0, rank_s=total * 0.55, difficulty="moyen", min_tier="rookie", lever=lv,
                   extra={"corners": ids})


# Consigne courte de chaque principe, pour l'objectif de la prochaine séance.
_CUES = {
    "enrouler": "tourne un temps plus tard et enroule",
    "entree_calme": "calme ton entrée, kart à plat",
    "elan": "garde de l'élan",
    "sacrifier": "freine plus fort, pivote et ressors en V",
    "braquer_moins": "braque moins",
    "regime": "garde le moteur dans les tours",
    "corde_avancee": "tourne un peu plus tôt",
    "repere_freinage": "un repère de freinage fixe",
    "attaque_frein": "attaque le frein plus fort",
    "temps_mort": "enchaîne frein et gaz, sans roue libre",
    "pied_constant": "pied constant, un effleurement de frein",
    "lacher_frein": "lâche le frein plus tôt",
    "corde_tardive": "corde tardive, sortie en V",
    "regard_corde": "regarde la corde avant de braquer",
}


def _cue(f: Finding) -> str:
    """Consigne courte d'un conseil de virage."""
    if f.principle == "frein_point" and f.lever == "repere_freinage":
        return f.headline.replace("tu freines", "avance ton freinage de").split(" plus tôt")[0]
    return _CUES.get(f.lever or "", f.headline)


def _setup_line(f: Finding) -> Optional[str]:
    """Ce qui se fait hors piste ou au départ, en une ligne."""
    import re
    teeth = re.search(r"couronne :? ?(\d+ → \d+ dents)", f.action)
    press = re.search(r"Pressions à froid[^:]*: ([^.]+?\d\sbar)(?=\.|$)", f.action)
    if f.principle == "demultiplication":
        if teeth:
            return f"Au stand : couronne {teeth.group(1)}."
        return "Au stand : " + ("rallonge" if "courte" in f.headline else "raccourcis") + " d'une dent à la couronne."
    if press:
        return f"Au stand : pressions à froid {press.group(1)}."
    if f.principle == "eau":
        return ("Au stand : masque un tiers du radiateur." if "froid" in f.headline
                else "Au stand : découvre le radiateur, vise 55 à 60 °C.")
    if f.principle == "pneus_chauffe":
        return "Au départ : charge les pneus au tour de lancement, freine fort et accélère fort."
    if f.principle == "pneus_chute":
        return "En fin de séance : roule plus rond pour ménager les pneus."
    if f.principle == "regularite":
        return "Pour commencer : cinq tours à 98 %, mêmes repères, puis attaque."
    return None


def _plan(chosen: List[Finding], corners_by_id) -> Optional[Dict[str, Any]]:
    """
    Ta prochaine séance : UN objectif, deux points à garder en tête au plus, et
    le réglage à faire au stand s'il y en a un. Pas de découpage en relais : un
    pilote en roulage roule comme il veut, autant de fois qu'il veut.
    """
    setup = next((ln for ln in (_setup_line(f) for f in chosen if f.corner is None) if ln), None)
    corners, used = [], set()
    for f in chosen:
        if f.corner is None or f.corner in used:
            continue
        used.add(f.corner)
        corners.append(f)
    if not corners:
        return None
    lines = []
    if setup:
        lines.append(setup)
    main = corners[0]
    lines.append(f"Objectif : virage {main.corner}, {_cue(main)}.")
    rest = [f"virage {f.corner}, {_cue(f)}" for f in corners[1:3] if _cue(f) != _cue(main)]
    if rest:
        lines.append("Si ça vient bien : " + " ; ".join(rest) + ".")
    return {
        "priority": 0, "category": "plan", "impact_seconds": 0.0, "corner": None,
        "message": "Ta prochaine séance",
        "explanation": " ".join(lines), "difficulty": "facile",
        "principle": "plan", "family": "plan", "tier_required": "racer",
        "steps": lines,
    }


def generate_pro_coaching(
    df,
    corner_analysis: List[Dict[str, Any]],
    *,
    track_condition: str = "dry",
    track_temperature: Optional[float] = None,
    laps_analyzed: int = 1,
    laps_used: Optional[List[int]] = None,
    ideal_lap: Optional[Dict[str, Any]] = None,
    tier: Optional[str] = "visitor",
    kart_raw: Optional[Dict[str, Any]] = None,
    circuit: Optional[Dict[str, Any]] = None,
    vehicle_hint: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from src.analysis.conditions import get_conditions, resolve_conditions

    tier = normalize_tier(tier)
    conditions = get_conditions(df)
    if conditions.condition != (track_condition or "dry").lower():
        conditions = resolve_conditions(track_condition, track_temperature)
    laps_used = list(laps_used or [])
    # pandas recopie df.attrs (freinages, ligne idéale…) à chaque accès de
    # colonne : avec des métadonnées volumineuses, un calcul d'une seconde en
    # prenait plus de cent. On les met de côté le temps des mesures.
    saved_attrs = df.attrs
    df.attrs = {}
    try:
        sess = session_facts(df, laps_used, ideal_lap)
        corners = corner_facts(df, corner_analysis, laps_used, ideal_lap, sess,
                               circuit if TIER_RANK[tier] >= 1 else None)
    finally:
        df.attrs = saved_attrs
    kart = build_kart_context(kart_raw) if tier == "racer" else None
    voice = F.Voice(seed=f"{len(corners)}|{sess.best_lap_time}")
    from .context import _engine_family
    family = (kart.engine if kart and kart.engine else None) or _engine_family(vehicle_hint)
    x = Ctx(tier=tier, session=sess, corners=corners, kart=kart, conditions=conditions, voice=voice,
            track_temp=track_temperature, engine_family=family or {})
    # Les principes sont évalués pour le niveau Racer aussi quand le pilote ne
    # l'est pas : c'est ce qui permet de lui montrer, verrouillé, ce qu'il
    # débloquerait. Le texte, lui, dépend de son niveau (x.allows).
    by_id = {c.id: c for c in corners}
    raw: List[Finding] = []
    for cf in corners:
        for p in CORNER_PRINCIPLES:
            try:
                f = p.fn(cf, x)
            except Exception:
                f = None
            if f:
                f.extra["_src"] = (p.fn, cf)
                raw.append(f)
    session_found: List[Finding] = []
    for p in SESSION_PRINCIPLES:
        try:
            f = p.fn(x)
        except Exception:
            f = None
        if f:
            f.extra["_src"] = (p.fn, None)
            session_found.append(f)
    corner_found = _per_corner_filter(raw)
    style = _style(corner_found, x)
    all_found = corner_found + session_found + ([style] if style else [])

    def allowed(f: Finding, t: str) -> bool:
        return TIER_RANK[t] >= TIER_RANK.get(f.min_tier, 0)

    def select(t: str) -> List[Finding]:
        q = TIER_QUOTAS[t]
        pool = sorted([f for f in all_found if allowed(f, t)], key=lambda f: f.rank_s, reverse=True)
        # Racer : ce qui est relié au kart et au réglage est la valeur de l'offre.
        # Au moins un de ces conseils figure dans la liste quand il y en a un.
        racer_only = [f for f in pool if f.min_tier == "racer"] if t == "racer" else []
        chosen: List[Finding] = []
        fam_count: Dict[str, int] = {}
        sess_used = 0
        while pool and len(chosen) < q:
            def score(f):
                return f.rank_s * (0.8 ** fam_count.get(f.family, 0))
            pool.sort(key=score, reverse=True)
            f = pool.pop(0)
            if f.corner is None and f.family != "style":
                if sess_used >= SESSION_SLOTS[t]:
                    continue
                sess_used += 1
            chosen.append(f)
            fam_count[f.family] = fam_count.get(f.family, 0) + 1
        if racer_only and not any(f.min_tier == "racer" for f in chosen) and chosen:
            chosen[-1] = racer_only[0]
        # Retour d'Auxence : une relance qui coûte au moins 0,03 s figure toujours dans la liste.
        ex = next((f for f in sorted(all_found, key=lambda f: f.impact_s, reverse=True)
                   if f.principle == "sortie" and f.impact_s >= 0.03 and allowed(f, t)), None)
        if ex and ex not in chosen and chosen:
            idx = next((i for i in range(len(chosen) - 1, -1, -1) if chosen[i].min_tier != "racer"
                        and chosen[i].principle != "sortie"), None)
            if idx is not None:
                chosen[idx] = ex
        # Ordre d'affichage : temps mesuré d'abord, puis le reste par poids.
        chosen.sort(key=lambda f: (f.impact_s > 0, f.impact_s, f.rank_s), reverse=True)
        return chosen

    chosen = select(tier)
    # Rédaction finale, dans l'ordre d'affichage : chaque consigne n'est écrite
    # qu'une fois dans la séance (les formulations essayées par des conseils
    # écartés ne comptent plus).
    x.voice = F.Voice(seed=voice.seed)
    rendered = []
    for f in chosen:
        src = f.extra.get("_src")
        g = None
        if src:
            try:
                g = src[0](src[1], x) if src[1] is not None else src[0](x)
            except Exception:
                g = None
        if g:
            g.extra = {**f.extra, **g.extra}
            g.rank_s = f.rank_s
            rendered.append(g)
        else:
            rendered.append(f)
    chosen = rendered
    items = _info_items(conditions, track_condition, track_temperature, laps_analyzed, laps_used)
    real = [_to_item(f, by_id) for f in chosen]
    for i, it in enumerate(real, start=1):
        it["priority"] = i
    out = items + real

    if tier == "racer":
        plan = _plan(chosen, by_id)
        if plan:
            out.append(plan)

    # Aperçu verrouillé : UN conseil du niveau suivant, flouté (constat sans la
    # consigne). Sans compte : le prochain conseil du compte gratuit. Compte
    # gratuit : un conseil Racer (relié au kart), sinon le plan de séance.
    locked: List[Dict[str, Any]] = []
    if tier == "visitor":
        nxt = [f for f in select("rookie") if f not in chosen and f.principle not in {c.principle for c in chosen} | {""}]
        nxt = nxt or [f for f in select("rookie") if f not in chosen]
        if nxt:
            locked.append(_to_item(nxt[0], by_id, locked=True, teaser_tier="rookie"))
    elif tier == "rookie":
        racer_only = sorted([f for f in all_found if f.min_tier == "racer"], key=lambda f: f.rank_s, reverse=True)
        if racer_only:
            locked.append(_to_item(racer_only[0], by_id, locked=True, teaser_tier="racer"))
        else:
            locked.append({
                "priority": 0, "category": "plan", "impact_seconds": 0.0, "corner": None,
                "message": "Ta prochaine séance", "explanation": "", "difficulty": "facile",
                "principle": "plan", "family": "plan", "tier_required": "racer", "locked": True,
                "teaser": "Ton objectif pour la prochaine séance, relié à ton kart et à ton réglage",
            })
    for it in locked:
        it["priority"] = len(real) + 1
    out += locked

    meta = {
        "engine": ENGINE_VERSION,
        "tier": tier, "tier_label": TIER_LABEL[tier],
        "quota": TIER_QUOTAS[tier], "shown": len(real), "locked": len(locked),
        "uses": {
            "circuit": any(c.kind_source == "circuit" for c in corners),
            "engine_curve": sess.engine is not None,
            "water": bool(sess.water_by_lap),
            "kart": bool(kart and kart.has_kart),
            "setup": bool(kart and kart.has_setup),
        },
        "found": sorted({f.principle for f in all_found}),
        "engine_curve": ({"knee_rpm": round(sess.engine.knee_rpm), "peak_rpm": round(sess.engine.peak_rpm),
                          "top_rpm": round(sess.engine.top_rpm), "top_plateau_s": round(sess.engine.top_plateau_s, 2)}
                         if sess.engine else None),
    }
    return out, meta
