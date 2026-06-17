"""FHIR ingestion endpoint.

`POST /api/ingest/fhir` accepts a FHIR R4 Bundle of Condition/Observation
resources, normalizes coded values via `app.terminology.mappings`, resolves
`subject.reference` (Patient/{mrn}) to an existing Participant, persists
Diagnosis / MeasureResult rows, writes one IngestionAudit row, and returns a
summary. The parsing/normalization logic lives in `app.adapters.fhir.adapter`.

The read endpoint for the audit trail (`GET /api/ingest/audit`) lets the
workbench show ingestion history.

Guardrail: ingestion only normalizes and stores synthetic data. It never makes
eligibility, enrollment, or treatment decisions; the pre-screening worklist
remains a human-reviewed support tool.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters.fhir.adapter import ingest_bundle
from ..database import get_db
from ..models import IngestionAudit
from ..schemas import AuditOut

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


@router.post("/fhir")
async def ingest_fhir(request: Request, db: Session = Depends(get_db)) -> dict:
    """Ingest a FHIR R4 Bundle of Condition/Observation resources.

    Returns a summary with received/ingested/skipped counts and an outcome. One
    IngestionAudit row is written per request (see GET /api/ingest/audit).
    """
    bundle = await request.json()
    try:
        return ingest_bundle(db, bundle, source="api")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditOut])
def list_audit(db: Session = Depends(get_db)) -> list[IngestionAudit]:
    """Return ingestion audit history (most recent first)."""
    return list(
        db.scalars(select(IngestionAudit).order_by(IngestionAudit.received_at.desc()))
    )
