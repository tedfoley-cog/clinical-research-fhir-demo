# Implementation Plan — Clinical Research FHIR Ingestion Demo

> This file is the first commit of the repo. It documents the *initial ("before")*
> state of the codebase and exactly what Devin does live during the demo. No
> migrated/after code is included in the scaffold.

## 1. What the demo proves

An enterprise engineering team can hand Devin a realistic Jira-style ticket
("add FHIR-based ingestion of Condition & Observation resources into the research
workbench") and Devin will inspect the existing backend/frontend/data model,
implement the integration adapter, normalize cancer-diagnosis fields where
mappings exist, persist an audit record for every ingest, add unit + integration
tests, update the docs, and open a reviewable PR with assumptions and reviewer
notes. This is governed, reviewable enterprise software work *around* Epic/FHIR
systems — **not** clinical decision-making.

## 2. What Devin does live (one sentence)

Devin implements the empty `app/adapters/fhir` adapter + the stubbed
`POST /api/ingest/fhir` endpoint so that synthetic FHIR R4 Condition/Observation
bundles are parsed, normalized against the terminology map, persisted, and audited
— then opens a PR.

> **Guardrail emphasized throughout:** the workbench produces *pre-screening
> support* surfaced to a human research coordinator. It never makes eligibility,
> enrollment, or treatment decisions. No PHI — all data is synthetic.

## 3. Stack and rationale

| Choice | Why | Source |
|---|---|---|
| FastAPI (Python 3.11) | Small, runnable in one command; free Swagger UI at `/docs` as a native visual | fastapi.tiangolo.com |
| SQLAlchemy + SQLite | Zero-setup relational data model; realistic participant/condition/observation schema | docs.sqlalchemy.org |
| Pydantic v2 | Request/response schemas + validation | docs.pydantic.dev |
| Vanilla HTML/JS workbench (`static/`) | Frontend the audience sees; lists participants + pre-screening flags; no build step | — |
| FHIR R4 (Condition, Observation, Bundle) | The integration format MSK works in post-Epic | HL7 FHIR R4 spec (hl7.org/fhir/R4) |
| pytest + ruff | Tests + lint; minimal green CI | — |

### Terminology / clinical codes (verified against authoritative sources)

All synthetic clinical codes are real and were confirmed before use:

| Code | System | Meaning | Source |
|---|---|---|---|
| `254637007` | SNOMED CT | NSCLC — Non-small cell lung cancer | HL7 FHIR clinical resource examples (confirmed via DeepWiki HL7/fhir) |
| `C34.90` / `C34.11` | ICD-10-CM | Malignant neoplasm of lung (unspecified / right upper lobe) | ICD-10-CM tabular |
| `254838004` | SNOMED CT | Malignant tumor of breast | SNOMED CT International |
| `C50.911` | ICD-10-CM | Malignant neoplasm, unspecified site of right female breast | ICD-10-CM tabular |
| `363406005` | SNOMED CT | Malignant tumor of colon | SNOMED CT International |
| `C18.9` | ICD-10-CM | Malignant neoplasm of colon, unspecified | ICD-10-CM tabular |
| `89247-1` | LOINC | ECOG Performance Status score (0–5) | loinc.org/89247-1 (verified) |
| `751-8` | LOINC | Neutrophils [#/volume] in Blood (ANC) | loinc.org/751-8 (verified) |
| `http://terminology.hl7.org/CodeSystem/condition-clinical` | FHIR | clinicalStatus = active | HL7 FHIR R4 |
| `http://terminology.hl7.org/CodeSystem/condition-ver-status` | FHIR | verificationStatus = confirmed | HL7 FHIR R4 |

## 4. Repo layout (initial state)

```
app/
  main.py               FastAPI app; mounts static workbench; includes routers
  database.py           SQLAlchemy engine/session (SQLite)
  models.py             ORM: Participant, Diagnosis, MeasureResult, Trial,
                        EligibilityCriterion, PreScreenFlag, IngestionAudit
  schemas.py            Pydantic request/response models
  seed.py               Seeds synthetic participants, trials, criteria
  services/
    prescreen.py        Existing pre-screening match logic (diagnosis + measures)
  routers/
    participants.py     GET /api/participants, /api/participants/{id}
    trials.py           GET /api/trials, /api/trials/{id}/prescreen
    ingestion.py        POST /api/ingest/fhir  <-- STUB (returns 501). Devin builds this.
  adapters/fhir/
    __init__.py         empty package
    README.md           the adapter contract Devin must fulfill (TODO)
  terminology/
    mappings.py         partial SNOMED/ICD-10 -> internal diagnosis-category map
static/
  index.html, app.js, styles.css   the workbench UI (native visual)
sample_data/fhir/
  condition_bundle.json    synthetic FHIR R4 Bundle of Condition resources
  observation_bundle.json  synthetic FHIR R4 Bundle of Observation resources
tests/
  test_prescreen.py     existing tests for pre-screen logic
  test_api.py           existing API tests
docs/
  IMPLEMENTATION_PLAN.md  (this file)
  TICKET.md             the ticket handed to Devin in the live demo
  DATA_MODEL.md         data model reference
  flowchart.html / .png
README.md, DEMO_NOTES.md, pyproject.toml, .github/workflows/ci.yml, .gitignore
```

Devin will *add* (live): `app/adapters/fhir/adapter.py`, the body of
`routers/ingestion.py`, `tests/test_fhir_ingestion.py`, and doc updates.

## 5. Flowchart outline

`Ticket (Jira)` -> `Devin Session` -> [`Inspect Repo`, `Implement FHIR Adapter`,
`Normalize Diagnoses`, `Persist + Audit`, `Add Tests`, `Update Docs`] -> `Open PR`
-> `Coordinator Reviews` -> `Pre-Screening Worklist` (human-in-the-loop).
Guardrail node: "Support only — no eligibility/treatment decisions".

## 6. Runtime plan

- `pip install -e ".[dev]"` then `uvicorn app.main:app --reload` (port 8000).
- Visit `/` for the workbench UI, `/docs` for Swagger.
- `python -m app.seed` populates SQLite with synthetic participants/trials.
- Before Devin's work, `POST /api/ingest/fhir` returns **501 Not Implemented**
  and ingested-diagnosis counts are zero — the visible gap the demo closes.

## 7. Visual artifact plan

Primary visual = **the flowchart** (always) + the **workbench UI** (native output
of the app showing the pre-screening worklist) + the **PR diff** Devin produces
live. No live dashboard is built — this is a one-shot transformation whose result
is a PR, so it fails the Step 5a Dashboard Decision Gate. The workbench UI is a
static-served page, not a separate dashboard server.

## 8. CI plan

GitHub Actions: checkout -> setup-python 3.11 -> `pip install -e ".[dev]"` ->
`ruff check` -> `pytest`. Under 40 lines. Green on the initial scaffold.

## 9. Risks / unknowns

- SNOMED CT online browser was rate-limited during research; SNOMED codes used are
  standard well-known concepts and the primary one (NSCLC `254637007`) was
  confirmed via HL7 FHIR examples. LOINC + ICD-10 codes verified directly.
- Realistic live "gotchas" seeded for the demo: (a) some FHIR `code` values have
  **no** entry in the terminology map (Devin must decide: skip + audit vs. fail);
  (b) Observation values arrive as both `valueQuantity` and `valueInteger`;
  (c) `Bundle.entry[].resource.subject.reference` uses `Patient/{mrn}` form that
  must be resolved to an internal participant.
```
