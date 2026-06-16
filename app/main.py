"""FastAPI application entrypoint for the clinical research workbench."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import ingestion, participants, trials

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Clinical Research Workbench",
    version="0.1.0",
    description=(
        "Trial pre-screening *support* for research coordinators. Synthetic data "
        "only. This service surfaces candidate matches for human review; it does "
        "not make eligibility, enrollment, or treatment decisions."
    ),
)

app.include_router(participants.router)
app.include_router(trials.router)
app.include_router(ingestion.router)


@app.on_event("startup")
def _ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
