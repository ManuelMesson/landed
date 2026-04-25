from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

import auth
import database
import jordan
from analyzer import analyze_job_post, fix_resume_for_job
from models import (
    AnalyzeRequest,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    HealthResponse,
    JobCreate,
    JobUpdate,
    JordanRespondRequest,
    JordanStartRequest,
    ResumeUpdateRequest,
    TrackResumeUpdate,
    UserRecord,
    UserResponse,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
STATIC = ROOT / "static"
AUDIO = STATIC / "audio"

AUDIO.mkdir(parents=True, exist_ok=True)
bearer_scheme = HTTPBearer(auto_error=False)


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


def _serialize_user(user: UserRecord) -> UserResponse:
    """Return the public user payload."""
    return UserResponse(
        id=user.id,
        email=user.email,
        resume=user.resume or "",
        has_resume=bool((user.resume or "").strip()),
        created_at=user.created_at,
    )


def _token_response(user: UserRecord) -> AuthTokenResponse:
    """Create the standard auth response payload."""
    token = auth.create_access_token(subject=user.email, user_id=user.id)
    return AuthTokenResponse(access_token=token, user=_serialize_user(user))


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserRecord | None:
    """Return the current user if a valid bearer token is present."""
    if credentials is None:
        return None
    try:
        payload = auth.decode_access_token(credentials.credentials)
        user_id = int(payload.get("user_id"))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except (ValueError, auth.JWTError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc
    user = database.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_user(
    current_user: UserRecord | None = Depends(get_optional_current_user),
) -> UserRecord:
    """Require a valid authenticated user."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return current_user


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return an application health payload."""
    return HealthResponse(status="ok")


@app.post("/analyze")
async def analyze(request: AnalyzeRequest, current_user: UserRecord | None = Depends(get_optional_current_user)) -> dict:
    """Analyze a pasted job post against the current resume text."""
    track = database.get_track(request.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    resume = (request.resume or "").strip()
    if not resume and current_user is not None:
        resume = (current_user.resume or "").strip()
    if not resume:
        raise HTTPException(status_code=422, detail="resume required")
    analysis = analyze_job_post(
        job_post=request.job_post,
        resume=resume,
        track_label=track.display_name,
    )
    return analysis.model_dump()


@app.post("/auth/register", response_model=AuthTokenResponse, status_code=201)
async def register(request: AuthRegisterRequest) -> AuthTokenResponse:
    """Register a new user and return a bearer token."""
    if database.get_user_by_email(str(request.email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        user = database.create_user(
            email=str(request.email),
            password_hash=auth.get_password_hash(request.password),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    return _token_response(user)


@app.post("/auth/login", response_model=AuthTokenResponse)
async def login(request: AuthLoginRequest) -> AuthTokenResponse:
    """Authenticate a user and return a bearer token."""
    user = database.get_user_by_email(str(request.email))
    if user is None or not auth.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _token_response(user)


@app.get("/auth/me", response_model=UserResponse)
async def auth_me(current_user: UserRecord = Depends(get_current_user)) -> UserResponse:
    """Return the current authenticated user."""
    return _serialize_user(current_user)


@app.put("/auth/resume", response_model=UserResponse)
async def update_auth_resume(
    request: ResumeUpdateRequest,
    current_user: UserRecord = Depends(get_current_user),
) -> UserResponse:
    """Persist the current user's resume."""
    user = database.update_user_resume(current_user.id, request.resume)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(user)


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
async def get_jobs(
    track_id: int | None = Query(default=None),
    current_user: UserRecord = Depends(get_current_user),
) -> list[dict]:
    """List applications, optionally filtered by track."""
    return [job.model_dump(mode="json") for job in database.list_jobs(user_id=current_user.id, track_id=track_id)]


@app.post("/jobs", status_code=201)
async def create_job(request: JobCreate, current_user: UserRecord = Depends(get_current_user)) -> dict:
    """Create an application entry for the tracker."""
    track = database.get_track(request.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    job = database.create_job(request.model_copy(update={"user_id": current_user.id}))
    return job.model_dump(mode="json")


@app.patch("/jobs/{job_id}")
async def patch_job(job_id: int, request: JobUpdate, current_user: UserRecord = Depends(get_current_user)) -> dict:
    """Update job status or notes."""
    job = database.update_job(job_id=job_id, user_id=current_user.id, status=request.status, notes=request.notes)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json")


@app.get("/jobs/{job_id}")
async def get_job(job_id: int, current_user: UserRecord = Depends(get_current_user)) -> dict:
    """Return one application row including analysis."""
    job = database.get_job(job_id, user_id=current_user.id)
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
async def jordan_profile(mode: str, context_id: int, current_user: UserRecord = Depends(get_current_user)) -> dict:
    """Return Jordan coaching history for a job or track."""
    track_key = jordan.make_track_key(user_id=current_user.id, mode=mode, context_id=context_id)
    profile = database.get_candidate_profile(track_key)
    if profile is None:
        return {"session_count": 0, "readiness_score": 0, "known_weaknesses": [], "known_strengths": [], "patterns": []}
    return profile.model_dump()


@app.post("/jordan/session/start")
async def jordan_start(request: JordanStartRequest, current_user: UserRecord = Depends(get_current_user)) -> dict:
    """Start a Jordan prep session for a track or job."""
    context_id = request.job_id if request.mode == "job" else request.track_id
    if context_id is None:
        raise HTTPException(status_code=422, detail="Missing context id")
    try:
        session = await jordan.start_session(mode=request.mode, context_id=context_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session.model_dump(mode="json")


@app.post("/jordan/session/respond")
async def jordan_respond(request: JordanRespondRequest, current_user: UserRecord = Depends(get_current_user)) -> dict:
    """Continue a Jordan prep session."""
    try:
        response = await jordan.respond(session_id=request.session_id, answer=request.answer, user_id=current_user.id)
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


@app.get("/login")
async def login_page() -> FileResponse:
    """Serve the login page."""
    return _page("login.html")


@app.get("/register")
async def register_page() -> FileResponse:
    """Serve the registration page."""
    return _page("register.html")
