"""Seed the workbench with synthetic participants, trials, and criteria.

Run with:  python -m app.seed

This seeds *demographics and study definitions only*. Participants have no
diagnoses or measurements yet — in the current (manual) process that clinical
data is keyed in by hand and lags behind. Once FHIR ingestion is implemented,
running it against sample_data/fhir/ populates the diagnoses/measures and the
pre-screening worklist lights up.

All names and MRNs are fictional. No PHI.
"""

from .database import Base, SessionLocal, engine
from .models import EligibilityCriterion, Participant, Trial

PARTICIPANTS = [
    # mrn, display_name, birth_year, sex
    ("MRN-1001", "Alex Rivera", 1968, "male"),
    ("MRN-1002", "Jordan Lee", 1975, "female"),
    ("MRN-1003", "Sam Patel", 1959, "male"),
    ("MRN-1004", "Casey Kim", 1980, "female"),
    ("MRN-1005", "Morgan Diaz", 1972, "male"),
    ("MRN-1006", "Taylor Brooks", 1990, "female"),
]

TRIALS = [
    {
        "code": "LUNG-2024-017",
        "title": "Phase II study of a targeted agent in advanced NSCLC",
        "phase": "II",
        "criteria": [
            ("diagnosis", "nsclc", None, "Confirmed non-small cell lung cancer"),
            ("measure_max", "ecog", 1, "ECOG performance status <= 1"),
            ("measure_min", "anc", 1.5, "Absolute neutrophil count >= 1.5 x10^9/L"),
            ("min_age", "", 18, "Age >= 18 years"),
        ],
    },
    {
        "code": "BRST-2024-003",
        "title": "Phase III adjuvant therapy study in breast cancer",
        "phase": "III",
        "criteria": [
            ("diagnosis", "breast_cancer", None, "Confirmed breast cancer"),
            ("measure_max", "ecog", 1, "ECOG performance status <= 1"),
            ("min_age", "", 18, "Age >= 18 years"),
        ],
    },
]


def seed() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for mrn, name, birth_year, sex in PARTICIPANTS:
            db.add(Participant(mrn=mrn, display_name=name, birth_year=birth_year, sex=sex))

        for t in TRIALS:
            trial = Trial(code=t["code"], title=t["title"], phase=t["phase"])
            for kind, target, threshold, description in t["criteria"]:
                trial.criteria.append(
                    EligibilityCriterion(
                        kind=kind,
                        target=target,
                        threshold=threshold,
                        description=description,
                    )
                )
            db.add(trial)

        db.commit()
        print(f"Seeded {len(PARTICIPANTS)} participants and {len(TRIALS)} trials.")
        print("Clinical data (diagnoses/observations) is empty until FHIR ingestion runs.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
