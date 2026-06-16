"""Trial + pre-screening endpoints (support only, human-in-the-loop)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Participant, Trial
from ..schemas import PreScreenResult, TrialOut
from ..services.prescreen import prescreen

router = APIRouter(prefix="/api/trials", tags=["trials"])


@router.get("", response_model=list[TrialOut])
def list_trials(db: Session = Depends(get_db)) -> list[Trial]:
    return list(db.scalars(select(Trial).order_by(Trial.id)))


@router.get("/{trial_id}/prescreen", response_model=list[PreScreenResult])
def prescreen_trial(trial_id: int, db: Session = Depends(get_db)) -> list[PreScreenResult]:
    """Return the pre-screening worklist for a trial.

    NOTE: these are *candidate* matches for coordinator review, not eligibility
    or enrollment decisions.
    """
    trial = db.get(Trial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="trial not found")

    results: list[PreScreenResult] = []
    for participant in db.scalars(select(Participant).order_by(Participant.id)):
        status, rationale = prescreen(participant, trial)
        results.append(
            PreScreenResult(
                participant_id=participant.id,
                mrn=participant.mrn,
                display_name=participant.display_name,
                status=status,
                rationale=rationale,
            )
        )
    return results
