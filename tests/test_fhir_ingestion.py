"""Tests for FHIR R4 ingestion (Condition + Observation).

Covers a clean Condition bundle, a clean Observation bundle, the unmapped-code
case (prostate cancer is intentionally absent from the terminology map), audit
creation, and the end-to-end effect on the pre-screening worklist.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data" / "fhir"


def _bundle(name: str) -> dict:
    return json.loads((SAMPLE_DIR / name).read_text())


@pytest.fixture(autouse=True)
def seeded_db():
    # Reset to seeded demographics-only state before each test (no clinical data).
    seed()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ingest_clean_condition_bundle(client):
    resp = client.post("/api/ingest/fhir", json=_bundle("condition_bundle.json"))
    assert resp.status_code == 200
    body = resp.json()
    # 6 conditions: 5 mapped, 1 (prostate cancer) unmapped -> skipped.
    assert body["resources_received"] == 6
    assert body["resources_ingested"] == 5
    assert body["resources_skipped"] == 1
    assert body["outcome"] == "partial"

    # Diagnosis is normalized and original coding preserved for traceability.
    pid = next(p["id"] for p in client.get("/api/participants").json() if p["mrn"] == "MRN-1001")
    detail = client.get(f"/api/participants/{pid}").json()
    assert detail["diagnoses"][0]["category"] == "nsclc"
    assert detail["diagnoses"][0]["source_system"] == "http://snomed.info/sct"
    assert detail["diagnoses"][0]["source_code"] == "254637007"


def test_ingest_clean_observation_bundle(client):
    resp = client.post("/api/ingest/fhir", json=_bundle("observation_bundle.json"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resources_received"] == 8
    assert body["resources_ingested"] == 8
    assert body["resources_skipped"] == 0
    assert body["outcome"] == "success"

    # Both valueInteger (ECOG) and valueQuantity (ANC) are read.
    pid = next(p["id"] for p in client.get("/api/participants").json() if p["mrn"] == "MRN-1001")
    measures = {m["measure"]: m for m in client.get(f"/api/participants/{pid}").json()["measures"]}
    assert measures["ecog"]["value"] == 1.0
    assert measures["anc"]["value"] == 2.1
    assert measures["anc"]["unit"] == "10*9/L"


def test_unmapped_code_is_skipped_and_audited(client):
    resp = client.post("/api/ingest/fhir", json=_bundle("condition_bundle.json"))
    assert resp.status_code == 200
    assert resp.json()["resources_skipped"] == 1

    # The unmapped system|code is recorded in the audit detail, not silently dropped.
    audit = client.get("/api/ingest/audit").json()[0]
    assert "http://snomed.info/sct|399068003" in audit["detail"]

    # The participant with only an unmapped diagnosis gets no Diagnosis row.
    pid = next(p["id"] for p in client.get("/api/participants").json() if p["mrn"] == "MRN-1005")
    assert client.get(f"/api/participants/{pid}").json()["diagnoses"] == []


def test_exactly_one_audit_row_per_request(client):
    assert client.get("/api/ingest/audit").json() == []

    client.post("/api/ingest/fhir", json=_bundle("condition_bundle.json"))
    client.post("/api/ingest/fhir", json=_bundle("observation_bundle.json"))

    audits = client.get("/api/ingest/audit").json()
    assert len(audits) == 2


def test_unknown_subject_is_skipped_not_created(client):
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "cond-ghost",
                    "code": {
                        "coding": [
                            {"system": "http://snomed.info/sct", "code": "254637007"}
                        ]
                    },
                    "subject": {"reference": "Patient/MRN-9999"},
                }
            }
        ],
    }
    resp = client.post("/api/ingest/fhir", json=bundle)
    assert resp.status_code == 200
    body = resp.json()
    assert body["resources_ingested"] == 0
    assert body["resources_skipped"] == 1
    # No participant is created for an unknown MRN.
    assert all(p["mrn"] != "MRN-9999" for p in client.get("/api/participants").json())


def test_observation_with_null_value_is_skipped_not_crashing(client):
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-null",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "89247-1"}]},
                    "subject": {"reference": "Patient/MRN-1001"},
                    "valueInteger": None,
                }
            }
        ],
    }
    resp = client.post("/api/ingest/fhir", json=bundle)
    assert resp.status_code == 200
    body = resp.json()
    assert body["resources_received"] == 1
    assert body["resources_ingested"] == 0
    assert body["resources_skipped"] == 1
    assert "missing value" in body["detail"]


def test_worklist_lights_up_after_ingesting_both_bundles(client):
    client.post("/api/ingest/fhir", json=_bundle("condition_bundle.json"))
    client.post("/api/ingest/fhir", json=_bundle("observation_bundle.json"))

    trials = client.get("/api/trials").json()
    trial_id = next(t["id"] for t in trials if t["code"] == "LUNG-2024-017")
    worklist = client.get(f"/api/trials/{trial_id}/prescreen").json()
    matches = {r["mrn"] for r in worklist if r["status"] == "potential_match"}
    # Alex Rivera (MRN-1001) and Casey Kim (MRN-1004) meet dx/ECOG/ANC/age.
    assert matches == {"MRN-1001", "MRN-1004"}
