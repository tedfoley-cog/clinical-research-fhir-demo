"""Tests for the existing workbench API (initial state).

These document current behavior, including that FHIR ingestion is not yet
implemented (returns 501). When Devin implements ingestion during the demo, the
501 test should be updated and `tests/test_fhir_ingestion.py` added.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    seed()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_list_participants(client):
    resp = client.get("/api/participants")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6
    assert {p["mrn"] for p in data} >= {"MRN-1001", "MRN-1006"}


def test_participant_detail_has_no_clinical_data_yet(client):
    pid = client.get("/api/participants").json()[0]["id"]
    detail = client.get(f"/api/participants/{pid}").json()
    # Initial state: clinical data is empty until FHIR ingestion runs.
    assert detail["diagnoses"] == []
    assert detail["measures"] == []


def test_list_trials(client):
    resp = client.get("/api/trials")
    assert resp.status_code == 200
    codes = {t["code"] for t in resp.json()}
    assert codes == {"LUNG-2024-017", "BRST-2024-003"}


def test_prescreen_returns_worklist(client):
    trial_id = client.get("/api/trials").json()[0]["id"]
    resp = client.get(f"/api/trials/{trial_id}/prescreen")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 6
    # No clinical data yet, so nobody is a potential match in the initial state.
    assert all(r["status"] == "not_matched" for r in results)


def test_fhir_ingestion_accepts_empty_bundle(client):
    # FHIR ingestion is implemented (RESWB-412); an empty Bundle is a no-op.
    resp = client.post("/api/ingest/fhir", json={"resourceType": "Bundle", "entry": []})
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["resources_received"] == 0
    assert summary["resources_ingested"] == 0
    assert summary["outcome"] == "success"
