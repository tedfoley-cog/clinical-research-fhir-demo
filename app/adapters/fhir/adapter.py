"""FHIR R4 Condition/Observation ingestion adapter.

Parses a FHIR R4 ``Bundle`` of ``Condition`` and ``Observation`` resources and
normalizes them into the workbench data model (``Diagnosis`` / ``MeasureResult``)
using ``app.terminology.mappings``. See ``README.md`` in this package for the
full contract.

Design notes:
- The adapter never crashes the whole bundle because of one bad resource. Each
  resource is processed independently; anything that can't be normalized
  (unknown subject, unmapped code, unsupported type, missing value) is skipped
  and recorded in the audit ``detail`` for traceability.
- Exactly one ``IngestionAudit`` row is written per call, summarizing the
  received / ingested / skipped counts and the outcome.
- Original ``system`` / ``code`` / ``display`` are preserved on the persisted
  rows so coordinators can trace a normalized value back to its source coding.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Diagnosis, IngestionAudit, MeasureResult, Participant
from ...terminology.mappings import map_diagnosis, map_measure

SUPPORTED_RESOURCE_TYPES = ("Condition", "Observation")


class IngestSummary(dict):
    """Plain dict summary returned by :func:`ingest_bundle` (and the endpoint).

    Keys: ``source``, ``resource_type``, ``resources_received``,
    ``resources_ingested``, ``resources_skipped``, ``outcome``, ``detail``,
    ``audit_id``.
    """


def _coding_list(concept: Any) -> list[Mapping[str, Any]]:
    """Return the ``coding`` array of a FHIR CodeableConcept, or an empty list."""
    if isinstance(concept, Mapping):
        coding = concept.get("coding")
        if isinstance(coding, list):
            return [c for c in coding if isinstance(c, Mapping)]
    return []


def _resolve_mrn(reference: Any) -> str | None:
    """Extract the MRN from a ``subject.reference`` like ``Patient/MRN-1001``."""
    if not isinstance(reference, str) or "/" not in reference:
        return None
    resource_type, _, identifier = reference.partition("/")
    if resource_type != "Patient" or not identifier:
        return None
    return identifier


def _observation_value(resource: Mapping[str, Any]) -> tuple[float, str] | None:
    """Read an Observation value from ``valueQuantity`` or ``valueInteger``.

    Returns ``(value, unit)`` or ``None`` if neither is present/usable.
    """
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, Mapping) and quantity.get("value") is not None:
        try:
            return float(quantity["value"]), str(quantity.get("unit", "") or "")
        except (TypeError, ValueError):
            return None
    if "valueInteger" in resource and resource["valueInteger"] is not None:
        try:
            return float(resource["valueInteger"]), ""
        except (TypeError, ValueError):
            return None
    return None


def ingest_bundle(
    db: Session, bundle: Mapping[str, Any], *, source: str = "fhir-bundle"
) -> IngestSummary:
    """Ingest a FHIR R4 Bundle of Condition/Observation resources.

    Persists ``Diagnosis`` / ``MeasureResult`` rows for resources that resolve to
    a known participant and a mapped terminology code, writes exactly one
    ``IngestionAudit`` row, and returns a summary dict.

    Raises ``ValueError`` if ``bundle`` is not a FHIR ``Bundle``.
    """
    if not isinstance(bundle, Mapping) or bundle.get("resourceType") != "Bundle":
        raise ValueError("payload is not a FHIR Bundle (resourceType must be 'Bundle')")

    entries = bundle.get("entry") or []
    resources: list[Mapping[str, Any]] = [
        e["resource"]
        for e in entries
        if isinstance(e, Mapping) and isinstance(e.get("resource"), Mapping)
    ]

    received = len(resources)
    ingested = 0
    seen_types: set[str] = set()
    skip_reasons: list[str] = []

    for resource in resources:
        rtype = resource.get("resourceType")
        if isinstance(rtype, str):
            seen_types.add(rtype)

        if rtype not in SUPPORTED_RESOURCE_TYPES:
            skip_reasons.append(f"unsupported resourceType '{rtype}'")
            continue

        mrn = _resolve_mrn((resource.get("subject") or {}).get("reference"))
        if mrn is None:
            skip_reasons.append(f"{rtype}: missing/invalid subject.reference")
            continue

        participant = db.scalar(select(Participant).where(Participant.mrn == mrn))
        if participant is None:
            skip_reasons.append(f"{rtype}: no participant for subject '{mrn}'")
            continue

        codings = _coding_list(resource.get("code"))
        if not codings:
            skip_reasons.append(f"{rtype} for {mrn}: no code.coding")
            continue

        if rtype == "Condition":
            ingested += _ingest_condition(db, participant, codings, mrn, skip_reasons)
        else:  # Observation
            ingested += _ingest_observation(
                db, participant, resource, codings, mrn, skip_reasons
            )

    skipped = received - ingested
    resource_type = "+".join(sorted(seen_types)) if seen_types else "Bundle"
    outcome = _outcome(received, ingested, skipped)
    detail = _detail(received, ingested, skipped, skip_reasons)

    audit = IngestionAudit(
        source=source,
        resource_type=resource_type,
        resources_received=received,
        resources_ingested=ingested,
        resources_skipped=skipped,
        outcome=outcome,
        detail=detail,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return IngestSummary(
        source=source,
        resource_type=resource_type,
        resources_received=received,
        resources_ingested=ingested,
        resources_skipped=skipped,
        outcome=outcome,
        detail=detail,
        audit_id=audit.id,
    )


def _ingest_condition(
    db: Session,
    participant: Participant,
    codings: list[Mapping[str, Any]],
    mrn: str,
    skip_reasons: list[str],
) -> int:
    """Persist a Diagnosis for the first mapped coding; return 1 if ingested."""
    for coding in codings:
        system = str(coding.get("system", ""))
        code = str(coding.get("code", ""))
        category = map_diagnosis(system, code)
        if category is not None:
            db.add(
                Diagnosis(
                    participant_id=participant.id,
                    category=category,
                    source_system=system,
                    source_code=code,
                    display=str(coding.get("display", "") or ""),
                )
            )
            return 1
    unmapped = ", ".join(f"{c.get('system')}|{c.get('code')}" for c in codings)
    skip_reasons.append(f"Condition for {mrn}: unmapped code(s) {unmapped}")
    return 0


def _ingest_observation(
    db: Session,
    participant: Participant,
    resource: Mapping[str, Any],
    codings: list[Mapping[str, Any]],
    mrn: str,
    skip_reasons: list[str],
) -> int:
    """Persist a MeasureResult for the first mapped coding; return 1 if ingested."""
    for coding in codings:
        system = str(coding.get("system", ""))
        code = str(coding.get("code", ""))
        measure = map_measure(system, code)
        if measure is not None:
            value = _observation_value(resource)
            if value is None:
                skip_reasons.append(
                    f"Observation {measure} for {mrn}: no valueQuantity/valueInteger"
                )
                return 0
            db.add(
                MeasureResult(
                    participant_id=participant.id,
                    measure=measure,
                    value=value[0],
                    unit=value[1],
                    source_system=system,
                    source_code=code,
                )
            )
            return 1
    unmapped = ", ".join(f"{c.get('system')}|{c.get('code')}" for c in codings)
    skip_reasons.append(f"Observation for {mrn}: unmapped code(s) {unmapped}")
    return 0


def _outcome(received: int, ingested: int, skipped: int) -> str:
    """Map counts to an outcome of "success" / "partial" / "error"."""
    if received == 0 or skipped == 0:
        return "success"
    if ingested == 0:
        return "error"
    return "partial"


def _detail(received: int, ingested: int, skipped: int, skip_reasons: list[str]) -> str:
    """Build a human-readable audit detail string."""
    summary = f"Received {received}, ingested {ingested}, skipped {skipped}."
    if skip_reasons:
        summary += " Skips: " + "; ".join(skip_reasons)
    return summary
