"""Analyses en tâche de fond : dépôt, progression, signature, mode allégé."""

import gzip
import os
import time

from src.api.jobs import signature
from src.api.main import app
from tests._httpx_compat import make_test_client

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "adria_4laps.csv.gz")


def _content() -> bytes:
    with gzip.open(FIXTURE, "rb") as f:
        return f.read()


def _wait(client, job_id, timeout=120):
    t = time.time()
    seen = []
    while time.time() - t < timeout:
        j = client.get(f"/api/analysis/jobs/{job_id}").json()
        seen.append(j["progress"])
        if j["status"] in ("done", "error"):
            return j, seen
        time.sleep(0.2)
    raise AssertionError("tâche jamais terminée")


def test_signature_depends_on_content_params_and_mode():
    a = signature(b"abc", {"laps": []}, "full")
    assert a == signature(b"abc", {"laps": []}, "full")
    assert a != signature(b"abd", {"laps": []}, "full")
    assert a != signature(b"abc", {"laps": [1]}, "full")
    assert a != signature(b"abc", {"laps": []}, "light")


def test_job_runs_reports_progress_and_reuses_signature():
    with make_test_client(app) as client:
        content = _content()
        r = client.post(
            "/api/analysis/jobs",
            files={"file": ("adria.csv", content, "text/csv")},
            data={"mode": "light", "track_condition": "dry"},
        )
        assert r.status_code in (200, 202), r.text
        job, seen = _wait(client, r.json()["job_id"])
        assert job["status"] == "done", job
        res = job["result"]
        assert res["plot_data"]["speed_trace"]["laps"]
        assert res["plot_data"]["trajectory_2d"]["laps"]
        assert res["coaching_advice"] == []  # allégé : pas de coaching
        assert seen == sorted(seen)  # la jauge ne recule jamais

        # Même fichier, mêmes paramètres : resservi tout de suite, nouvel identifiant.
        r2 = client.post(
            "/api/analysis/jobs",
            files={"file": ("adria.csv", content, "text/csv")},
            data={"mode": "light", "track_condition": "dry"},
        )
        j2 = r2.json()
        assert j2["status"] == "done" and j2["cached"] is True
        assert j2["result"]["analysis_id"] != res["analysis_id"]


def test_unknown_job_is_404():
    with make_test_client(app) as client:
        assert client.get("/api/analysis/jobs/inconnu").status_code == 404
