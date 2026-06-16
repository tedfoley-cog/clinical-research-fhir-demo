"""Pre-screening match logic (existing functionality).

Given a trial's eligibility criteria and a participant's normalized diagnoses and
measures, decide whether the participant is a *potential match* worth a
coordinator's review. This is decision-support only: the output is a worklist for
a human, never an enrollment or eligibility determination.

Criterion kinds:
- "diagnosis":    participant has a diagnosis whose category == target
- "measure_max":  participant's latest `target` measure <= threshold
- "measure_min":  participant's latest `target` measure >= threshold
- "min_age":      (current_year - birth_year) >= threshold
"""

from datetime import UTC, datetime

from ..models import EligibilityCriterion, Participant, Trial


def _latest_measure(participant: Participant, key: str) -> float | None:
    values = [m for m in participant.measures if m.measure == key]
    if not values:
        return None
    latest = max(values, key=lambda m: m.effective_at)
    return latest.value


def evaluate_criterion(
    participant: Participant, criterion: EligibilityCriterion
) -> tuple[bool, str]:
    """Return (met, human_readable_reason) for a single criterion."""
    if criterion.kind == "diagnosis":
        has = any(d.category == criterion.target for d in participant.diagnoses)
        return has, f"diagnosis {criterion.target}: {'present' if has else 'absent'}"

    if criterion.kind in ("measure_max", "measure_min"):
        value = _latest_measure(participant, criterion.target)
        if value is None:
            return False, f"{criterion.target}: no value on record"
        if criterion.kind == "measure_max":
            met = value <= (criterion.threshold or 0)
            return met, f"{criterion.target}={value} (<= {criterion.threshold}? {met})"
        met = value >= (criterion.threshold or 0)
        return met, f"{criterion.target}={value} (>= {criterion.threshold}? {met})"

    if criterion.kind == "min_age":
        age = datetime.now(UTC).year - participant.birth_year
        met = age >= (criterion.threshold or 0)
        return met, f"age={age} (>= {criterion.threshold}? {met})"

    return False, f"unknown criterion kind: {criterion.kind}"


def prescreen(participant: Participant, trial: Trial) -> tuple[str, str]:
    """Return (status, rationale) for one participant against one trial."""
    results = [evaluate_criterion(participant, c) for c in trial.criteria]
    reasons = "; ".join(reason for _, reason in results)
    status = "potential_match" if results and all(met for met, _ in results) else "not_matched"
    return status, reasons
