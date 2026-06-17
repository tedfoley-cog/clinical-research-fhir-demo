"""FHIR R4 ingestion adapter.

Parses a FHIR R4 ``Bundle`` of ``Condition`` and ``Observation`` resources,
normalizes coded values via :mod:`app.terminology.mappings`, resolves the
subject MRN to an existing :class:`Participant`, and persists
:class:`Diagnosis` / :class:`MeasureResult` rows. Exactly one
:class:`IngestionAudit` row is written per request (see
``app/adapters/fhir/README.md`` for the full contract).

Guardrail: this only normalizes and stores data. It never makes eligibility,
enrollment, or treatment decisions, and it never creates participants.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Diagnosis, IngestionAudit, MeasureResult, Participant
from ...terminology.mappings import map_diagnosis, map_measure

SUPPORTED_RESOURCE_TYPES = ("Condition", "Observation")


@dataclass
class _Counts:
    received: int = 0
    ingested: int = 0
    skipped: int = 0


def _codings(resource: dict) -> list[dict]:
    """Return ``resource.code.coding[]`` (or an empty list)."""
    return (resource.get("code") or {}).get("coding") or []


def _subject_mrn(resource: dict) -> str | None:
    """Extract the MRN from ``subject.reference`` (``Patient/{mrn}``)."""
    reference = (resource.get("subject") or {}).get("reference") or ""
    prefix = "Patient/"
    if reference.startswith(prefix):
        return reference[len(prefix) :]
    return None


def _observation_value(resource: dict) -> tuple[float, str] | None:
    """Return ``(value, unit)`` from ``valueQuantity`` or ``valueInteger``.

    ECOG is reported as ``valueInteger`` and ANC as ``valueQuantity`` in the
    sample data; both must be supported. Returns ``None`` when neither is
    present.
    """
    if "valueQuantity" in resource:
        quantity = resource["valueQuantity"] or {}
        if quantity.get("value") is not None:
            return float(quantity["value"]), str(quantity.get("unit") or "")
    if "valueInteger" in resource:
        return float(resource["valueInteger"]), ""
    return None


def ingest_bundle(
    db: Session, bundle: dict, source: str = "fhir-api"
) -> IngestionAudit:
    """Ingest a FHIR R4 Bundle and persist an audit row.

    The bundle, its resolved rows, and exactly one audit row are added to the
    session and flushed (so the audit ``id`` is populated). Committing is left
    to the caller so ingestion stays a single transaction with the request.
    """
    counts = _Counts()
    skip_notes: list[str] = []

    entries = bundle.get("entry") or []
    for entry in entries:
        resource = entry.get("resource") or {}
        resource_type = resource.get("resourceType")
        if resource_type not in SUPPORTED_RESOURCE_TYPES:
            continue

        counts.received += 1
        resource_id = resource.get("id") or "?"

        mrn = _subject_mrn(resource)
        participant = (
            db.scalar(select(Participant).where(Participant.mrn == mrn))
            if mrn
            else None
        )
        if participant is None:
            counts.skipped += 1
            skip_notes.append(f"{resource_type}/{resource_id}: unknown subject {mrn!r}")
            continue

        if resource_type == "Condition":
            note = _ingest_condition(db, participant, resource)
        else:
            note = _ingest_observation(db, participant, resource)

        if note is None:
            counts.ingested += 1
        else:
            counts.skipped += 1
            skip_notes.append(f"{resource_type}/{resource_id}: {note}")

    outcome = "success" if counts.skipped == 0 else "partial"
    detail = (
        f"Ingested {counts.ingested}/{counts.received} resources."
        if not skip_notes
        else f"Ingested {counts.ingested}/{counts.received}. Skipped: "
        + "; ".join(skip_notes)
    )

    audit = IngestionAudit(
        source=source,
        resource_type="Bundle",
        resources_received=counts.received,
        resources_ingested=counts.ingested,
        resources_skipped=counts.skipped,
        outcome=outcome,
        detail=detail,
    )
    db.add(audit)
    db.flush()
    return audit


def _ingest_condition(
    db: Session, participant: Participant, resource: dict
) -> str | None:
    """Persist a Diagnosis, or return a skip reason if the code is unmapped."""
    for coding in _codings(resource):
        system = coding.get("system") or ""
        code = coding.get("code") or ""
        category = map_diagnosis(system, code)
        if category is not None:
            db.add(
                Diagnosis(
                    participant_id=participant.id,
                    category=category,
                    source_system=system,
                    source_code=code,
                    display=coding.get("display") or "",
                )
            )
            return None
    return f"unmapped code {_first_code(resource)}"


def _ingest_observation(
    db: Session, participant: Participant, resource: dict
) -> str | None:
    """Persist a MeasureResult, or return a skip reason if it can't be mapped."""
    measure: str | None = None
    matched: dict | None = None
    for coding in _codings(resource):
        measure = map_measure(coding.get("system") or "", coding.get("code") or "")
        if measure is not None:
            matched = coding
            break

    if measure is None or matched is None:
        return f"unmapped code {_first_code(resource)}"

    value = _observation_value(resource)
    if value is None:
        return "missing value (no valueQuantity/valueInteger)"

    amount, unit = value
    db.add(
        MeasureResult(
            participant_id=participant.id,
            measure=measure,
            value=amount,
            unit=unit,
            source_system=matched.get("system") or "",
            source_code=matched.get("code") or "",
        )
    )
    return None


def _first_code(resource: dict) -> str:
    """Render the first coding as ``system|code`` for audit detail."""
    codings = _codings(resource)
    if not codings:
        return "(no coding)"
    first = codings[0]
    return f"{first.get('system') or ''}|{first.get('code') or ''}"
