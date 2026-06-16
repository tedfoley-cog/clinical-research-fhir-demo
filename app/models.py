"""ORM data model for the clinical research workbench.

Entities:
- Participant       a synthetic research subject (no PHI)
- Diagnosis         a normalized cancer diagnosis for a participant
- MeasureResult     a normalized measurement/observation (e.g. ECOG, ANC)
- Trial             an open research study
- EligibilityCriterion   a single machine-checkable pre-screening criterion
- PreScreenFlag     a cached pre-screening match (support only, human-reviewed)
- IngestionAudit    one row per FHIR ingest attempt (who/what/when/result)

The FHIR ingestion path (adapter + endpoint) is intentionally NOT implemented in
this initial state — Devin adds it during the demo and writes IngestionAudit rows.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    mrn: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    birth_year: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String(16))

    diagnoses: Mapped[list["Diagnosis"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    measures: Mapped[list["MeasureResult"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    # normalized internal category, e.g. "nsclc", "breast_cancer", "colon_cancer"
    category: Mapped[str] = mapped_column(String(64), index=True)
    # the original coded value as received (kept for traceability/audit)
    source_system: Mapped[str] = mapped_column(String(64))
    source_code: Mapped[str] = mapped_column(String(64))
    display: Mapped[str] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    participant: Mapped[Participant] = relationship(back_populates="diagnoses")


class MeasureResult(Base):
    __tablename__ = "measure_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    # normalized internal measure key, e.g. "ecog", "anc"
    measure: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float] = mapped_column()
    unit: Mapped[str] = mapped_column(String(32), default="")
    source_system: Mapped[str] = mapped_column(String(64))
    source_code: Mapped[str] = mapped_column(String(64))
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    participant: Mapped[Participant] = relationship(back_populates="measures")


class Trial(Base):
    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    phase: Mapped[str] = mapped_column(String(16))

    criteria: Mapped[list["EligibilityCriterion"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan"
    )


class EligibilityCriterion(Base):
    __tablename__ = "eligibility_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    trial_id: Mapped[int] = mapped_column(ForeignKey("trials.id"))
    # kind in {"diagnosis", "measure_max", "measure_min", "min_age"}
    kind: Mapped[str] = mapped_column(String(32))
    # target key: a diagnosis category, a measure key, or "" for min_age
    target: Mapped[str] = mapped_column(String(64), default="")
    # threshold for measure_*/min_age criteria; null for diagnosis criteria
    threshold: Mapped[float | None] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(String(200))

    trial: Mapped[Trial] = relationship(back_populates="criteria")


class PreScreenFlag(Base):
    __tablename__ = "prescreen_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    trial_id: Mapped[int] = mapped_column(ForeignKey("trials.id"))
    # "potential_match" or "not_matched" — support only, never a determination
    status: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IngestionAudit(Base):
    __tablename__ = "ingestion_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resources_received: Mapped[int] = mapped_column(Integer, default=0)
    resources_ingested: Mapped[int] = mapped_column(Integer, default=0)
    resources_skipped: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default="")
