"""Tests for the existing pre-screening match logic."""

from datetime import datetime

from app.models import Diagnosis, EligibilityCriterion, MeasureResult, Participant, Trial
from app.services.prescreen import prescreen


def _participant(birth_year=1970, diagnoses=(), measures=()):
    p = Participant(
        mrn="MRN-TEST", display_name="Test Subject", birth_year=birth_year, sex="other"
    )
    p.diagnoses = [
        Diagnosis(category=c, source_system="test", source_code="x", display=c)
        for c in diagnoses
    ]
    p.measures = [
        MeasureResult(
            measure=m,
            value=v,
            unit="",
            source_system="test",
            source_code="x",
            effective_at=datetime(2025, 1, 1),
        )
        for m, v in measures
    ]
    return p


def _lung_trial():
    trial = Trial(code="LUNG-TEST", title="Lung", phase="II")
    trial.criteria = [
        EligibilityCriterion(kind="diagnosis", target="nsclc", threshold=None, description="dx"),
        EligibilityCriterion(kind="measure_max", target="ecog", threshold=1, description="ecog"),
        EligibilityCriterion(kind="measure_min", target="anc", threshold=1.5, description="anc"),
        EligibilityCriterion(kind="min_age", target="", threshold=18, description="age"),
    ]
    return trial


def test_full_match():
    p = _participant(birth_year=1970, diagnoses=("nsclc",), measures=(("ecog", 1), ("anc", 2.1)))
    status, _ = prescreen(p, _lung_trial())
    assert status == "potential_match"


def test_fails_on_high_ecog():
    p = _participant(birth_year=1970, diagnoses=("nsclc",), measures=(("ecog", 2), ("anc", 2.1)))
    status, rationale = prescreen(p, _lung_trial())
    assert status == "not_matched"
    assert "ecog" in rationale


def test_missing_measure_is_not_match():
    p = _participant(birth_year=1970, diagnoses=("nsclc",), measures=())
    status, rationale = prescreen(p, _lung_trial())
    assert status == "not_matched"
    assert "no value on record" in rationale


def test_wrong_diagnosis():
    p = _participant(diagnoses=("breast_cancer",), measures=(("ecog", 0), ("anc", 3.0)))
    status, _ = prescreen(p, _lung_trial())
    assert status == "not_matched"


def test_underage():
    p = _participant(birth_year=datetime.now().year - 5, diagnoses=("nsclc",),
                     measures=(("ecog", 0), ("anc", 3.0)))
    status, rationale = prescreen(p, _lung_trial())
    assert status == "not_matched"
    assert "age" in rationale
