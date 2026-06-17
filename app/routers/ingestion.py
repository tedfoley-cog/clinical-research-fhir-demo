"""FHIR ingestion endpoint.

``POST /api/ingest/fhir`` accepts a FHIR R4 ``Bundle`` of ``Condition`` and
``Observation`` resources, normalizes coded values via
``app.terminology.mappings``, resolves ``subject.reference`` (``Patient/{mrn}``)
to an existing participant, persists ``Diagnosis`` / ``MeasureResult`` rows, and
writes one ``IngestionAudit`` row per request. The parsing/normalization logic
lives in ``app.adapters.fhir.adapter`` (see ``app/adapters/fhir/README.md``).

``GET /api/ingest/audit`` returns the ingestion audit trail so the workbench can
show ingestion history.
"""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters.fhir.adapter import ingest_bundle
from ..database import get_db
from ..models import IngestionAudit
from ..schemas import AuditOut, IngestSummary

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


@router.post("/fhir", response_model=IngestSummary)
def ingest_fhir(
    bundle: dict = Body(..., description="FHIR R4 Bundle of Condition/Observation resources"),
    db: Session = Depends(get_db),
) -> IngestSummary:
    """Ingest a FHIR R4 Bundle of Condition/Observation resources.

    Normalizes and stores the data and records an audit row. This is
    decision-support tooling only — it never makes eligibility, enrollment, or
    treatment decisions.
    """
    if bundle.get("resourceType") != "Bundle":
        raise HTTPException(
            status_code=400,
            detail="Expected a FHIR Bundle (resourceType == 'Bundle').",
        )

    audit = ingest_bundle(db, bundle)
    db.commit()
    return IngestSummary(
        audit_id=audit.id,
        resources_received=audit.resources_received,
        resources_ingested=audit.resources_ingested,
        resources_skipped=audit.resources_skipped,
        outcome=audit.outcome,
        detail=audit.detail,
    )


@router.get("/audit", response_model=list[AuditOut])
def list_audit(db: Session = Depends(get_db)) -> list[IngestionAudit]:
    """Return ingestion audit history (most recent first)."""
    return list(
        db.scalars(select(IngestionAudit).order_by(IngestionAudit.received_at.desc()))
    )
