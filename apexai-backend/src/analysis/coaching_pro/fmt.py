# -*- coding: utf-8 -*-
"""Mise en forme française des chiffres et choix des formulations."""
from __future__ import annotations

import hashlib
from typing import List, Optional, Sequence


def num(x: Optional[float], nd: int = 0) -> str:
    """1234.5 -> « 1 234,5 » (espace fine insécable pour les milliers)."""
    if x is None:
        return "?"
    s = f"{abs(float(x)):,.{nd}f}".replace(",", " ").replace(".", ",")
    return ("-" if float(x) < 0 and float(f"{abs(x):.{nd}f}") != 0 else "") + s


def kmh(x, nd=0) -> str:
    return f"{num(x, nd)}\u00a0km/h"


def sec(x, nd=2) -> str:
    return f"{num(x, nd)}\u00a0s"


def m(x, nd=0) -> str:
    return f"{num(x, nd)}\u00a0m"


def g(x, nd=2) -> str:
    return f"{num(x, nd)}\u00a0g"


def rpm(x) -> str:
    return f"{num(round(float(x) / 10) * 10 if x is not None else None, 0)}\u00a0tr/min"


def bar(x, nd=2) -> str:
    return f"{num(x, nd)}\u00a0bar"


def deg(x) -> str:
    return f"{num(x, 0)}\u00a0°C"


def plural(n: int, one: str, many: str) -> str:
    return one if abs(n) == 1 else many


def laps_list(laps: Sequence[int]) -> str:
    laps = [int(x) for x in laps]
    if not laps:
        return ""
    if len(laps) == 1:
        return f"tour {laps[0]}"
    return "tours " + ", ".join(str(x) for x in laps[:-1]) + f" et {laps[-1]}"


class Voice:
    """
    Choisit une formulation parmi plusieurs, sans répéter la même consigne
    deux fois dans une séance. Le choix est stable (même séance, même texte).
    """

    def __init__(self, seed: str = ""):
        self.seed = seed
        self.used: set = set()

    def pick(self, key: str, variants: List[str]) -> str:
        variants = [v for v in variants if v]
        if not variants:
            return ""
        h = int(hashlib.md5(f"{self.seed}|{key}".encode()).hexdigest(), 16)
        order = [variants[(h + i) % len(variants)] for i in range(len(variants))]
        for v in order:
            if v not in self.used:
                self.used.add(v)
                return v
        return order[0]
