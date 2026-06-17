"""Pydantic response/request schemas for the workbench API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DiagnosisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    source_system: str
    source_code: str
    display: str


class MeasureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    measure: str
    value: float
    unit: str


class ParticipantSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mrn: str
    display_name: str
    birth_year: int
    sex: str


class ParticipantDetail(ParticipantSummary):
    diagnoses: list[DiagnosisOut] = []
    measures: list[MeasureOut] = []


class CriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    target: str
    threshold: float | None
    description: str


class TrialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    phase: str
    criteria: list[CriterionOut] = []


class PreScreenResult(BaseModel):
    participant_id: int
    mrn: str
    display_name: str
    status: str
    rationale: str


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    received_at: datetime
    source: str
    resource_type: str
    resources_received: int
    resources_ingested: int
    resources_skipped: int
    outcome: str
    detail: str


class IngestSummary(BaseModel):
    """Summary returned by POST /api/ingest/fhir (mirrors the audit row)."""

    audit_id: int
    resources_received: int
    resources_ingested: int
    resources_skipped: int
    outcome: str
    detail: str
