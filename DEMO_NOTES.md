# Demo Cheat Sheet — Post-Epic FHIR Ingestion

## Setup (do this before joining the call)
- [ ] Clone repo and confirm `pip install -e ".[dev]" && python -m app.seed && pytest` passes
- [ ] Have `docs/TICKET.md` open to copy the ticket prompt into Devin

## Demo Flow
1. Open a fresh Devin session against the repo; paste the ticket text from `docs/TICKET.md`
2. Talking point: "This workbench does trial pre-screening *support* — it surfaces candidates for a human coordinator, never makes eligibility/treatment decisions. Right now FHIR ingestion returns 501 — the team enters data manually. Devin is going to close that gap."
3. Watch Devin inspect the repo: data model, terminology maps, sample FHIR bundles, the adapter contract in `app/adapters/fhir/README.md`
4. Talking point: "Notice the unmapped prostate-cancer code in the sample data — Devin has to decide what to do. The expected behavior is skip and audit, not crash."
5. Devin runs the workbench inside its session (`python -m app.seed && uvicorn app.main:app`), POSTs the sample bundles, and the worklist updates live in the browser tab — Alex Rivera and Casey Kim surface as potential NSCLC matches
6. Devin opens a PR with assumptions and reviewer notes — show the diff and the audit trail
