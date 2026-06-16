"""Terminology maps from external clinical codes to internal workbench keys.

These are the *partial* mappings that already exist for the workbench's current
manual data-entry flow. The FHIR ingestion adapter (added by Devin) should reuse
these maps to normalize incoming Condition/Observation codes.

Intentional demo gotcha: not every code that can appear in a FHIR bundle has an
entry here. The adapter must decide what to do with an unmapped code (the
expected behavior is: skip it, but record it in the ingestion audit detail rather
than silently dropping it).

Code systems (verified against authoritative sources — see docs/IMPLEMENTATION_PLAN.md):
- SNOMED CT:   http://snomed.info/sct
- ICD-10-CM:   http://hl7.org/fhir/sid/icd-10-cm
- LOINC:       http://loinc.org
"""

SNOMED = "http://snomed.info/sct"
ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"
LOINC = "http://loinc.org"

# (system, code) -> internal diagnosis category
DIAGNOSIS_CODE_MAP: dict[tuple[str, str], str] = {
    (SNOMED, "254637007"): "nsclc",          # Non-small cell lung cancer
    (ICD10CM, "C34.90"): "nsclc",            # Malignant neoplasm of lung, unspecified
    (ICD10CM, "C34.11"): "nsclc",            # Malignant neoplasm, right upper lobe
    (SNOMED, "254838004"): "breast_cancer",  # Malignant tumor of breast
    (ICD10CM, "C50.911"): "breast_cancer",   # Malignant neoplasm, right female breast
    (SNOMED, "363406005"): "colon_cancer",   # Malignant tumor of colon
    (ICD10CM, "C18.9"): "colon_cancer",      # Malignant neoplasm of colon, unspecified
    # NOTE: prostate cancer codes are intentionally NOT mapped yet (demo gotcha).
}

# (system, code) -> internal measure key
MEASURE_CODE_MAP: dict[tuple[str, str], str] = {
    (LOINC, "89247-1"): "ecog",  # ECOG Performance Status score
    (LOINC, "751-8"): "anc",     # Neutrophils [#/volume] in Blood (absolute count)
}


def map_diagnosis(system: str, code: str) -> str | None:
    """Return the internal diagnosis category for a coded value, or None if unmapped."""
    return DIAGNOSIS_CODE_MAP.get((system, code))


def map_measure(system: str, code: str) -> str | None:
    """Return the internal measure key for a coded value, or None if unmapped."""
    return MEASURE_CODE_MAP.get((system, code))
