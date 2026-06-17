# FHIR Adapter Contract

Implemented in `adapter.py` (`ingest_bundle`) and wired into `POST /api/ingest/fhir`
(`app/routers/ingestion.py`). This document is the contract the adapter follows.

## Expected behavior

Input: a FHIR R4 `Bundle` (JSON) whose entries are `Condition` and/or
`Observation` resources. Examples live in `sample_data/fhir/`.

The adapter should:

1. **Parse** each `Bundle.entry[].resource`, branching on `resourceType`.
2. **Resolve the subject.** `resource.subject.reference` is of the form
   `Patient/{mrn}`. Map the MRN to an existing `Participant`. If no participant
   matches, skip the resource and record it (do not create participants here).
3. **Normalize codes** using `app.terminology.mappings`:
   - `Condition.code.coding[]` → `map_diagnosis(system, code)` → `Diagnosis.category`
   - `Observation.code.coding[]` → `map_measure(system, code)` → `MeasureResult.measure`
   Keep the original `system`/`code`/`display` for traceability.
4. **Extract Observation values** from either `valueQuantity.value` or
   `valueInteger` (both appear in the sample data — ECOG is an integer, ANC is a
   quantity).
5. **Handle unmapped codes** gracefully: skip the resource, increment the skipped
   count, and include the unmapped `system|code` in the audit `detail`. Never
   crash the whole bundle because of one unknown code.
6. **Persist** `Diagnosis` / `MeasureResult` rows.
7. **Audit**: write exactly one `IngestionAudit` row per request capturing
   `resources_received`, `resources_ingested`, `resources_skipped`, `outcome`
   ("success"/"partial"/"error"), and a human-readable `detail`.
8. **Return** a JSON summary matching the audit counts.

## Out of scope (guardrails)

- No eligibility, enrollment, or treatment decisions. Ingestion only normalizes
  and stores data; the pre-screening worklist remains a human-reviewed support tool.
- No PHI: all sample data is synthetic.

## Tests to add

`tests/test_fhir_ingestion.py` should cover: a clean Condition bundle, a clean
Observation bundle, a bundle containing an unmapped code (prostate cancer — see
`mappings.py`), and verification that an `IngestionAudit` row is written.
