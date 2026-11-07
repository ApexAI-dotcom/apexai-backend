"""
Progression réelle d'une analyse.

Le pipeline tourne dans un thread ; il annonce ses étapes avec ``report()``.
La tâche de fond qui l'a lancé installe un collecteur pour ce thread
(``bind``) et le transmet au suivi lu par l'app. Sans collecteur (appel
direct, tests), ``report()`` ne fait rien.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

_local = threading.local()

Reporter = Callable[[int, str], None]


def bind(fn: Optional[Reporter]) -> None:
    _local.fn = fn


def report(pct: int, label: str) -> None:
    fn: Optional[Reporter] = getattr(_local, "fn", None)
    if fn is None:
        return
    try:
        fn(int(pct), label)
    except Exception:
        pass
