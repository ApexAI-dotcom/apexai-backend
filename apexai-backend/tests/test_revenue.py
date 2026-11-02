from src.api.revenue import summarize


def _sub(status, created, amount, interval="month", price="p_racer_m", canceled_at=None, qty=1):
    return {
        "status": status,
        "created": created,
        "canceled_at": canceled_at,
        "items": {"data": [{"quantity": qty, "price": {"id": price, "unit_amount": amount, "currency": "eur", "recurring": {"interval": interval, "interval_count": 1}}}]},
    }


def test_summarize_counts_mrr_and_period():
    since = 1_000
    subs = [
        _sub("active", 500, 999),  # ancien, mensuel 9,99
        _sub("active", 1_500, 9_900, interval="year", price="p_racer_y"),  # nouveau, annuel 99 -> 8,25/mois
        _sub("trialing", 1_200, 999),  # essai : ni actif ni MRR
        _sub("canceled", 100, 999, canceled_at=1_100),  # résilié dans la période
        _sub("incomplete", 1_300, 999),  # paiement non abouti : pas un nouvel abonné
    ]
    invoices = [
        {"amount_paid": 999, "status_transitions": {"paid_at": 1_200}},
        {"amount_paid": 9_900, "status_transitions": {"paid_at": 1_600}},
        {"amount_paid": 999, "status_transitions": {"paid_at": 900}},  # avant la période
    ]
    out = summarize(subs, invoices, since, {"p_racer_m": "Racer mensuel", "p_racer_y": "Racer annuel"})
    assert out["active"] == 2
    assert out["trialing"] == 1
    assert out["mrr"] == round((999 + 9_900 / 12) / 100, 2)
    assert out["collected"] == 108.99
    assert out["new"] == 2  # l'annuel et l'essai
    assert out["cancellations"] == 1
    assert {p["plan"] for p in out["by_plan"]} == {"Racer mensuel", "Racer annuel"}
