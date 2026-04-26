from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import auth
import database
import jordan
from analyzer import analyze_job_post, fix_resume_for_job
from models import (
    AnalyzeRequest,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    ForgotPasswordRequest,
    HealthResponse,
    JobCreate,
    JobUpdate,
    JordanRespondRequest,
    JordanStartRequest,
    MessageResponse,
    ResetPasswordRequest,
    ResetPasswordVerifyResponse,
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "media-src 'self' blob:; "
            "frame-ancestors 'none';"
        )
        return response


def _trusted_hosts() -> list[str]:
    """Return the allowed hostnames for TrustedHostMiddleware."""
    configured = os.getenv("ALLOWED_HOSTS", "").strip()
    if configured:
        return [host.strip() for host in configured.split(",") if host.strip()]
    hosts = {"localhost", "127.0.0.1", "testserver"}
    render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_hostname:
        hosts.add(render_hostname)
    return sorted(hosts)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _fallback_display_name(email: str) -> str:
    """Build a basic first-name fallback from the email local part."""
    local_part = email.split("@", 1)[0]
    first_chunk = local_part.split(".", 1)[0]
    return first_chunk.capitalize()


def _serialize_user(user: UserRecord) -> UserResponse:
    """Return the public user payload."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name or _fallback_display_name(str(user.email)),
        resume=user.resume or "",
        has_resume=bool((user.resume or "").strip()),
        created_at=user.created_at,
    )


def _token_response(user: UserRecord, response: Response) -> AuthTokenResponse:
    """Create the standard auth response payload."""
    token = auth.create_access_token(subject=user.email, user_id=user.id)
    auth.set_auth_cookie(response, token)
    return AuthTokenResponse(access_token=token, user=_serialize_user(user))


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserRecord | None:
    """Return the current user if a valid cookie or bearer token is present."""
    token = request.cookies.get(auth.COOKIE_NAME)
    if not token and credentials is not None:
        token = credentials.credentials
    if not token:
        return None
    try:
        payload = auth.decode_access_token(token)
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
async def analyze(request: AnalyzeRequest, current_user: UserRecord = Depends(get_current_user)) -> dict:
    """Analyze a pasted job post against the current resume text."""
    track = database.get_track(request.track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    resume = (request.resume or "").strip()
    if not resume:
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
async def register(request: AuthRegisterRequest, response: Response) -> AuthTokenResponse:
    """Register a new user and return an auth token while setting the session cookie."""
    if database.get_user_by_email(str(request.email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    display_name = request.name or _fallback_display_name(str(request.email))
    try:
        user = database.create_user(
            email=str(request.email),
            password_hash=auth.get_password_hash(request.password),
            display_name=display_name,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    return _token_response(user, response)


@app.post("/auth/login", response_model=AuthTokenResponse)
async def login(request: AuthLoginRequest, response: Response) -> AuthTokenResponse:
    """Authenticate a user and return an auth token while setting the session cookie."""
    user = database.get_user_by_email(str(request.email))
    if user is None or not auth.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _token_response(user, response)


@app.post("/auth/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear the auth cookie for the current browser session."""
    auth.clear_auth_cookie(response)
    return {"status": "logged out"}


@app.post("/auth/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest) -> MessageResponse:
    """Send a password reset email when the account exists."""
    # Post-launch: add per-IP and per-email rate limiting for reset attempts.
    message = "If that email exists, a reset link is on its way."
    user = database.get_user_by_email(str(request.email))
    if user is None:
        return MessageResponse(message=message)

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    database.create_password_reset_token(user_id=user.id, token=token, expires_at=expires_at)
    reset_url = auth.build_password_reset_url(token)
    try:
        auth.send_reset_email(str(user.email), reset_url)
    except Exception:
        logging.exception("Failed to send password reset email for user_id=%s", user.id)
    return MessageResponse(message=message)


@app.get("/auth/reset-password/verify", response_model=ResetPasswordVerifyResponse)
async def verify_reset_password(token: str = Query(min_length=1)) -> ResetPasswordVerifyResponse:
    """Validate a password reset token."""
    reset_token = database.get_password_reset_token(token)
    if reset_token is None or not database.password_reset_token_is_valid(reset_token):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    return ResetPasswordVerifyResponse(valid=True)


@app.post("/auth/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest) -> MessageResponse:
    """Set a new password using a valid reset token."""
    reset_token = database.get_password_reset_token(request.token)
    if reset_token is None or not database.password_reset_token_is_valid(reset_token):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = database.update_user_password(
        reset_token.user_id,
        auth.get_password_hash(request.password),
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    database.mark_password_reset_token_used(request.token)
    return MessageResponse(message="Password updated. Sign in.")


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


@app.get("/forgot-password")
async def forgot_password_page() -> FileResponse:
    """Serve the forgot-password page."""
    return _page("forgot-password.html")


@app.get("/reset-password")
async def reset_password_page() -> FileResponse:
    """Serve the reset-password page."""
    return _page("reset-password.html")
