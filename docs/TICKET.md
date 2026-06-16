# RESWB-412 — Add FHIR-based ingestion of Condition & Observation resources

**Type:** Story &nbsp; **Priority:** High &nbsp; **Component:** Research Workbench / Integrations
**Reporter:** Research Informatics &nbsp; **Assignee:** _Devin_

## Context

Post-Epic, our clinical research workbench should consume FHIR R4 data instead of
relying on manual data entry for trial pre-screening support. Today, coordinators
key in diagnoses and performance-status/lab values by hand, which is slow and
error-prone. We want to ingest synthetic `Condition` and `Observation` resources
(exported as FHIR Bundles) and normalize them into our workbench data model so the
pre-screening worklist reflects current data.

> **Scope guardrail:** this is integration + data-normalization + tooling work.
> The workbench provides *support* to a human coordinator. It must not make
> eligibility, enrollment, or treatment decisions. No PHI — synthetic data only.

## Acceptance Criteria

1. **AC1 — Ingestion endpoint.** `POST /api/ingest/fhir` accepts a FHIR R4
   `Bundle` of `Condition` and `Observation` resources and returns a summary
   (received / ingested / skipped counts + outcome).
2. **AC2 — Adapter.** Implement `app/adapters/fhir/adapter.py` per the contract in
   `app/adapters/fhir/README.md`.
3. **AC3 — Normalization.** Use `app/terminology/mappings.py` to map coded
   diagnoses/observations to internal categories/measures, preserving the original
   `system`/`code`/`display` for traceability.
4. **AC4 — Subject resolution.** Resolve `subject.reference` (`Patient/{mrn}`) to
   an existing participant; skip (do not create) participants that don't exist.
5. **AC5 — Unmapped codes.** Skip resources with codes not in the terminology map,
   count them as skipped, and record the unmapped `system|code` in the audit
   detail. Do not fail the whole bundle.
6. **AC6 — Value handling.** Read Observation values from both `valueQuantity` and
   `valueInteger` (ECOG is an integer, ANC is a quantity).
7. **AC7 — Audit.** Write exactly one `IngestionAudit` row per ingest request.
8. **AC8 — Tests.** Add `tests/test_fhir_ingestion.py` covering a clean Condition
   bundle, a clean Observation bundle, an unmapped-code case, and audit creation.
   Update the existing 501 test in `tests/test_api.py`.
9. **AC9 — Docs.** Update `README.md` (and any relevant docs) to describe ingestion.
10. **AC10 — PR.** Open a PR summarizing the change, assumptions made, and reviewer
    notes (especially the unmapped-code handling decision).

## Test data

`sample_data/fhir/condition_bundle.json` and
`sample_data/fhir/observation_bundle.json`. After ingesting both, the
`LUNG-2024-017` worklist should surface the lung-cancer participants who meet the
ECOG/ANC/age criteria as **potential matches** for coordinator review.
