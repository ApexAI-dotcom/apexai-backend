import json
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("scrapling")  # lancé par le workflow « Collecte » ; ignoré ailleurs si absent

from collect.polite import USER_AGENT, PoliteFetcher, Refused
from collect.sources import circuit_page, ffsa_events

FIX = Path(__file__).parent / "fixtures"


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        return self.routes.get(url, (404, ""))


def fetcher(tmp_path, routes):
    http = FakeHttp(routes)
    return PoliteFetcher(cache_dir=tmp_path / "c", http_get=http, delay_s=0), http


# ── Garde-fous ──────────────────────────────────────────────────────────────
def test_identification_honnete(tmp_path):
    f, http = fetcher(tmp_path, {"https://a.fr/p": (200, "ok")})
    f.get("https://a.fr/p")
    assert all(h["User-Agent"] == USER_AGENT for _, h in http.calls)
    assert "ApexAIBot" in USER_AGENT and "apexai.racing" in USER_AGENT


@pytest.mark.parametrize("url", ["https://www.linkedin.com/company/x", "https://instagram.com/x", "https://m.facebook.com/x"])
def test_domaines_exclus(tmp_path, url):
    f, http = fetcher(tmp_path, {})
    with pytest.raises(Refused):
        f.get(url)
    assert http.calls == []  # pas même robots.txt


def test_robots_respecte(tmp_path):
    f, http = fetcher(tmp_path, {
        "https://a.fr/robots.txt": (200, "User-agent: *\nDisallow: /prive/\n"),
        "https://a.fr/prive/x": (200, "secret"),
        "https://a.fr/public": (200, "ok"),
    })
    with pytest.raises(Refused):
        f.get("https://a.fr/prive/x")
    assert f.get("https://a.fr/public") == "ok"
    assert ("https://a.fr/prive/x", {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}) not in http.calls


def test_robots_illisible_on_s_abstient(tmp_path):
    f, _ = fetcher(tmp_path, {"https://a.fr/robots.txt": (500, ""), "https://a.fr/p": (200, "ok")})
    with pytest.raises(Refused):
        f.get("https://a.fr/p")


@pytest.mark.parametrize("status,body", [(403, ""), (429, ""), (200, '<div class="g-recaptcha" data-sitekey="x">')])
def test_refus_arrete_le_domaine(tmp_path, status, body):
    f, http = fetcher(tmp_path, {"https://a.fr/p": (status, body), "https://a.fr/q": (200, "ok")})
    with pytest.raises(Refused):
        f.get("https://a.fr/p")
    n = len(http.calls)
    with pytest.raises(Refused):
        f.get("https://a.fr/q")  # on ne réessaie pas, on ne contourne pas
    assert len(http.calls) == n


def test_cache(tmp_path):
    f, http = fetcher(tmp_path, {"https://a.fr/p": (200, "ok")})
    f.get("https://a.fr/p")
    f.get("https://a.fr/p")
    assert [u for u, _ in http.calls].count("https://a.fr/p") == 1


def test_delai_entre_requetes(tmp_path, monkeypatch):
    slept = []
    monkeypatch.setattr("collect.polite.time.sleep", lambda s: slept.append(s))
    http = FakeHttp({"https://a.fr/p": (200, "1"), "https://a.fr/q": (200, "2")})
    f = PoliteFetcher(cache_dir=tmp_path / "c", http_get=http, delay_s=4)
    f.get("https://a.fr/p")
    f.get("https://a.fr/q")
    assert slept and all(s <= 4 for s in slept) and sum(slept) > 7  # robots + p + q : deux attentes


# ── FFSA ────────────────────────────────────────────────────────────────────
def test_ffsa_parse():
    recs = ffsa_events.parse_events((FIX / "ffsa_events_2026.json").read_text(), 2026)
    assert len(recs) == 15
    assert recs == sorted(recs, key=lambda r: r["date"])
    bresse = next(r for r in recs if r["source_id"] == "ffsa:210")
    assert bresse["date"] == "2026-10-25" and bresse["place"] == "Bresse"
    assert "KZ2" in bresse["categories"]
    assert bresse["url"].startswith("https://www.ffsakarting.org/competitions/2026/")
    assert set(bresse) == {"source", "source_id", "season", "date", "place", "competition", "categories", "url", "collected_at"}


def test_ffsa_reponse_vide_ou_cassee():
    assert ffsa_events.parse_events({"success": False}, 2026) == []
    assert ffsa_events.parse_events({"success": True, "data": [{"date": "?", "place": "X"}]}, 2026) == []


def test_ffsa_saisons():
    filt = (FIX / "ffsa_events_filters.json").read_text()
    assert ffsa_events.seasons_to_fetch(filt, date(2026, 11, 18)) == [2026]
    assert ffsa_events.seasons_to_fetch({"data": {"years": [2027, 2026]}}, date(2026, 11, 18)) == [2026, 2027]


def test_ffsa_collect_bout_en_bout(tmp_path):
    base = "https://www.ffsakarting.org"
    f, http = fetcher(tmp_path, {
        f"{base}/ajax/events/filters": (200, (FIX / "ffsa_events_filters.json").read_text()),
        f"{base}/ajax/events?year=2026": (200, (FIX / "ffsa_events_2026.json").read_text()),
    })
    recs = list(ffsa_events.collect(f, today=date(2026, 11, 18)))
    assert len(recs) == 15
    assert [u for u, _ in http.calls] == [f"{base}/robots.txt", f"{base}/ajax/events/filters", f"{base}/ajax/events?year=2026"]


# ── Circuits (Scrapling) ────────────────────────────────────────────────────
def test_circuit_jsonld():
    r = circuit_page.parse_circuit((FIX / "circuit_jsonld.html").read_text(), "https://karting-du-val.example/")
    assert r["name"] == "Karting du Val"
    assert (r["postal_code"], r["city"]) == ("72000", "Exempleville")
    assert (r["lat"], r["lng"]) == (47.95, 0.21)
    assert r["track_length_m"] == 1150
    assert "Jean" not in json.dumps(r)  # jamais un nom de personne


def test_circuit_sans_donnees_structurees():
    r = circuit_page.parse_circuit((FIX / "circuit_meta.html").read_text(), "https://kc.example/")
    assert r["name"] == "Kart Club Exemple" and r["track_length_m"] == 820 and r["lat"] is None


def test_seed_vide_par_defaut():
    seed = json.loads((Path(circuit_page.__file__).parent / "circuits_seed.json").read_text())
    assert seed["circuits"] == []


# ── Circuits (OpenStreetMap) ────────────────────────────────────────────────
def test_osm_parse():
    from collect.sources import osm_circuits
    recs = osm_circuits.parse_overpass((FIX / "overpass_karting.json").read_text())
    assert [r["name"] for r in recs] == ["Kart Club Exemple Sud", "Karting Exemple Nord"]  # doublon et sans-nom écartés
    nord = recs[1]
    assert nord["track_length_m"] == 1150 and nord["surface"] == "asphalt"
    assert recs[0]["track_length_m"] == 900 and recs[0]["city"] == "Exempleville"
    assert all("OpenStreetMap" in r["attribution"] for r in recs)
