from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PositionTrack(BaseModel):
    id: int
    name: str
    display_name: str
    base_resume: str
    created_at: str


class AnalysisResult(BaseModel):
    ats_score: int = Field(ge=0, le=100)
    hm_score: float = Field(ge=0.0, le=10.0)
    role_summary: str
    key_requirements: list[str]
    your_strengths: list[str]
    gaps_to_address: list[str]
    talking_points: list[str]
    red_flags: list[str]


class AnalyzeRequest(BaseModel):
    job_post: str
    resume: str
    track_id: int


class JobCreate(BaseModel):
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


class JordanRespondRequest(BaseModel):
    session_id: int
    answer: str


class JordanRespondResponse(BaseModel):
    coaching: str
    next_question_text: str
    audio_url: str
    session_complete: bool


class JordanSession(BaseModel):
    id: int
    mode: str
    context_id: int
    transcript: list[dict[str, Any]]
    created_at: str


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
