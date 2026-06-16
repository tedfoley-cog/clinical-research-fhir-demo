"""Participant read endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Participant
from ..schemas import ParticipantDetail, ParticipantSummary

router = APIRouter(prefix="/api/participants", tags=["participants"])


@router.get("", response_model=list[ParticipantSummary])
def list_participants(db: Session = Depends(get_db)) -> list[Participant]:
    return list(db.scalars(select(Participant).order_by(Participant.id)))


@router.get("/{participant_id}", response_model=ParticipantDetail)
def get_participant(participant_id: int, db: Session = Depends(get_db)) -> Participant:
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="participant not found")
    return participant
