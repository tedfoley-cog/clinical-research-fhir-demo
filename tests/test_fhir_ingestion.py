"""Tests for FHIR R4 Condition/Observation ingestion (RESWB-412).

Covers: a clean Condition bundle, a clean Observation bundle, an unmapped-code
case, Observation value handling (valueInteger + valueQuantity), subject
resolution, audit creation, and the end-to-end pre-screening worklist.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data" / "fhir"


def _load(name: str) -> dict:
    return json.loads((SAMPLE_DIR / name).read_text())


@pytest.fixture(autouse=True)
def seeded_db():
    # Fresh state per test (drops + recreates tables, reseeds participants/trials).
    seed()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_clean_condition_bundle(client):
    resp = client.post("/api/ingest/fhir", json=_load("condition_bundle.json"))
    assert resp.status_code == 200
    summary = resp.json()
    # 6 conditions, prostate cancer (MRN-1005) is unmapped → skipped.
    assert summary["resources_received"] == 6
    assert summary["resources_ingested"] == 5
    assert summary["resources_skipped"] == 1
    assert summary["outcome"] == "partial"

    # Diagnosis persisted with original coding preserved for traceability.
    pid = client.get("/api/participants").json()[0]["id"]
    detail = client.get(f"/api/participants/{pid}").json()
    assert detail["diagnoses"]
    dx = detail["diagnoses"][0]
    assert dx["category"] == "nsclc"
    assert dx["source_system"] == "http://snomed.info/sct"
    assert dx["source_code"] == "254637007"


def test_clean_observation_bundle(client):
    resp = client.post("/api/ingest/fhir", json=_load("observation_bundle.json"))
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["resources_received"] == 8
    assert summary["resources_ingested"] == 8
    assert summary["resources_skipped"] == 0
    assert summary["outcome"] == "success"

    # Value handling: ECOG arrives as valueInteger, ANC as valueQuantity.
    participants = {p["mrn"]: p["id"] for p in client.get("/api/participants").json()}
    detail = client.get(f"/api/participants/{participants['MRN-1001']}").json()
    measures = {m["measure"]: m for m in detail["measures"]}
    assert measures["ecog"]["value"] == 1.0
    assert measures["ecog"]["unit"] == ""
    assert measures["anc"]["value"] == 2.1
    assert measures["anc"]["unit"] == "10*9/L"


def test_unmapped_code_is_skipped_and_audited(client):
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Condition",
                    "code": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "254637007",
                                "display": "Non-small cell lung cancer",
                            }
                        ]
                    },
                    "subject": {"reference": "Patient/MRN-1001"},
                },
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "code": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": "399068003",
                                "display": "Malignant tumor of prostate",
                            }
                        ]
                    },
                    "subject": {"reference": "Patient/MRN-1005"},
                },
            },
        ],
    }
    resp = client.post("/api/ingest/fhir", json=bundle)
    assert resp.status_code == 200
    summary = resp.json()
    # One mapped (NSCLC) ingested, one unmapped (prostate) skipped — bundle not failed.
    assert summary["resources_received"] == 2
    assert summary["resources_ingested"] == 1
    assert summary["resources_skipped"] == 1
    assert summary["outcome"] == "partial"
    # The unmapped system|code is recorded in the audit detail for traceability.
    assert "http://snomed.info/sct|399068003" in summary["detail"]


def test_unknown_subject_is_skipped_not_created(client):
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Condition",
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
    summary = resp.json()
    assert summary["resources_ingested"] == 0
    assert summary["resources_skipped"] == 1
    # No participant was created for the unknown MRN.
    mrns = {p["mrn"] for p in client.get("/api/participants").json()}
    assert "MRN-9999" not in mrns


def test_exactly_one_audit_row_per_request(client):
    assert client.get("/api/ingest/audit").json() == []
    client.post("/api/ingest/fhir", json=_load("condition_bundle.json"))
    audit = client.get("/api/ingest/audit").json()
    assert len(audit) == 1
    row = audit[0]
    assert row["resources_received"] == 6
    assert row["resources_ingested"] == 5
    assert row["resources_skipped"] == 1
    assert row["resource_type"] == "Condition"

    client.post("/api/ingest/fhir", json=_load("observation_bundle.json"))
    assert len(client.get("/api/ingest/audit").json()) == 2


def test_invalid_payload_rejected(client):
    resp = client.post("/api/ingest/fhir", json={"resourceType": "Patient"})
    assert resp.status_code == 400


def test_worklist_lights_up_after_ingest(client):
    client.post("/api/ingest/fhir", json=_load("condition_bundle.json"))
    client.post("/api/ingest/fhir", json=_load("observation_bundle.json"))

    trials = {t["code"]: t["id"] for t in client.get("/api/trials").json()}
    results = client.get(f"/api/trials/{trials['LUNG-2024-017']}/prescreen").json()
    matches = {r["mrn"] for r in results if r["status"] == "potential_match"}
    # Alex Rivera (MRN-1001) and Casey Kim (MRN-1004) meet NSCLC + ECOG<=1 +
    # ANC>=1.5 + age>=18; surfaced as candidates for coordinator review.
    assert matches == {"MRN-1001", "MRN-1004"}
