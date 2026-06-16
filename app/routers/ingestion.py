"""FHIR ingestion endpoint.

>>> THIS IS THE GAP THE DEMO CLOSES. <<<

In the initial state, FHIR ingestion is not wired up: posting a Bundle returns
501 Not Implemented. The research team currently enters Condition/Observation
data by hand, which does not scale post-Epic.

During the demo, Devin implements `app/adapters/fhir/adapter.py` and replaces the
body of `ingest_fhir` below so that it:
  1. parses the incoming FHIR R4 Bundle (Condition + Observation entries),
  2. normalizes coded values via `app.terminology.mappings`,
  3. resolves `subject.reference` (Patient/{mrn}) to a Participant,
  4. persists Diagnosis / MeasureResult rows,
  5. writes an IngestionAudit row (received/ingested/skipped + unmapped codes),
  6. returns a summary.

The read endpoint for the audit trail (`GET /api/ingest/audit`) already exists so
the workbench can show ingestion history once Devin wires up writes.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IngestionAudit
from ..schemas import AuditOut

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


@router.post("/fhir", status_code=501)
async def ingest_fhir(request: Request, db: Session = Depends(get_db)) -> dict:
    """Ingest a FHIR R4 Bundle of Condition/Observation resources.

    Not implemented in the initial state — see module docstring. Devin implements
    this during the demo.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "FHIR ingestion is not implemented. Implement app/adapters/fhir/adapter.py "
            "and wire it into this endpoint (see app/adapters/fhir/README.md)."
        ),
    )


@router.get("/audit", response_model=list[AuditOut])
def list_audit(db: Session = Depends(get_db)) -> list[IngestionAudit]:
    """Return ingestion audit history (most recent first)."""
    return list(
        db.scalars(select(IngestionAudit).order_by(IngestionAudit.received_at.desc()))
    )
