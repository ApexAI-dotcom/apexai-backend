"""
Revenus réels, lus dans Stripe, pour le back-office.

- abonnements actifs (hors essais), par offre ;
- revenu mensuel récurrent (MRR) : prix catalogue ramené au mois, hors remises ;
- encaissé sur la période : factures réellement payées ;
- nouveaux abonnements et résiliations sur la période.

Lecture seule. Mise en cache 5 minutes : le back-office se rafraîchit toutes les
minutes, Stripe n'a pas besoin d'être interrogé à chaque fois.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[int, tuple] = {}
_TTL_S = 300

_LIVE = {"active", "past_due"}


def _monthly(amount_cents: int, interval: str, count: int) -> float:
    count = max(1, int(count or 1))
    if interval == "year":
        return amount_cents / 12 / count
    if interval == "week":
        return amount_cents * 52 / 12 / count
    if interval == "day":
        return amount_cents * 365 / 12 / count
    return amount_cents / count


def _g(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def summarize(
    subscriptions: Iterable[Any],
    paid_invoices: Iterable[Any],
    since_ts: int,
    price_names: Dict[str, str],
) -> Dict[str, Any]:
    """Synthèse pure (testable) à partir des objets Stripe."""
    active = 0
    trialing = 0
    mrr_cents = 0.0
    by_plan: Dict[str, int] = {}
    new_subs = 0
    cancellations = 0
    currency = "eur"

    for s in subscriptions:
        status = _g(s, "status")
        created = int(_g(s, "created", 0) or 0)
        canceled_at = _g(s, "canceled_at")
        if created >= since_ts and status not in ("incomplete", "incomplete_expired"):
            new_subs += 1
        if canceled_at and int(canceled_at) >= since_ts:
            cancellations += 1
        if status == "trialing":
            trialing += 1
            continue
        if status not in _LIVE:
            continue
        active += 1
        items = _g(_g(s, "items"), "data", []) or []
        for it in items:
            price = _g(it, "price") or {}
            rec = _g(price, "recurring") or {}
            amount = int(_g(price, "unit_amount", 0) or 0)
            qty = int(_g(it, "quantity", 1) or 1)
            currency = _g(price, "currency", currency) or currency
            mrr_cents += _monthly(amount * qty, _g(rec, "interval", "month"), _g(rec, "interval_count", 1))
            pid = _g(price, "id", "")
            name = price_names.get(pid) or _g(price, "nickname") or "Autre offre"
            by_plan[name] = by_plan.get(name, 0) + 1

    collected = 0
    for inv in paid_invoices:
        paid_at = _g(_g(inv, "status_transitions"), "paid_at") or _g(inv, "created", 0)
        if int(paid_at or 0) >= since_ts:
            collected += int(_g(inv, "amount_paid", 0) or 0)

    return {
        "currency": currency,
        "active": active,
        "trialing": trialing,
        "mrr": round(mrr_cents / 100, 2),
        "collected": round(collected / 100, 2),
        "new": new_subs,
        "cancellations": cancellations,
        "by_plan": [{"plan": k, "count": v} for k, v in sorted(by_plan.items(), key=lambda kv: -kv[1])],
    }


def stripe_revenue(days: int) -> Optional[Dict[str, Any]]:
    """Revenus Stripe de la période, ou None si Stripe est injoignable ou non configuré."""
    try:
        import stripe  # type: ignore

        if not getattr(stripe, "api_key", None):
            return None
        hit = _CACHE.get(days)
        if hit and time.time() - hit[0] < _TTL_S:
            return hit[1]

        from .stripe_routes import PRICE_IDS

        names = {
            PRICE_IDS.get("racer_monthly"): "Racer mensuel",
            PRICE_IDS.get("racer_annual"): "Racer annuel",
            PRICE_IDS.get("team_monthly"): "Team mensuel",
            PRICE_IDS.get("team_annual"): "Team annuel",
        }
        names = {k: v for k, v in names.items() if k}
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_ts = int(since.timestamp())

        subs: List[Any] = list(stripe.Subscription.list(status="all", limit=100, expand=["data.items.data.price"]).auto_paging_iter())
        invoices: List[Any] = list(
            stripe.Invoice.list(status="paid", limit=100, created={"gte": since_ts - 86400}).auto_paging_iter()
        )
        out = summarize(subs, invoices, since_ts, names)
        out["window_days"] = days
        _CACHE[days] = (time.time(), out)
        return out
    except Exception as exc:  # Stripe injoignable : le reste du back-office s'affiche
        logger.warning("stripe_revenue: %s", exc)
        return None
