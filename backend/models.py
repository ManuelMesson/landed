from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class PositionTrack(BaseModel):
    id: int
    name: str
    display_name: str
    base_resume: str
    created_at: str


class AnalysisResult(BaseModel):
    ats_score: int = Field(ge=0, le=100)
    hm_score: float = Field(ge=0.0, le=10.0)
    company_name: str = ""
    role_title: str = ""
    role_summary: str
    key_requirements: list[str]
    your_strengths: list[str]
    gaps_to_address: list[str]
    talking_points: list[str]
    red_flags: list[str]
    company_values: list[str] = []
    interview_style: str = ""


class AnalyzeRequest(BaseModel):
    job_post: str
    resume: str | None = None
    track_id: int


class JobCreate(BaseModel):
    user_id: int | None = None
    track_id: int
    company: str
    role: str
    job_post: str
    date_applied: str
    ats_score: int
    hm_score: float
    analysis: AnalysisResult
    interview_prep: str | None = ""
    notes: str | None = ""


class JobUpdate(BaseModel):
    status: Literal["Applied", "Screening", "Interview", "Offer", "Rejected", "Ghosted"] | None = None
    notes: str | None = None


class JobRecord(BaseModel):
    id: int
    user_id: int | None = None
    track_id: int
    company: str
    role: str
    job_post: str
    date_applied: str
    status: str
    ats_score: int
    hm_score: float
    analysis: AnalysisResult
    interview_prep: str
    notes: str
    created_at: str


class JobWithTrack(JobRecord):
    track_name: str
    track_display_name: str


class TrackResumeUpdate(BaseModel):
    resume: str


class JordanStartRequest(BaseModel):
    mode: Literal["job", "track"]
    job_id: int | None = None
    track_id: int | None = None


class JordanStartResponse(BaseModel):
    session_id: int
    question_text: str
    audio_url: str
    prefetched_audio_urls: list[str] = Field(default_factory=list)
    display_name: str = ""
    warmup_text: str = ""
    context_summary: str = ""
    readiness_score: float = 0
    session_count: int = 0
    known_weaknesses: list[str] = []
    fit_level: str = "good"
    company_type: str = "other"


class JordanRespondRequest(BaseModel):
    session_id: int
    answer: str


class JordanRespondResponse(BaseModel):
    coaching: str
    next_question_text: str
    audio_url: str
    session_complete: bool
    summary: str | None = None
    readiness_score: float | None = None


class CandidateProfile(BaseModel):
    id: int
    track_key: str
    readiness_score: float = 0
    session_count: int = 0
    known_strengths: list[str] = []
    known_weaknesses: list[str] = []
    patterns: list[str] = []
    last_session_summary: str = ""
    last_updated: str = ""


class JordanSession(BaseModel):
    id: int
    user_id: int | None = None
    mode: str
    context_id: int
    transcript: list[dict[str, Any]]
    created_at: str


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuthRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str


class ResumeUpdateRequest(BaseModel):
    resume: str


class UserRecord(BaseModel):
    id: int
    email: EmailStr
    password_hash: str
    display_name: str = Field(default="", max_length=50)
    resume: str = ""
    created_at: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str = Field(default="", max_length=50)
    resume: str = ""
    has_resume: bool = False
    created_at: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
