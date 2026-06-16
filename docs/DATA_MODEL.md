# Data Model

SQLite via SQLAlchemy 2.0. All tables are created automatically on startup; run
`python -m app.seed` to (re)load synthetic participants, trials, and criteria.

```
Participant 1───* Diagnosis
Participant 1───* MeasureResult
Trial       1───* EligibilityCriterion
PreScreenFlag   *───1 Participant, *───1 Trial   (cached worklist; support only)
IngestionAudit                                   (one row per FHIR ingest)
```

## Tables

### participants
| column | type | notes |
|---|---|---|
| id | int PK | |
| mrn | str unique | synthetic medical record number, e.g. `MRN-1001` |
| display_name | str | fictional |
| birth_year | int | used for the `min_age` criterion |
| sex | str | |

### diagnoses
Normalized cancer diagnoses. Populated by FHIR ingestion (added live).
| column | type | notes |
|---|---|---|
| category | str | internal key, e.g. `nsclc`, `breast_cancer`, `colon_cancer` |
| source_system / source_code / display | str | original coded value (traceability) |

### measure_results
Normalized measurements. Populated by FHIR ingestion (added live).
| column | type | notes |
|---|---|---|
| measure | str | internal key, e.g. `ecog`, `anc` |
| value | float | |
| unit | str | |
| source_system / source_code | str | original coded value |

### trials / eligibility_criteria
A trial has machine-checkable criteria. `kind` ∈ {`diagnosis`, `measure_max`,
`measure_min`, `min_age`}; `target` is a diagnosis category or measure key;
`threshold` applies to `measure_*`/`min_age`.

### ingestion_audit
One row per `POST /api/ingest/fhir`: `source`, `resource_type`,
`resources_received`, `resources_ingested`, `resources_skipped`, `outcome`,
`detail` (includes unmapped codes). Written by the adapter Devin implements.

## Terminology mappings

`app/terminology/mappings.py` holds the partial code→internal maps. Prostate
cancer codes are intentionally absent so the ingest path exercises unmapped-code
handling (skip + audit, never crash).
