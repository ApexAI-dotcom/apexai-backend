#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Conditions de piste.

SOURCE UNIQUE. L'état de la piste et sa température ne sont pas une étiquette
décorative en haut du rapport : ils changent la PHYSIQUE de la séance, donc les
objectifs affichés au pilote.

Le défaut que ce module corrige était grave. La ligne de course bornait
l'adhérence latérale à μ ≥ 1,00 quelles que soient les conditions, alors qu'un
kart sous la pluie tient environ 0,7. L'outil calculait donc, par temps
humide, des vitesses de passage que le pilote ne pouvait pas atteindre — puis
lui reprochait de ne pas les atteindre.

Ce qui dépend réellement des conditions :

1. **L'adhérence de référence μ** — d'où découlent la vitesse optimale à l'apex
   et la ligne de course. C'est le paramètre central.
2. **Les bornes de calibration** — on continue de mesurer le grip réel du
   pilote, mais on ne le ramène plus de force dans une plage « sec ».
3. **La capacité de freinage plausible** — 0,6 à 1,6 g au sec, 0,35 à 0,95 g
   sous la pluie.
4. **Ce qu'on a le droit de conseiller** — « freine plus tard » sur piste
   mouillée est un conseil dangereux, pas un conseil exigeant.

Valeurs : adhérence d'un pneu slick karting au sec (μ ≈ 1,3), puis abattements
usuels en compétition pour piste humide, mouillée et pluie battante, où l'on
roule en pneus pluie sur une piste qui n'offre plus le même report.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

# ─── Adhérence par état de piste ────────────────────────────────────────────
# mu_reference : adhérence latérale attendue, en g.
# mu_min/mu_max : bornes dans lesquelles la calibration sur données réelles est
#   autorisée à se placer. Larges, mais cohérentes avec l'état de la piste.
# braking_min_g/braking_max_g : décélération plausible en karting.
_PROFILES: Dict[str, Dict[str, Any]] = {
    "dry": {
        "label": "Sec",
        "grip_factor": 1.00,
        "mu_reference": 1.30,
        "mu_min": 1.00, "mu_max": 1.55,
        "braking_min_g": 0.60, "braking_max_g": 1.60,
        "allow_brake_later": True,
        "allow_speed_push": True,
    },
    "damp": {
        "label": "Humide",
        "grip_factor": 0.85,
        "mu_reference": 1.10,
        "mu_min": 0.80, "mu_max": 1.30,
        "braking_min_g": 0.50, "braking_max_g": 1.30,
        "allow_brake_later": True,
        "allow_speed_push": True,
    },
    "wet": {
        "label": "Mouillée",
        "grip_factor": 0.72,
        "mu_reference": 0.95,
        "mu_min": 0.65, "mu_max": 1.15,
        "braking_min_g": 0.40, "braking_max_g": 1.10,
        # Sur piste mouillée, retarder le freinage fait partir le kart tout
        # droit : on ne le conseille pas, quel que soit l'écart mesuré.
        "allow_brake_later": False,
        "allow_speed_push": True,
    },
    "rain": {
        "label": "Pluie",
        "grip_factor": 0.62,
        "mu_reference": 0.80,
        "mu_min": 0.55, "mu_max": 1.00,
        "braking_min_g": 0.35, "braking_max_g": 0.95,
        "allow_brake_later": False,
        # Sous la pluie, les vitesses de référence n'ont plus de sens : on juge
        # la fluidité et la régularité, pas la vitesse de pointe en virage.
        "allow_speed_push": False,
    },
}


def _temperature_factor(temp_c: Optional[float]) -> float:
    """
    Correction d'adhérence liée à la température de piste.

    Un pneu karting travaille dans une fenêtre étroite. En dessous de 15 °C il
    ne monte pas en température sur un run court ; au-delà de 45 °C la gomme
    surchauffe et glisse. Les abattements restent modérés : la température
    module l'adhérence, elle ne la transforme pas comme le fait la pluie.
    """
    if temp_c is None:
        return 1.0
    t = float(temp_c)
    if t < 10:
        return 0.92
    if t < 15:
        return 0.96
    if t < 20:
        return 0.99
    if t <= 35:
        return 1.00
    if t <= 45:
        return 0.98
    return 0.95


@dataclass(frozen=True)
class TrackConditions:
    """État de piste résolu : tout le pipeline lit ces valeurs, pas la chaîne."""
    condition: str
    label: str
    temperature_c: Optional[float]
    grip_factor: float
    temperature_factor: float
    mu_reference: float
    mu_min: float
    mu_max: float
    braking_min_g: float
    braking_max_g: float
    allow_brake_later: bool
    allow_speed_push: bool

    @property
    def is_wet(self) -> bool:
        return self.condition in ("wet", "rain")

    @property
    def is_dry_reference(self) -> bool:
        return self.condition == "dry" and abs(self.temperature_factor - 1.0) < 1e-6

    def summary(self) -> str:
        """Phrase affichée au pilote : ce que les conditions ont changé."""
        # Virgule décimale : le rapport est en français, mélanger « 0.91 » et
        # « 1,30 » dans la même phrase fait négligé.
        mu = f"{self.mu_reference:.2f}".replace(".", ",")
        if self.is_dry_reference:
            return (
                "Piste sèche : les vitesses de référence sont calculées avec "
                f"l'adhérence maximale d'un slick karting ({mu} g)."
            )
        temp = f", {self.temperature_c:.0f} °C" if self.temperature_c is not None else ""
        return (
            f"Piste {self.label.lower()}{temp} : adhérence de référence ramenée à "
            f"{mu} g (contre 1,30 g au sec). Les vitesses de passage, la ligne de "
            f"course et les distances de freinage attendues sont recalculées sur "
            f"cette base — comparer ta séance à des repères de piste sèche "
            f"n'aurait aucun sens."
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["summary"] = self.summary()
        return d


def resolve_conditions(
    condition: Optional[str] = "dry",
    temperature_c: Optional[float] = None,
) -> TrackConditions:
    """Construit l'état de piste à partir de ce que le pilote a déclaré."""
    key = (condition or "dry").lower().strip()
    profile = _PROFILES.get(key, _PROFILES["dry"])
    tf = _temperature_factor(temperature_c)

    # La température module l'adhérence disponible ; elle ne relève jamais le
    # plancher, sinon un run par temps froid afficherait des cibles trop hautes.
    return TrackConditions(
        condition=key if key in _PROFILES else "dry",
        label=profile["label"],
        temperature_c=temperature_c,
        grip_factor=round(profile["grip_factor"] * tf, 3),
        temperature_factor=tf,
        mu_reference=round(profile["mu_reference"] * tf, 3),
        mu_min=round(profile["mu_min"] * tf, 3),
        mu_max=round(profile["mu_max"] * tf, 3),
        braking_min_g=round(profile["braking_min_g"] * tf, 3),
        braking_max_g=round(profile["braking_max_g"] * tf, 3),
        allow_brake_later=bool(profile["allow_brake_later"]),
        allow_speed_push=bool(profile["allow_speed_push"]),
    )


DRY = resolve_conditions("dry", None)


def get_conditions(df) -> TrackConditions:
    """
    Conditions attachées à la session.

    Passer l'état de piste en paramètre de chaque fonction du pipeline aurait
    demandé de modifier une vingtaine de signatures — et il aurait suffi d'en
    oublier une pour qu'un module continue de raisonner « au sec ». On le
    dépose une fois sur le DataFrame, et tout le monde y lit la même valeur.
    """
    try:
        c = df.attrs.get("track_conditions")
        if isinstance(c, TrackConditions):
            return c
    except Exception:
        pass
    return DRY


def attach_conditions(df, condition: Optional[str], temperature_c: Optional[float]) -> TrackConditions:
    """Résout puis attache les conditions au DataFrame de la session."""
    resolved = resolve_conditions(condition, temperature_c)
    df.attrs["track_conditions"] = resolved
    return resolved
