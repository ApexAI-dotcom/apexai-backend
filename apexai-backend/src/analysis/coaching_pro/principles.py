# -*- coding: utf-8 -*-
"""
Base de principes de pilotage, reliée aux mesures.

Chaque principe est ce qu'un coach ou un ingénieur de piste dirait devant les
données : un constat chiffré tiré de la séance, une consigne applicable au
prochain relais, et un repère pour vérifier que ça a marché. Un principe ne
parle que si sa mesure le déclenche ; s'il lui manque une donnée (pas de
capteur de régime, pas de kart renseigné…), il passe à sa version simple ou
se tait. Aucun gain n'est estimé : le temps annoncé est toujours mesuré.

Familles : freinage, entrée, trajectoire (selon le type de virage), sortie et
relance, moteur, pneus, réglage, régularité, conditions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from . import fmt as F
from .context import TIER_RANK, KartContext
from .facts import CornerFacts, SessionFacts


@dataclass
class Finding:
    principle: str
    family: str
    category: str               # catégorie affichée (braking, apex, speed, exit, line, engine, tire, setup…)
    corner: Optional[int]
    headline: str
    fact: str                   # constat chiffré (1re phrase affichée)
    action: str                 # consigne du jour
    check: str = ""             # comment vérifier au prochain relais
    impact_s: float = 0.0       # temps mesuré (s/tour) ; 0 si non chronométrable
    rank_s: float = 0.0         # poids de classement (= impact_s, ou équivalent pour la séance)
    difficulty: str = "moyen"
    min_tier: str = "visitor"
    lever: Optional[str] = None  # levier de style (pour le conseil de style global)
    teaser: Optional[str] = None  # phrase d'aperçu pour un niveau inférieur
    extra: Dict[str, Any] = field(default_factory=dict)

    def gain_txt(self) -> str:
        return f" Gain mesuré : {F.sec(self.impact_s)} par tour." if self.impact_s >= 0.02 else ""


@dataclass
class Ctx:
    tier: str
    session: SessionFacts
    corners: List[CornerFacts]
    kart: Optional[KartContext]
    conditions: Any            # TrackConditions
    voice: F.Voice
    track_temp: Optional[float] = None
    engine_family: Dict[str, Any] = field(default_factory=dict)   # Mon Kart, sinon en-tête du fichier

    def allows(self, tier: str) -> bool:
        return TIER_RANK.get(self.tier, 0) >= TIER_RANK.get(tier, 0)

    @property
    def wet(self) -> bool:
        return getattr(self.conditions, "condition", "dry") in ("wet", "rain", "damp")

    @property
    def allow_attack(self) -> bool:
        return bool(getattr(self.conditions, "allow_brake_later", True))

    @property
    def allow_speed(self) -> bool:
        return bool(getattr(self.conditions, "allow_speed_push", True))


@dataclass
class Principle:
    id: str
    family: str
    title: str
    doctrine: str               # ce que dit le principe, en mots de pilote
    measures: str               # ce qui le déclenche dans les données
    min_tier: str
    scope: str                  # corner | session
    fn: Callable[..., Optional[Finding]]


def _speeds(cf: CornerFacts):
    """(vitesse habituelle, vitesse des meilleurs passages) au point le plus lent, mesurées tour par tour."""
    per = (cf.exits or {}).get("per_lap") or []
    v = sorted([p["min_speed"] for p in per if p.get("min_speed")], reverse=True)
    if len(v) >= 5:
        third = max(2, len(v) // 3)
        return float(np.median(v)), float(np.mean(v[:third]))
    if cf.apex_speed and cf.apex_speed_best and cf.apex_speed_best <= cf.apex_speed * 1.12:
        return cf.apex_speed, cf.apex_speed_best
    return None, None


def exit_gap(cf: CornerFacts):
    """
    (écart, vitesse des meilleures sorties, vitesse habituelle) si la mesure de
    sortie est plausible, sinon None. Une seule sortie très au-dessus des autres
    (dépassement, aspiration, autre trajectoire) ne fait pas une cible.
    """
    s = cf.exits
    if not s:
        return None
    key = s.get("measure") or "exit_near"
    vals = sorted([p[key] for p in s.get("per_lap") or [] if p.get(key) is not None], reverse=True)
    if len(vals) < 5:
        return None
    third = max(2, len(vals) // 3)
    best_mean, med = float(np.mean(vals[:third])), float(np.median(vals))
    gap = best_mean - med
    if gap < 1.5 or gap > max(8.0, 0.10 * med):
        return None
    return gap, best_mean, med


def _lap(cf: CornerFacts) -> str:
    return f" (ton meilleur passage ici : tour {cf.best_lap_here})" if cf.best_lap_here else ""


def _r(c: Dict[str, Any], k: str, d=0.0) -> float:
    v = c.get(k)
    try:
        x = float(v)
        return x if math.isfinite(x) else d
    except (TypeError, ValueError):
        return d


# ═════════════════════════════════════════════════════════════════════════════
# FREINAGE
# ═════════════════════════════════════════════════════════════════════════════

def _is_real_braking(c) -> bool:
    entry = _r(c, "braking_entry_speed")
    dv = _r(c, "braking_delta_v")
    return dv >= max(15.0, 0.25 * entry)


def p_brake_attack(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    c = cf.raw
    if not c.get("has_braking_zone") or c.get("braking_verdict") != "soft" or not x.allow_attack:
        return None
    if not _is_real_braking(c) or cf.time_lost < 0.03:
        return None
    peak, cap = _r(c, "braking_peak_g"), _r(c, "braking_capability_g")
    if cap <= 0 or peak <= 0:
        return None
    entry, vmin = _r(c, "braking_entry_speed"), _r(c, "braking_min_speed")
    point, theo = _r(c, "braking_point_distance"), _r(c, "braking_theoretical_min_m")
    ref = max((o for o in x.corners if o.raw.get("has_braking_zone")),
              key=lambda o: _r(o.raw, "braking_peak_g"), default=None)
    where = f" au virage {ref.id}" if ref and ref.id != cf.id else " ailleurs sur la séance"
    fact = (f"Tu plafonnes à {F.g(peak)} au freinage alors que tu montes à {F.g(cap)}{where}. "
            f"De {F.kmh(entry)} à {F.kmh(vmin)}, il te faut {F.m(theo)} au minimum ; tu en prends {F.m(point)}.")
    action = x.voice.pick("brake_attack", [
        "Mets la pression maxi d'un coup, dès le premier appui, puis relâche progressivement en tournant : "
        "c'est l'attaque qui raccourcit la zone, pas la fin du freinage.",
        "Freine en une fois et franchement, puis dose en relâchant : la force se met au début, le dosage à la fin.",
    ])
    check = (f"Sur la carte, ta zone de freinage doit raccourcir d'environ {F.m(max(2, point - theo))}. "
             "Ensuite seulement, recule ton repère.")
    return Finding("frein_attaque", "freinage", "braking", cf.id,
                   f"freinage trop timide : {F.g(peak)} contre {F.g(cap)}", fact, action, check,
                   impact_s=cf.time_lost, rank_s=cf.time_lost, difficulty="moyen", lever="attaque_frein")


def p_brake_scrub(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    """Virage rapide : un coup de frein de trop casse la vitesse de passage."""
    c = cf.raw
    if not c.get("has_braking_zone") or _is_real_braking(c) or cf.kind not in ("rapide", "moyen"):
        return None
    cur, best = _speeds(cf)
    if not x.allow_speed or cur is None:
        return None
    gap = best - cur
    if gap < max(1.5, 0.025 * cur) or cf.time_lost < 0.03:
        return None
    entry, dv = _r(c, "braking_entry_speed"), _r(c, "braking_delta_v")
    fact = (f"Tu freines de {F.kmh(entry)} à {F.kmh(entry - dv)} et tu passes à {F.kmh(cur)} au point le plus lent ; "
            f"tes meilleurs passages gardent {F.kmh(best)}.")
    action = x.voice.pick("brake_scrub", [
        "Ici, un effleurement de frein suffit pour charger l'avant : garde les gaz, pose le kart, "
        "et laisse-le rouler jusqu'à la corde.",
        "Ce virage se passe pied droit presque à fond : un léger appui du pied gauche pour placer le kart, "
        "sans couper les gaz, et le moteur reste dans les tours.",
    ])
    f = Finding("frein_effleurement", "freinage", "speed", cf.id,
                f"un effleurement suffit : {F.kmh(gap, 1)} de vitesse à garder", fact, action,
                f"Repère : vise {F.kmh(best)} au point le plus lent.",
                impact_s=cf.time_lost, rank_s=cf.time_lost, difficulty="difficile", lever="pied_constant")
    return f


def p_brake_point(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    c = cf.raw
    v = c.get("braking_verdict")
    if not c.get("has_braking_zone") or v not in ("brake_later", "brake_earlier"):
        return None
    delta, point, best = _r(c, "braking_delta"), _r(c, "braking_point_distance"), _r(c, "braking_best_point_m")
    best_lap = c.get("braking_best_lap")
    vmin = _r(c, "braking_min_speed")
    if abs(delta) < 3 or abs(delta) > 22 or point < 6 or best < 6 or cf.time_lost < 0.03:
        return None  # écart trop faible, ou trop grand pour être le même freinage
    ref = f" sur ton tour {best_lap}" if best_lap else ""
    if v == "brake_later":
        if not x.allow_attack:
            return None
        fact = (f"Tu déclenches à {F.m(point)} de la corde ; tu as déjà freiné à {F.m(best)}{ref}, "
                f"pour la même vitesse au point de corde ({F.kmh(vmin)}).")
        action = x.voice.pick("brake_later", [
            f"Prends un repère fixe (panneau, poteau, marque au sol) et avance-le de {F.m(delta)}, par paliers de 2 à 3 m.",
            f"Avance ton repère de freinage de {F.m(delta)} en deux ou trois relais : tu l'as déjà fait, ce n'est pas un risque.",
        ])
        check = "Si le kart ne veut plus tourner ou que tu élargis en sortie, reviens d'un palier."
        head = f"tu freines {F.m(delta)} plus tôt que ton meilleur passage"
        lever, diff = "repere_freinage", "facile"
    else:
        fact = (f"Tu déclenches à {F.m(point)} de la corde, mais ton passage le plus rapide ici freinait à "
                f"{F.m(best)}{ref} : plus tôt, et pourtant plus vite sur la portion.")
        action = x.voice.pick("brake_earlier", [
            "Freine un peu avant et rends les freins avant de tourner : le kart arrive à plat à la corde "
            "et la relance part plus tôt.",
            "Recule ton repère et finis ton freinage roues presque droites : un kart encore freiné en "
            "plein virage glisse, et la sortie se paie sur toute la ligne droite.",
        ])
        check = "Repère : la vitesse en sortie doit monter, même si l'entrée te semble plus lente."
        head = f"ton meilleur passage freinait {F.m(abs(delta))} plus tôt"
        lever, diff = "entree_calme", "moyen"
    return Finding("frein_point", "freinage", "braking", cf.id, head, fact, action, check,
                   impact_s=cf.time_lost, rank_s=cf.time_lost, difficulty=diff, lever=lever)


def p_brake_consistency(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    c = cf.raw
    if not c.get("has_braking_zone") or c.get("braking_verdict") != "inconsistent" or cf.time_lost < 0.03:
        return None
    spread = _r(c, "braking_consistency_m")
    fact = f"D'un tour à l'autre, ton point de freinage bouge de ± {F.m(spread)} ; un pilote confirmé tient 2 à 3 m."
    action = x.voice.pick("brake_consistency", [
        "Choisis UN repère visuel au bord de la piste et garde-le toute la séance : la régularité vient avant la performance.",
        "Freine toujours au même endroit, même si ce n'est pas le plus tard : ton cerveau a besoin d'un repère fixe "
        "pour pouvoir le déplacer ensuite.",
    ])
    return Finding("frein_regularite", "freinage", "braking", cf.id,
                   f"point de freinage instable (± {F.m(spread)})", fact, action,
                   "Repère : sur la carte, tes points de freinage doivent se regrouper.",
                   impact_s=cf.time_lost, rank_s=cf.time_lost * 0.9, difficulty="facile", lever="repere_freinage")


def p_double_brake(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    c = cf.raw
    n = int(_r(c, "double_brake_laps"))
    laps = len(x.session.laps_used) or 1
    if n < max(2, laps // 3) or cf.time_lost < 0.03:
        return None
    fact = f"Sur {n} tours sur {laps}, tu freines en deux fois avant ce virage."
    action = ("Un seul appui franc, puis relâche progressivement : chaque reprise de frein recharge l'avant, "
              "fait sautiller le kart et casse l'élan.")
    return Finding("frein_double", "freinage", "braking", cf.id, f"double freinage sur {n} tours", fact, action,
                   impact_s=cf.time_lost, rank_s=cf.time_lost * 0.95, difficulty="facile", lever="attaque_frein")


# ═════════════════════════════════════════════════════════════════════════════
# ENTRÉE ET MILIEU DE VIRAGE
# ═════════════════════════════════════════════════════════════════════════════

def p_dead_time(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    """
    Roue libre : gaz coupés, ni frein ni accélération.

    Les durées citées sont celles du module de freinage (mêmes chiffres que la
    carte). La mesure de phase sert à trancher : si le kart reste en appui sans
    décélérer, ce n'est pas une roue libre mais un kart qui force (autre principe).
    """
    c = cf.raw
    ph = cf.phase or {}
    if ph.get("neutral_ax") is not None and ph["neutral_ax"] > -0.06 and ph.get("neutral_lat") and ph.get("peak_lat") \
            and ph["neutral_lat"] >= 0.75 * ph["peak_lat"]:
        return None
    coast, best = _r(c, "coasting_s"), _r(c, "coasting_best_s")
    best_lap = c.get("braking_best_lap")
    if c.get("has_braking_zone") and c.get("braking_verdict") == "coasting" and coast > 0:
        pass
    elif ph.get("neutral_s") is not None and ph["neutral_s"] >= 0.45 and ph["neutral_s"] - ph["best_s"] >= 0.25 \
            and (ph.get("neutral_ax") or 0) <= -0.06:
        coast, best, best_lap = ph["neutral_s"], ph["best_s"], ph["best_lap"]
    else:
        return None
    if cf.time_lost < 0.03 or coast - best < 0.2:
        return None
    ref = f" sur ton tour {best_lap}" if best_lap else " sur ton passage le plus rapide"
    fact = (f"Entre le relâcher du frein et la remise des gaz, tu roules {F.sec(coast)} en roue libre, "
            f"contre {F.sec(best)}{ref}.")
    action = x.voice.pick("dead_time", [
        "Enchaîne frein et gaz sans palier : relâche le frein en tournant et reprends les gaz dès que le kart "
        "pointe vers la corde, même à moitié.",
        "Ne laisse pas le kart rouler sur son élan : dès la fin du freinage, un filet de gaz pour le garder "
        "chargé, puis plein gaz à la corde.",
    ])
    return Finding("temps_mort", "entree", "braking", cf.id,
                   f"{F.sec(coast)} sans frein ni gaz", fact, action,
                   "Repère : le temps entre frein et gaz doit approcher celui de ton meilleur tour.",
                   impact_s=cf.time_lost, rank_s=cf.time_lost, difficulty="moyen", lever="temps_mort")


def p_kart_scrub(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    """Kart en appui qui ne repart pas : le châssis force sur le moteur."""
    ph = cf.phase
    if not ph or ph.get("neutral_s") is None or ph.get("neutral_lat") is None or not ph.get("peak_lat"):
        return None
    if ph["neutral_s"] < 0.5 or (ph.get("neutral_ax") or 0) <= -0.06:
        return None
    if ph["neutral_lat"] < 0.75 * ph["peak_lat"] or ph["neutral_s"] - ph["best_s"] < 0.2:
        return None
    if cf.time_lost < 0.03:
        return None
    fact = (f"Pendant {F.sec(ph['neutral_s'])}, le kart reste sous {F.g(ph['neutral_lat'])} d'appui sans reprendre "
            f"de vitesse (contre {F.sec(ph['best_s'])} sur ton tour {ph['best_lap']}) : ce n'est pas un temps mort, "
            "c'est le châssis qui force sur le moteur.")
    action = x.voice.pick("kart_scrub", [
        "Braque moins et plus tard, puis ouvre les mains dès la corde : un kart qui frotte en appui retient le "
        "moteur. Laisse-le courir un peu plus large en sortie.",
        "Arrondis : un seul mouvement de volant, sans en rajouter au milieu. Si le kart « colle », c'est que tu "
        "le forces à tourner plus serré qu'il ne veut.",
    ])
    extra = ""
    if x.allows("racer") and x.kart and x.kart.track_rear_mm:
        extra = (f" Si ça frotte dans plusieurs virages, élargis la voie arrière de 10 mm "
                 f"({F.num(x.kart.track_rear_mm)} → {F.num(x.kart.track_rear_mm + 10)} mm) pour libérer l'arrière.")
    return Finding("kart_force", "entree", "line", cf.id,
                   "le kart frotte en appui et retient le moteur", fact, action + extra,
                   "Repère : la vitesse doit remonter plus tôt après le point le plus lent.",
                   impact_s=cf.time_lost, rank_s=cf.time_lost, difficulty="moyen", lever="braquer_moins",
                   teaser="Le réglage qui libère ton kart quand il frotte en appui")


def p_apex(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    if cf.apex_error_m < 1.0 or cf.time_lost < 0.03:
        return None
    shift = None
    if cf.exits and cf.exits.get("per_lap"):
        shifts = [p.get("apex_shift_m") for p in cf.exits["per_lap"] if p.get("apex_shift_m") is not None]
        shift = float(np.median(shifts)) if shifts else None
    when = ""
    if shift is not None and shift <= -3:
        when = f" Ton point le plus lent arrive {F.m(-shift)} avant la corde : tu tournes trop tôt."
    elif shift is not None and shift >= 4:
        when = f" Ton point le plus lent arrive {F.m(shift)} après la corde."
    fact = f"Ton point de corde est décalé de {F.m(cf.apex_error_m, 1)} par rapport à la corde du virage.{when}"
    by_kind = {
        "epingle": [
            "Épingle : corde tardive. Freine droit, pivote en fin de freinage, et vise le dernier tiers de "
            "l'intérieur : tu ressors en V, roues droites plus tôt.",
            "Dans une épingle, c'est la sortie qui compte : retarde ton braquage et va chercher la corde tard, "
            "pour remettre les gaz kart déjà redressé.",
        ],
        "lent": [
            "Regarde la corde AVANT de braquer : la trajectoire suit le regard. Un seul mouvement de volant.",
            "Retarde un peu ton braquage et vise la corde du regard : un kart bien placé ouvre le volant plus tôt.",
        ],
        "moyen": [
            "Un seul mouvement de volant, fluide, regard sur la corde avant de braquer : la corde propre "
            "allonge la phase d'accélération.",
            "Place-toi bien à l'extérieur à l'entrée, puis vise la corde en une rotation : pas de correction au milieu.",
        ],
        "rapide": [
            "Virage rapide : la corde se vise de loin. Le kart doit lécher l'intérieur sans monter le vibreur, "
            "pied constant.",
            "Dans un virage rapide, regarde la corde dès l'entrée et garde un rayon constant : chaque correction coûte de la vitesse.",
        ],
    }
    action = x.voice.pick(f"apex_{cf.kind}", by_kind.get(cf.kind, by_kind["moyen"]))
    if x.wet:
        action = ("Sous la pluie, sors de la trajectoire sèche : la gomme déposée glisse. Tourne un peu plus tôt, "
                  "plus large, et cherche le grip là où la piste est encore rugueuse.")
    head = (f"{cf.kind_fr} : point de corde manqué de {F.m(cf.apex_error_m, 1)}"
            if x.allows("rookie") and cf.kind_source == "circuit" else
            f"point de corde manqué de {F.m(cf.apex_error_m, 1)}")
    return Finding("corde", "trajectoire", "apex", cf.id, head, fact, action,
                   "Repère : sur la carte, ta trajectoire doit toucher la corde au bon endroit.",
                   impact_s=cf.time_lost, rank_s=cf.time_lost, difficulty="moyen",
                   lever="corde_tardive" if cf.kind == "epingle" else "regard_corde")


def p_corner_speed(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    cur, best = _speeds(cf)
    if not x.allow_speed or cur is None:
        return None
    gap = best - cur
    if gap < max(1.5, 0.025 * cur) or gap > max(8.0, 0.12 * cur) or cf.time_lost < 0.03:
        return None
    trail = _r(cf.raw, "trail_braking_ratio", -1)
    fact = (f"Au point le plus lent, tu passes à {F.kmh(cur)} ; sur tes meilleurs passages, "
            f"{F.kmh(best)}. Cette vitesse, tu l'as déjà faite.")
    if cf.kind in ("epingle", "lent"):
        if 0 <= trail < 0.2:
            action = ("Tu finis de freiner roues droites puis tu tournes. Garde un peu de frein en inscrivant "
                      "et relâche progressivement jusqu'à la corde : l'avant reste chargé et le kart pivote sans perdre de vitesse.")
        else:
            action = x.voice.pick("speed_slow", [
                "Relâche le frein un peu plus tôt : le kart doit ROULER à la corde, pas y arriver encore freiné.",
                "Lâche les freins plus tôt et laisse le kart glisser jusqu'à la corde : un kart qui roule passe plus vite qu'un kart qui freine.",
            ])
        lever = "lacher_frein"
    elif cf.kind == "rapide":
        action = x.voice.pick("speed_fast", [
            "Sur un virage rapide, la perte vient presque toujours d'un lever de pied de sécurité. Vise la corde du regard et garde le pied constant.",
            "Fais confiance au grip : pied constant, volant immobile. Le moindre lever charge l'avant et casse la vitesse.",
        ])
        lever = "pied_constant"
    else:
        action = x.voice.pick("speed_mid", [
            "Élargis ton entrée pour ouvrir le rayon : tu pourras passer plus vite à la corde sans élargir en sortie.",
            "Entre plus à l'extérieur et dessine un rayon plus grand : plus le rayon est grand, plus tu passes vite.",
        ])
        lever = "elan"
    return Finding("vitesse_corde", "trajectoire", "speed", cf.id,
                   f"{F.kmh(gap, 1)} à reprendre au point de corde", fact, action,
                   f"Repère : vise {F.kmh(best)} au point le plus lent au prochain relais.",
                   impact_s=cf.time_lost, rank_s=cf.time_lost, difficulty="difficile" if cf.kind == "rapide" else "moyen",
                   lever=lever)


# ═════════════════════════════════════════════════════════════════════════════
# SORTIE ET RELANCE
# ═════════════════════════════════════════════════════════════════════════════

def _lever(lv, k, thr):
    L = (lv or {}).get(k)
    return L if L and abs(L["diff"]) >= thr and (L["rho"] is None or abs(L["rho"]) >= 0.35) else None


def p_exit(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    s = cf.exits
    if not s:
        return None
    gain = s.get("relance_gain_s")
    if gain is None or gain < 0.03:
        return None
    eg = exit_gap(cf)
    if eg is None:
        return None
    gap, best_mean, med = eg
    lv = s.get("levers") or {}
    reasons, actions, levers = [], [], []
    e = _lever(lv, "entry_speed", 1.5)
    if e and e["diff"] < 0:
        reasons.append(f"tu entrais {F.kmh(-e['diff'])} moins vite")
        actions.append(x.voice.pick("exit_entry", [
            "Rentre un peu moins fort : le kart reste à plat au lieu de glisser ou de se cabrer, le châssis ne freine "
            "plus le moteur et la relance arrive plus tôt",
            "Calme l'entrée : un kart posé à plat à la corde relance mieux qu'un kart qui arrive trop vite et glisse",
        ]))
        levers.append("entree_calme")
    a = _lever(lv, "apex_shift_m", 3.0)
    if a and a["diff"] > 0:
        reasons.append(f"ton point le plus lent arrivait {F.m(a['diff'])} plus loin")
        actions.append(x.voice.pick("exit_late", [
            "Attends un peu avant de tourner et enroule jusqu'à la corde : tu redresses plus tôt et tu remets les gaz roues droites",
            "Corde plus tardive : tourne un temps plus tard, enroule, et tu sors avec le volant déjà ouvert",
            "Retarde ton point de braquage : la corde plus tardive t'ouvre la sortie et tu accélères kart droit",
        ]))
        levers.append("enrouler")
    elif a and a["diff"] < 0:
        reasons.append(f"ton point le plus lent arrivait {F.m(-a['diff'])} plus tôt")
        actions.append("Ici, tourner plus tôt te réussit : la corde plus avancée t'ouvre la sortie")
        levers.append("corde_avancee")
    mn = _lever(lv, "min_speed", 2.0)
    # Un écart de vitesse énorme au point le plus lent, c'est une autre trajectoire
    # (dépassement, erreur), pas un geste à reproduire.
    if mn and abs(mn["diff"]) > 0.18 * max(1.0, mn["worst"]):
        mn = None
    if mn and mn["diff"] > 0:
        reasons.append(f"tu gardais {F.kmh(mn['diff'])} de plus au point le plus lent")
        actions.append(x.voice.pick("exit_carry", [
            "Garde de l'élan dans le virage plutôt que de casser la vitesse : enroule, le moteur repart de plus haut",
            "Ne casse pas toute ta vitesse : un virage plus rond, le moteur repart de plus haut",
        ]))
        levers.append("elan")
    elif mn and mn["diff"] < 0 and not e:
        reasons.append(f"tu sacrifiais {F.kmh(-mn['diff'])} au point le plus lent")
        actions.append(x.voice.pick("exit_sacrifice", [
            "Ralentis franchement pour pivoter, puis redresse et accélère tôt : ici, sacrifier un peu de vitesse au "
            "point de corde paie en sortie",
            "Freine un peu plus fort et fais pivoter le kart : en V, tu remets les gaz plus tôt et plus longtemps",
        ]))
        levers.append("sacrifier")
    gl = _lever(lv, "lat_g", 0.08)
    if gl and gl["diff"] < 0:
        reasons.append(f"le kart prenait {F.g(-gl['diff'])} d'appui latéral en moins")
        actions.append("Braque moins et plus doucement : un kart qui frotte ou qui saute perd sa vitesse")
        levers.append("braquer_moins")
    r = _lever(lv, "rpm_min", 200)
    if r and r["diff"] > 0:
        reasons.append(f"le moteur restait {F.rpm(r['diff'])} plus haut ({F.rpm(r['best'])} contre {F.rpm(r['worst'])})")
        if not actions:
            actions.append("Ne laisse pas le régime s'écrouler au point le plus lent : c'est lui qui fait la relance")
        levers.append("regime")
    eng = x.session.engine
    if (x.allows("rookie") and eng and cf.rpm_min and cf.rpm_min < eng.knee_rpm - 300
            and "regime" in levers):
        actions.append(f"Ton moteur tombe à {F.rpm(cf.rpm_min)}, sous sa plage (il pousse vraiment à partir de "
                       f"{F.rpm(eng.knee_rpm)}) : c'est ce régime-là qu'il faut garder")
    dist = int(s.get("distance_m") or 40)
    fact = (f"{dist} m après le point le plus lent, tu ressors à {F.kmh(med)} en moyenne, et à {F.kmh(best_mean)} "
            f"sur tes meilleures sorties (dont le tour {s.get('exit_best_lap')}).")
    if reasons:
        fact += f" Sur ces sorties, {', '.join(reasons[:2])}."
        action = ". ".join(actions[:2] + actions[-1:] if len(actions) > 2 and "sous sa plage" in actions[-1] else actions[:2]) + "."
    else:
        action = ("Rien ne distingue nettement tes entrées : reprends les repères de ton tour "
                  f"{s.get('exit_best_lap')} (point de braquage, moment où tu remets les gaz).")
    if x.allows("rookie") and cf.opens_longest_straight and x.session.longest_straight_m:
        action += (f" C'est le virage qui ouvre ta plus longue ligne droite (environ "
                   f"{F.m(round(x.session.longest_straight_m, -1))}) : chaque km/h gagné ici se garde jusqu'au freinage suivant.")
    if x.wet:
        action += " Sous la pluie, remets les gaz progressivement, kart droit : la relance se gagne sans glisse."
    out = Finding("sortie", "sortie", "exit", cf.id,
                  f"ta relance : {F.kmh(gap, 1)} de plus à aller chercher en sortie", fact, action,
                  f"Repère : {dist} m après le point le plus lent, vise {F.kmh(best_mean)}.",
                  impact_s=round(gain, 3), rank_s=gain * (1.15 if cf.opens_longest_straight else 1.0),
                  difficulty="moyen", lever=levers[0] if levers else None)
    out.extra["levers"] = levers
    return out


def p_engine_band(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    """Moteur qui tombe sous sa plage au point le plus lent."""
    eng = x.session.engine
    if not eng or cf.rpm_min is None or cf.kind not in ("epingle", "lent", "moyen"):
        return None
    if cf.rpm_min > eng.knee_rpm - 300:
        return None
    # Atteignable : ses meilleures sorties gardaient déjà le moteur plus haut.
    if cf.rpm_min_best is None or cf.rpm_min_best < cf.rpm_min + 200:
        return None
    # Le temps annoncé est celui de la relance, mesuré seulement si la sortie l'est.
    if exit_gap(cf) is None:
        return None
    loss = float((cf.exits or {}).get("relance_gain_s") or 0.0)
    if loss < 0.03:
        return None
    low_g = float(np.interp(cf.rpm_min, [b["rpm"] for b in eng.bins], [b["g"] for b in eng.bins]))
    drop = max(0.0, 1.0 - low_g / eng.peak_g) * 100 if eng.peak_g > 0 else 0
    if drop < 12:
        return None
    fam = (x.kart.engine.get("label") if x.kart and x.kart.engine and x.allows("racer") else None)
    fam = f"ton {fam}" if fam else "ton moteur"
    fact = (f"Au point le plus lent, {fam} tombe à {F.rpm(cf.rpm_min)} en moyenne, contre {F.rpm(cf.rpm_min_best)} "
            f"sur tes meilleures sorties. Mesuré sur tes relances, il pousse {F.num(drop)} % moins fort qu'à partir de "
            f"{F.rpm(eng.knee_rpm)}.")
    action = x.voice.pick("engine_band", [
        f"Garde de l'élan : un virage plus rond et une corde un peu plus tardive pour ne pas descendre sous {F.rpm(eng.knee_rpm)}.",
        f"Ne casse pas toute ta vitesse ici : chaque tour/minute sous {F.rpm(eng.knee_rpm)} se paie en sortie.",
    ])
    return Finding("moteur_plage", "moteur", "engine", cf.id,
                   f"moteur sous sa plage ({F.rpm(cf.rpm_min)})", fact, action,
                   f"Repère : au point le plus lent, vise plus de {F.rpm(eng.knee_rpm)} sur le compte-tours.",
                   impact_s=round(loss, 3), rank_s=loss * 0.9, difficulty="moyen", min_tier="rookie", lever="regime",
                   teaser="Combien de dents changer pour garder ton moteur dans sa plage")


def p_chain(cf: CornerFacts, x: Ctx) -> Optional[Finding]:
    """Enchaînement : sacrifier le premier virage pour le second."""
    if cf.to_next_m is None or cf.to_next_m > 55:
        return None
    nxt = next((o for o in x.corners if o.pos_m > cf.pos_m and o.id != cf.id), None)
    if nxt is None or nxt.time_lost < 0.05 or nxt.time_lost <= cf.time_lost:
        return None
    if (nxt.straight_after_m or 0) < 80 or (cf.straight_after_m or 0) >= (nxt.straight_after_m or 0):
        return None
    cur, best = _speeds(cf)
    if cur is None or cur < best - 1.0:
        return None
    fact = (f"Les virages {cf.id} et {nxt.id} s'enchaînent sur {F.m(cf.to_next_m)}. Tu soignes le {cf.id} "
            f"({F.kmh(cur)} au point le plus lent, au niveau de tes meilleurs passages) mais tu perds {F.sec(nxt.time_lost)} au {nxt.id}, "
            f"celui qui lance la ligne droite.")
    action = (f"Sacrifie le {cf.id} : entre un peu plus lentement et reste au milieu de la piste pour arriver bien "
              f"placé à l'extérieur du {nxt.id}. C'est sa sortie qui compte.")
    return Finding("enchainement", "trajectoire", "line", nxt.id,
                   f"enchaînement {cf.id}-{nxt.id} : sacrifie le {cf.id} pour le {nxt.id}", fact, action,
                   f"Repère : la vitesse en sortie du {nxt.id} doit monter, même si le {cf.id} paraît plus lent.",
                   impact_s=nxt.time_lost, rank_s=nxt.time_lost * 0.95, difficulty="difficile", min_tier="rookie",
                   lever="sacrifier")


CORNER_PRINCIPLES = [
    Principle("frein_attaque", "freinage", "Attaque de frein",
              "La force se met au début du freinage, le dosage à la fin. Un freinage mou allonge la zone et empêche de retarder le point.",
              "Décélération maxi du virage < 82 % de la meilleure décélération de la séance, sur un vrai freinage (≥ 15 km/h et ≥ 25 % de la vitesse).",
              "visitor", "corner", p_brake_attack),
    Principle("frein_effleurement", "freinage", "Effleurement de frein en virage rapide",
              "Un virage rapide se place d'un effleurement de frein, gaz ouverts : un vrai freinage y casse la vitesse.",
              "Freinage léger (< 25 % de la vitesse) et vitesse de corde en dessous des meilleurs passages.",
              "visitor", "corner", p_brake_scrub),
    Principle("frein_point", "freinage", "Point de freinage",
              "On ne retarde un freinage qu'après l'avoir fait plus fort ; et on reproduit le repère de son passage le plus rapide.",
              "Écart de 3 à 22 m entre le point habituel et celui du passage le plus rapide.",
              "visitor", "corner", p_brake_point),
    Principle("frein_regularite", "freinage", "Repère de freinage fixe",
              "Un repère fixe avant tout : on ne peut déplacer qu'un repère qu'on tient.",
              "Dispersion du point de freinage ≥ 6 m d'un tour à l'autre.",
              "visitor", "corner", p_brake_consistency),
    Principle("frein_double", "freinage", "Un seul appui",
              "Freiner en deux fois recharge l'avant et fait sautiller le kart.",
              "Deux freinages détectés avant le même virage sur au moins un tiers des tours.",
              "visitor", "corner", p_double_brake),
    Principle("temps_mort", "entree", "Pas de roue libre",
              "Un kart n'a pas de transfert de masse à attendre : frein puis gaz, sans palier.",
              "Phase sans frein ni gaz (décélération ≈ frein moteur) plus longue de 0,25 s que sur le meilleur passage.",
              "visitor", "corner", p_dead_time),
    Principle("kart_force", "entree", "Kart à plat, châssis qui force",
              "Un kart qu'on force à tourner frotte et retient le moteur : moins de braquage, plus d'élan.",
              "Vitesse qui stagne sous un appui latéral ≥ 75 % du maximum, plus longtemps que sur le meilleur passage.",
              "visitor", "corner", p_kart_scrub),
    Principle("corde", "trajectoire", "Corde selon le type de virage",
              "Épingle : corde tardive et sortie en V. Moyen : une rotation fluide. Rapide : corde visée de loin, rayon constant.",
              "Écart de corde ≥ 1 m ; type de virage lu dans la base circuits, sinon mesuré (angle, vitesse).",
              "visitor", "corner", p_apex),
    Principle("vitesse_corde", "trajectoire", "Vitesse de passage",
              "Lent : relâcher le frein en inscrivant. Moyen : ouvrir le rayon. Rapide : pied constant.",
              "Vitesse à la corde ≥ 2,5 % sous les meilleurs passages, avec du temps perdu mesuré.",
              "visitor", "corner", p_corner_speed),
    Principle("sortie", "sortie", "Sortie et relance",
              "Corde tardive, enrouler, kart à plat, entrée plus calme, élan : ce qui fait les meilleures sorties du pilote.",
              "Comparaison des meilleures sorties aux sorties habituelles (vitesse 40 ou 80 m après le point le plus lent).",
              "visitor", "corner", p_exit),
    Principle("moteur_plage", "moteur", "Rester dans la plage du moteur",
              "Le moteur relance d'autant mieux qu'il repart de haut : ne pas le laisser s'écrouler au point le plus lent.",
              "Régime au point le plus lent < régime où le moteur pousse à 85 % de son maximum (courbe mesurée sur les relances).",
              "rookie", "corner", p_engine_band),
    Principle("enchainement", "trajectoire", "Enchaînements",
              "Dans un enchaînement, on sacrifie le virage qui ne mène nulle part pour soigner celui qui lance la ligne droite.",
              "Deux virages à moins de 55 m, perte sur le second, plus longue ligne droite après le second.",
              "rookie", "corner", p_chain),
]


# ═════════════════════════════════════════════════════════════════════════════
# SÉANCE : MOTEUR, PNEUS, RÉGLAGE, RÉGULARITÉ
# ═════════════════════════════════════════════════════════════════════════════

def p_water(x: Ctx) -> Optional[Finding]:
    s = x.session
    if not s.water_by_lap or x.engine_family.get("cooling") == "air":
        return None
    laps = sorted(s.water_by_lap)
    w = [s.water_by_lap[k] for k in laps]
    cold = [k for k, v in zip(laps, w) if v < 48]
    hot = [k for k, v in zip(laps, w) if v > 64]
    eng = x.kart.engine.get("label") if (x.kart and x.kart.engine and x.allows("racer")) else None
    pour = f"Pour ton {eng}, m" if eng else "M"
    if len(cold) >= 3:
        fact = (f"Ton eau reste sous 48 °C pendant {len(cold)} tours ({F.deg(w[0])} au tour {laps[0]}, "
                f"{F.deg(max(w))} au plus haut). Un 2-temps à eau donne sa pleine puissance vers 50-60 °C.")
        action = (f"{pour}asque environ un tiers du radiateur (volet ou adhésif) au départ, et découvre-le dès que "
                  "l'eau passe 55 °C. Sur piste froide, garde-le masqué toute la séance.")
        head = f"moteur trop froid : eau sous 48 °C pendant {len(cold)} tours"
        rank = 0.07 + 0.01 * len(cold)
    elif len(hot) >= 3:
        fact = (f"Ton eau dépasse 64 °C pendant {len(hot)} tours ({F.deg(max(w))} au plus haut). "
                "Au-delà de 60-62 °C, un 2-temps à eau perd de la puissance et le piston souffre.")
        action = ("Pour ton " + eng + ", d" if eng else "D") + "écouvre davantage le radiateur ou ouvre le volet : vise 55-60 °C en fin de séance."
        head = f"moteur trop chaud : {F.deg(max(w))}"
        rank = 0.06 + 0.01 * len(hot)
    else:
        return None
    return Finding("eau", "moteur", "engine", None, head, fact, action,
                   "Repère : lis la température d'eau sur ton boîtier au 3e tour.",
                   impact_s=0.0, rank_s=rank, difficulty="facile", min_tier="rookie")


def _pressure_line(x: Ctx, delta: float) -> str:
    k = x.kart
    if not (x.allows("racer") and k and (k.cold_front or k.cold_rear)):
        return ""
    f0, r0 = k.cold_front, k.cold_rear
    parts = []
    if f0:
        parts.append(f"avant {F.bar(f0)} → {F.bar(f0 + delta)}")
    if r0:
        parts.append(f"arrière {F.bar(r0)} → {F.bar(r0 + delta)}")
    tire = f" sur tes {k.tire['name']}" if k.tire else ""
    return f" Pressions à froid{tire} : " + ", ".join(parts) + "."


def p_tire_warmup(x: Ctx) -> Optional[Finding]:
    s = x.session
    n = s.grip_warmup_laps
    if n is None or n < 3 or len(s.grip_by_lap) < 6:
        return None
    laps = sorted(s.grip_by_lap)
    g0 = s.grip_by_lap[laps[0]]
    plateau = float(np.median(sorted(s.grip_by_lap.values())[-max(3, len(laps) // 2):]))
    if g0 >= 0.93 * plateau:
        return None
    temp = f" sur une piste à {F.deg(x.track_temp)}" if x.track_temp is not None else ""
    fact = (f"Tes pneus mettent {n} tours à atteindre leur adhérence maximale{temp} : {F.g(g0)} d'appui latéral au "
            f"tour {laps[0]}, {F.g(plateau)} une fois chauds.")
    action = ("Au tour de lancement, freine fort et accélère fort en ligne droite pour charger les pneus, et "
              "n'attaque vraiment qu'une fois l'appui revenu.")
    k = x.kart
    racer_line = ""
    if x.allows("racer") and k and k.tire and (k.cold_front or k.cold_rear):
        rng = (k.tire.get("cold") or {}).get("dry")
        cur = k.cold_rear or k.cold_front
        if rng and cur is not None and cur + 0.03 <= rng[1] + 1e-6:
            racer_line = (" Monte aussi de 0,03 bar à froid, en restant dans la plage de ta gomme "
                          f"({F.num(rng[0], 2)} à {F.bar(rng[1])})." + _pressure_line(x, 0.03))
    return Finding("pneus_chauffe", "pneus", "tire", None,
                   f"pneus longs à chauffer : {n} tours", fact, action + racer_line,
                   "Repère : ton 2e tour doit déjà être à moins de 0,3 s de ton meilleur.",
                   impact_s=0.0, rank_s=0.05 + 0.01 * n, difficulty="facile", min_tier="rookie",
                   teaser="La pression à froid exacte pour tes pneus et ta piste")


def p_tire_fade(x: Ctx) -> Optional[Finding]:
    s = x.session
    if s.grip_fade_pct is None or s.grip_fade_pct < 3.5 or len(s.grip_by_lap) < 8:
        return None
    fact = (f"Ton adhérence baisse de {F.num(s.grip_fade_pct, 1)} % sur les trois derniers tours par rapport à ton "
            "meilleur niveau de la séance.")
    action = ("Pneus qui surchauffent ou qui s'usent : roule plus rond (moins de glisse en entrée), et garde ton "
              "attaque pour les premiers tours chauds.")
    racer = _pressure_line(x, -0.03)
    if racer:
        action += " Baisse de 0,03 bar à froid pour limiter la montée en pression." + racer
    return Finding("pneus_chute", "pneus", "tire", None,
                   f"adhérence en baisse en fin de séance (−{F.num(s.grip_fade_pct, 1)} %)", fact, action,
                   impact_s=0.0, rank_s=0.04 + 0.005 * s.grip_fade_pct, difficulty="moyen", min_tier="rookie",
                   teaser="L'ajustement de pression qui tient ton grip jusqu'au bout")


def p_pressures(x: Ctx) -> Optional[Finding]:
    k = x.kart
    if not (x.allows("racer") and k and k.tire and (k.cold_front or k.cold_rear)):
        return None
    cond = getattr(x.conditions, "condition", "dry")
    key = {"dry": "dry", "damp": "damp", "wet": "wet", "rain": "wet"}.get(cond, "dry")
    rng = (k.tire.get("cold") or {}).get(key)
    if not rng:
        if key != "dry" and (k.tire.get("compound") != "wet"):
            return Finding("pression", "pneus", "setup", None, "pneus slicks sur piste mouillée",
                           f"Tes {k.tire['name']} sont des slicks et la piste est {getattr(x.conditions, 'label', 'mouillée').lower()}.",
                           "Monte un train pluie, ou au minimum remonte nettement les pressions pour chauffer la gomme.",
                           rank_s=0.09, difficulty="facile", min_tier="racer")
        return None
    lo, hi = float(rng[0]), float(rng[1])
    cur = [v for v in (k.cold_front, k.cold_rear) if v]
    avg = float(np.mean(cur))
    hot_txt = ""
    if k.tire.get("hot") and (k.hot_front or k.hot_rear):
        h = float(np.mean([v for v in (k.hot_front, k.hot_rear) if v]))
        hlo, hhi = k.tire["hot"]
        if h > hhi + 0.02:
            hot_txt = f" À chaud, tu relèves {F.bar(h)} pour une cible de {F.num(hlo, 2)} à {F.bar(hhi)} : baisse à froid de {F.bar(h - hhi)}."
        elif h < hlo - 0.02:
            hot_txt = f" À chaud, tu relèves {F.bar(h)} pour une cible de {F.num(hlo, 2)} à {F.bar(hhi)} : monte à froid de {F.bar(hlo - h)}."
    if lo - 0.01 <= avg <= hi + 0.01 and not hot_txt:
        return None
    if avg > hi:
        d = round(hi - avg, 2)
        head = f"pressions trop hautes pour tes {k.tire['name']}"
    elif avg < lo:
        d = round(lo - avg, 2)
        head = f"pressions trop basses pour tes {k.tire['name']}"
    else:
        d = 0.0
        head = f"pressions à chaud hors cible ({k.tire['name']})"
    fact = (f"Tu pars à {F.bar(avg)} à froid ; la plage de ta gomme ({k.tire.get('compound') or 'slick'}) sur piste "
            f"{getattr(x.conditions, 'label', 'sèche').lower()} est de {F.num(lo, 2)} à {F.bar(hi)} ({k.tire.get('source')}).{hot_txt}")
    action = ("Recale-toi dans la plage avant le prochain relais." + (_pressure_line(x, d) if d else "")
              + " Mesure à froid, pneus à l'ombre, avec le même manomètre.")
    return Finding("pression", "pneus", "setup", None, head, fact, action,
                   rank_s=0.08, difficulty="facile", min_tier="racer")


def p_gearing(x: Ctx) -> Optional[Finding]:
    eng = x.session.engine
    if not eng:
        return None
    low = [c for c in x.corners if c.rpm_min is not None and c.rpm_min < eng.knee_rpm - 300
           and c.kind in ("epingle", "lent", "moyen")]
    k = x.kart
    r = k.sprocket_rear if k else None
    pig = k.sprocket_front if k else None
    fam_top = x.engine_family.get("top")
    if eng.top_plateau_s >= 0.45:
        fact = (f"En bout de ligne droite, ton moteur reste collé à {F.rpm(eng.top_rpm)} sans accélérer pendant "
                f"{F.sec(eng.top_plateau_s, 1)} par tour : la démultiplication est trop courte pour ce circuit.")
        if x.allows("racer") and r:
            new = r - 1
            drop = eng.top_rpm * (1 - new / r)
            action = (f"Rallonge d'une dent à la couronne : {r} → {new} dents"
                      f"{f' (pignon {pig})' if pig else ''}. Tu perds environ {F.rpm(drop)} en bout de ligne droite "
                      "et le moteur continue de tirer jusqu'au freinage.")
        else:
            action = "Rallonge la démultiplication d'une dent à la couronne et compare ta vitesse de pointe."
        head = f"démultiplication trop courte : {F.sec(eng.top_plateau_s, 1)} par tour au plafond"
        rank = 0.06 + 0.05 * min(1.0, eng.top_plateau_s)
    elif len(low) >= 2 and fam_top and eng.top_rpm < fam_top - 300:
        worst = min(low, key=lambda c: c.rpm_min)
        names = ", ".join(str(c.id) for c in sorted(low, key=lambda c: c.id)[:4])
        fact = (f"Ton moteur tombe sous {F.rpm(eng.knee_rpm)} (le régime où il pousse vraiment) dans les virages {names}, "
                f"jusqu'à {F.rpm(worst.rpm_min)} au {worst.id}, et ne plafonne pas en bout de ligne droite "
                f"({F.rpm(eng.top_rpm)}).")
        if x.allows("racer") and r:
            need = r * (eng.knee_rpm / worst.rpm_min - 1.0)
            room = r * (fam_top / eng.top_rpm - 1.0)
            n = int(max(1, min(3, math.floor(min(need, room) + 0.5))))
            new = r + n
            gain = worst.rpm_min * (new / r - 1)
            action = (f"Raccourcis : couronne {r} → {new} dents{f' (pignon {pig})' if pig else ''}. "
                      f"Environ {F.rpm(gain)} de plus au point le plus lent du {worst.id}, et ton bout de ligne droite "
                      f"monte vers {F.rpm(eng.top_rpm * new / r)}.")
        else:
            action = ("Raccourcis la démultiplication d'une à deux dents à la couronne, et vérifie que tu ne "
                      "plafonnes pas en bout de ligne droite.")
        head = f"démultiplication trop longue : moteur sous sa plage dans {len(low)} virages"
        rank = 0.06 + 0.01 * len(low)
    else:
        return None
    return Finding("demultiplication", "reglage", "setup", None, head, fact, action,
                   "Repère : au prochain relais, compare le régime en bout de ligne droite et au point le plus lent.",
                   impact_s=0.0, rank_s=rank, difficulty="facile", min_tier="racer",
                   teaser="Combien de dents changer à la couronne pour ce circuit")


def p_consistency(x: Ctx) -> Optional[Finding]:
    s = x.session
    if not s.best_lap_time or not s.median_lap_time or len(s.lap_times) < 5:
        return None
    # Les tours de mise en température ne disent rien de la régularité.
    laps = sorted(s.lap_times)
    skip = s.grip_warmup_laps or 0
    kept = [s.lap_times[k] for k in laps[skip:]] if len(laps) - skip >= 4 else list(s.lap_times.values())
    gap = float(np.median(kept)) - s.best_lap_time
    if gap < 0.35:
        return None
    top = sorted([c for c in x.corners if c.lap_spread_s], key=lambda c: c.lap_spread_s, reverse=True)[:2]
    where = ""
    if top:
        where = " L'écart vient surtout " + " et ".join(
            f"du virage {c.id} ({F.sec(c.lap_spread_s)} entre ton meilleur et ton pire passage)" for c in top) + "."
    fact = (f"Ton tour habituel est à {F.sec(gap)} de ton meilleur tour ({F.sec(s.best_lap_time, 3)}, tour {s.best_lap}).{where}")
    action = ("Prochain relais : cinq tours à 98 %, exactement les mêmes repères à chaque tour, puis seulement attaque. "
              "La vitesse vient de la régularité.")
    return Finding("regularite", "regularite", "consistency", None, f"{F.sec(gap)} entre ton meilleur tour et ton tour habituel",
                   fact, action, impact_s=0.0, rank_s=min(0.12, gap * 0.15), difficulty="moyen", min_tier="rookie")


SESSION_PRINCIPLES = [
    Principle("eau", "moteur", "Température d'eau",
              "Un 2-temps à eau donne sa pleine puissance vers 50-60 °C : on masque le radiateur à froid, on le découvre à chaud.",
              "Température d'eau maxi par tour : < 48 °C sur 3 tours, ou > 64 °C sur 3 tours.",
              "rookie", "session", p_water),
    Principle("pneus_chauffe", "pneus", "Montée en température des pneus",
              "Pneus froids : on les charge au tour de lancement et on n'attaque qu'une fois l'appui revenu.",
              "Appui latéral (95e centile) par tour : au moins 3 tours pour atteindre 97 % du plateau.",
              "rookie", "session", p_tire_warmup),
    Principle("pneus_chute", "pneus", "Pneus qui surchauffent",
              "Une adhérence qui chute en fin de séance : moins de glisse, et une pression à froid un peu plus basse.",
              "Appui latéral des 3 derniers tours ≥ 3,5 % sous le meilleur niveau.",
              "rookie", "session", p_tire_fade),
    Principle("pression", "pneus", "Pressions selon la gomme",
              "Chaque gomme a sa plage de pression à froid et sa cible à chaud, selon l'état de piste.",
              "Pressions du réglage comparées à l'abaque de la base composants (pneu de Mon Kart).",
              "racer", "session", p_pressures),
    Principle("demultiplication", "reglage", "Démultiplication",
              "Le moteur doit rester dans sa plage partout : ni plafond en bout de ligne droite, ni effondrement dans les virages lents.",
              "Temps collé au régime maxi sans accélérer, et régime au point le plus lent des virages lents, sur la courbe du moteur mesurée.",
              "racer", "session", p_gearing),
    Principle("regularite", "regularite", "Régularité",
              "À niveau égal, c'est la régularité qui sépare deux pilotes : mêmes repères à chaque tour.",
              "Écart ≥ 0,35 s entre le meilleur tour et le tour médian.",
              "rookie", "session", p_consistency),
]

ALL_PRINCIPLES = CORNER_PRINCIPLES + SESSION_PRINCIPLES

# Levier de style -> phrase de synthèse (conseil de style global).
STYLE_LEVERS = {
    "enrouler": ("tes meilleures sorties viennent quand tu tournes plus tard et que tu enroules",
                 "Fais-en ta règle sur toute la piste : point de braquage un temps plus tard, corde tardive, gaz roues droites."),
    "entree_calme": ("tu rentres trop fort, et ça te coûte la sortie",
                     "Sur tout le tour, calme l'entrée de 2 à 3 km/h : le kart reste à plat et la relance arrive plus tôt."),
    "elan": ("tu casses trop ta vitesse dans les virages",
             "Pilote plus rond partout : garde de l'élan au point le plus lent, le moteur repart de plus haut."),
    "sacrifier": ("tu gagnes quand tu sacrifies l'entrée pour la sortie",
                  "Dans les virages lents, freine un peu plus fort, pivote, et accélère roues droites : pilotage en V."),
    "braquer_moins": ("ton kart frotte : tu le forces à tourner",
                      "Moins de volant, un seul mouvement par virage : un kart à plat ne retient pas le moteur."),
    "repere_freinage": ("tes freinages manquent de repères fixes",
                        "Choisis un repère visuel par freinage et tiens-le toute la séance, puis avance-les un par un."),
    "attaque_frein": ("tes freinages sont trop progressifs",
                      "Partout : attaque franche, puis relâche progressif. La force au début, le dosage à la fin."),
    "temps_mort": ("tu laisses le kart rouler en roue libre",
                   "Partout : enchaîne frein et gaz sans palier, un filet de gaz dès la fin du freinage."),
    "regime": ("ton moteur s'écroule dans les virages lents",
               "Garde le régime haut au point le plus lent : virages plus ronds, cordes un peu plus tardives."),
    "pied_constant": ("tu lèves le pied dans les virages rapides",
                      "Dans les virages rapides : pied constant, volant immobile, regard loin."),
    "lacher_frein": ("tu arrives encore freiné à la corde",
                     "Lâche les freins un peu plus tôt partout : le kart doit rouler à la corde."),
}
