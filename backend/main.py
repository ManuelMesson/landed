from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import database
import jordan
from analyzer import analyze_job_post, fix_resume_for_job
from models import (
    AnalyzeRequest,
    HealthResponse,
    JobCreate,
    JobUpdate,
    JordanRespondRequest,
    JordanStartRequest,
    TrackResumeUpdate,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
STATIC = ROOT / "static"
AUDIO = STATIC / "audio"

AUDIO.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize storage on app startup."""
    AUDIO.mkdir(parents=True, exist_ok=True)
    database.init_db()
    yield


app = FastAPI(title="Landed", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return an application health payload."""
    return HealthResponse(status="ok")


@app.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    """Analyze a pasted job post against the current resume text."""
    track = database.get_track(request.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    analysis = analyze_job_post(
        job_post=request.job_post,
        resume=request.resume,
        track_label=track.display_name,
    )
    return analysis.model_dump()


@app.get("/tracks")
async def get_tracks() -> list[dict]:
    """Return all position tracks."""
    return [track.model_dump() for track in database.list_tracks()]


@app.put("/tracks/{track_id}/resume")
async def update_resume(track_id: int, request: TrackResumeUpdate) -> dict:
    """Persist an edited base resume for a track."""
    track = database.update_track_resume(track_id=track_id, resume=request.resume)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return track.model_dump()


@app.get("/jobs")
async def get_jobs(track_id: int | None = Query(default=None)) -> list[dict]:
    """List applications, optionally filtered by track."""
    return [job.model_dump(mode="json") for job in database.list_jobs(track_id=track_id)]


@app.post("/jobs", status_code=201)
async def create_job(request: JobCreate) -> dict:
    """Create an application entry for the tracker."""
    track = database.get_track(request.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    job = database.create_job(request)
    return job.model_dump(mode="json")


@app.patch("/jobs/{job_id}")
async def patch_job(job_id: int, request: JobUpdate) -> dict:
    """Update job status or notes."""
    job = database.update_job(job_id=job_id, status=request.status, notes=request.notes)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json")


@app.get("/jobs/{job_id}")
async def get_job(job_id: int) -> dict:
    """Return one application row including analysis."""
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json")


@app.post("/resume-fix")
async def resume_fix(request: dict) -> dict:
    """Return 3 specific resume edits tailored to a job post."""
    job_post = request.get("job_post", "")
    resume = request.get("resume", "")
    gaps = request.get("gaps", [])
    key_requirements = request.get("key_requirements", [])
    if not job_post or not resume:
        raise HTTPException(status_code=422, detail="job_post and resume required")
    fixes = fix_resume_for_job(job_post=job_post, resume=resume, gaps=gaps, key_requirements=key_requirements)
    return {"fixes": fixes}


@app.get("/jordan/profile/{mode}/{context_id}")
async def jordan_profile(mode: str, context_id: int) -> dict:
    """Return Jordan coaching history for a job or track."""
    track_key = f"{mode}:{context_id}"
    profile = database.get_candidate_profile(track_key)
    if profile is None:
        return {"session_count": 0, "readiness_score": 0, "known_weaknesses": [], "known_strengths": [], "patterns": []}
    return profile.model_dump()


@app.post("/jordan/session/start")
async def jordan_start(request: JordanStartRequest) -> dict:
    """Start a Jordan prep session for a track or job."""
    context_id = request.job_id if request.mode == "job" else request.track_id
    if context_id is None:
        raise HTTPException(status_code=422, detail="Missing context id")
    try:
        session = await jordan.start_session(mode=request.mode, context_id=context_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session.model_dump(mode="json")


@app.post("/jordan/session/respond")
async def jordan_respond(request: JordanRespondRequest) -> dict:
    """Continue a Jordan prep session."""
    try:
        response = await jordan.respond(session_id=request.session_id, answer=request.answer)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return response.model_dump(mode="json")


def _page(name: str) -> FileResponse:
    """Return one of the frontend html pages."""
    return FileResponse(FRONTEND / name)


@app.get("/")
async def index() -> FileResponse:
    """Serve the main analyzer page."""
    return _page("index.html")


@app.get("/tracker")
async def tracker() -> FileResponse:
    """Serve the application tracker page."""
    return _page("tracker.html")


@app.get("/jordan")
async def jordan_page() -> FileResponse:
    """Serve the Jordan prep page."""
    return _page("jordan.html")
