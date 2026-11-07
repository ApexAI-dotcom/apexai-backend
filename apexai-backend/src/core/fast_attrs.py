"""
Propagation légère de ``DataFrame.attrs``.

pandas recopie ``attrs`` en COPIE PROFONDE à chaque opération qui crée un
nouvel objet (lecture d'une colonne, filtre, ``.loc``…). Le pipeline range
dans ``df.attrs`` des résultats volumineux (virages, freinages, Tour Parfait
IA) : chaque ``df["speed"]`` recopiait donc tout cela. Mesuré sur une séance
de 12 minutes à 20 Hz : 125 s sur 142 s d'analyse passaient dans ces copies.

On remplace la copie profonde par une copie superficielle : un objet dérivé
garde ses propres clés (en ajouter une ne touche pas l'original), mais les
valeurs sont partagées, ce qui est le cas d'usage du pipeline (métadonnées
de séance lues, jamais modifiées sur une sous-sélection).

Idempotent : ``install()`` peut être appelé plusieurs fois.
"""

from __future__ import annotations

from pandas.core.generic import NDFrame

_original = NDFrame.__finalize__


def _finalize(self, other, method=None, **kwargs):
    if isinstance(other, NDFrame):
        attrs = other.__dict__.get("_attrs")
        if attrs:
            # Le __finalize__ d'origine ne voit pas d'attrs : il saute la copie
            # profonde mais garde tout le reste (drapeaux, _metadata).
            object.__setattr__(other, "_attrs", {})
            try:
                result = _original(self, other, method=method, **kwargs)
            finally:
                object.__setattr__(other, "_attrs", attrs)
            object.__setattr__(self, "_attrs", dict(attrs))
            return result
    return _original(self, other, method=method, **kwargs)


def install() -> None:
    if getattr(NDFrame.__finalize__, "_apexai_fast", False):
        return
    _finalize._apexai_fast = True  # type: ignore[attr-defined]
    NDFrame.__finalize__ = _finalize  # type: ignore[assignment]


install()
