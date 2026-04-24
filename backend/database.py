from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from models import AnalysisResult, CandidateProfile, JobCreate, JobRecord, JobWithTrack, JordanSession, PositionTrack

MANUEL_RESUME = """
Name: Manuel Messon-Roque
Experience:
- Barista, Compass Group (Amazon HQ), Feb 2025-Present
- E-Commerce & Operations Manager, Nufours Bakery, Feb 2022-Jan 2025
- Prep Cook/Kitchen Ops, Reef Kitchens, Jul 2018-Jan 2022
- Front-End Developer, Geniuslink, Feb 2017-Jul 2018
Projects:
- Taquigrafia (AI Transcription Tool) - WhisperX + AssemblyAI
- DirtyBean (Coffee Discovery SaaS) - React, FastAPI, full-stack
- Landed (AI Job Search Command Center) - FastAPI, Claude API, SQLite
Skills: Customer Onboarding, Customer Success, Issue Resolution, HubSpot/Zendesk/Intercom, AI Tools, Google Workspace, Slack, Process Improvement, Stakeholder Communication
Education: Associate of Business, Seattle Central College, Dec 2025
""".strip()

SEEDED_TRACKS = [
    {
        "name": "customer-success",
        "display_name": "Customer Success Specialist",
        "base_resume": MANUEL_RESUME,
    },
    {
        "name": "onboarding-implementation",
        "display_name": "Onboarding & Implementation Specialist",
        "base_resume": MANUEL_RESUME,
    },
    {
        "name": "product-support",
        "display_name": "Product Support Specialist",
        "base_resume": MANUEL_RESUME,
    },
]


def repo_root() -> Path:
    """Return the project root path."""
    return Path(__file__).resolve().parent.parent


def get_db_path() -> Path:
    """Resolve the sqlite database path."""
    env_path = os.getenv("LANDED_DB_PATH")
    if env_path:
        return Path(env_path)
    return repo_root() / "data" / "landed.db"


def _connect() -> sqlite3.Connection:
    """Create a sqlite connection with row access by name."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a sqlite connection and close it on exit."""
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    """Create tables and seed default tracks."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS position_tracks (
              id INTEGER PRIMARY KEY,
              name TEXT UNIQUE,
              display_name TEXT,
              base_resume TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS applications (
              id INTEGER PRIMARY KEY,
              track_id INTEGER REFERENCES position_tracks(id),
              company TEXT,
              role TEXT,
              job_post TEXT,
              date_applied TEXT,
              status TEXT DEFAULT 'Applied',
              ats_score INTEGER,
              hm_score REAL,
              analysis TEXT,
              interview_prep TEXT,
              notes TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS jordan_sessions (
              id INTEGER PRIMARY KEY,
              mode TEXT,
              context_id INTEGER,
              transcript TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS candidate_profiles (
              id INTEGER PRIMARY KEY,
              track_key TEXT UNIQUE,
              readiness_score REAL DEFAULT 0,
              session_count INTEGER DEFAULT 0,
              known_strengths TEXT DEFAULT '[]',
              known_weaknesses TEXT DEFAULT '[]',
              patterns TEXT DEFAULT '[]',
              last_session_summary TEXT DEFAULT '',
              last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        count = connection.execute("SELECT COUNT(*) FROM position_tracks").fetchone()[0]
        if count == 0:
            connection.executemany(
                """
                INSERT INTO position_tracks (name, display_name, base_resume)
                VALUES (:name, :display_name, :base_resume)
                """,
                SEEDED_TRACKS,
            )


def _track_from_row(row: sqlite3.Row) -> PositionTrack:
    """Convert a sqlite row into a track model."""
    return PositionTrack(**dict(row))


def list_tracks() -> list[PositionTrack]:
    """Return all seeded position tracks."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, display_name, base_resume, created_at FROM position_tracks ORDER BY id"
        ).fetchall()
    return [_track_from_row(row) for row in rows]


def get_track(track_id: int) -> PositionTrack | None:
    """Return a track by id."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, display_name, base_resume, created_at FROM position_tracks WHERE id = ?",
            (track_id,),
        ).fetchone()
    return _track_from_row(row) if row else None


def update_track_resume(track_id: int, resume: str) -> PositionTrack | None:
    """Update a track's base resume and return the track."""
    with get_connection() as connection:
        connection.execute(
            "UPDATE position_tracks SET base_resume = ? WHERE id = ?",
            (resume, track_id),
        )
    return get_track(track_id)


def _job_from_row(row: sqlite3.Row) -> JobWithTrack:
    """Convert a job row and joined track fields into a response model."""
    payload = dict(row)
    payload["analysis"] = AnalysisResult.model_validate(json.loads(payload["analysis"]))
    payload["interview_prep"] = payload.get("interview_prep") or ""
    payload["notes"] = payload.get("notes") or ""
    return JobWithTrack(**payload)


def create_job(job: JobCreate) -> JobRecord:
    """Persist an application record."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO applications (
              track_id, company, role, job_post, date_applied, status,
              ats_score, hm_score, analysis, interview_prep, notes
            ) VALUES (?, ?, ?, ?, ?, 'Applied', ?, ?, ?, ?, ?)
            """,
            (
                job.track_id,
                job.company,
                job.role,
                job.job_post,
                job.date_applied,
                job.ats_score,
                job.hm_score,
                job.analysis.model_dump_json(),
                job.interview_prep or "",
                job.notes or "",
            ),
        )
        job_id = int(cursor.lastrowid)
    stored = get_job(job_id)
    if stored is None:
        raise RuntimeError("Failed to load newly created job")
    return JobRecord(**stored.model_dump(exclude={"track_name", "track_display_name"}))


def list_jobs(track_id: int | None = None) -> list[JobWithTrack]:
    """Return application rows, optionally filtered by track."""
    query = """
        SELECT
          a.id, a.track_id, a.company, a.role, a.job_post, a.date_applied, a.status,
          a.ats_score, a.hm_score, a.analysis, a.interview_prep, a.notes, a.created_at,
          t.name AS track_name, t.display_name AS track_display_name
        FROM applications a
        JOIN position_tracks t ON t.id = a.track_id
    """
    params: tuple[Any, ...] = ()
    if track_id is not None:
        query += " WHERE a.track_id = ?"
        params = (track_id,)
    query += " ORDER BY a.created_at DESC, a.id DESC"
    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_job_from_row(row) for row in rows]


def get_job(job_id: int) -> JobWithTrack | None:
    """Return a single application with joined track fields."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
              a.id, a.track_id, a.company, a.role, a.job_post, a.date_applied, a.status,
              a.ats_score, a.hm_score, a.analysis, a.interview_prep, a.notes, a.created_at,
              t.name AS track_name, t.display_name AS track_display_name
            FROM applications a
            JOIN position_tracks t ON t.id = a.track_id
            WHERE a.id = ?
            """,
            (job_id,),
        ).fetchone()
    return _job_from_row(row) if row else None


def update_job(job_id: int, *, status: str | None = None, notes: str | None = None) -> JobWithTrack | None:
    """Patch mutable application fields."""
    fields: list[str] = []
    values: list[Any] = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if not fields:
        return get_job(job_id)
    values.append(job_id)
    with get_connection() as connection:
        connection.execute(f"UPDATE applications SET {', '.join(fields)} WHERE id = ?", tuple(values))
    return get_job(job_id)


def create_jordan_session(mode: str, context_id: int, transcript: list[dict[str, Any]]) -> JordanSession:
    """Persist a Jordan session and return it."""
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO jordan_sessions (mode, context_id, transcript) VALUES (?, ?, ?)",
            (mode, context_id, json.dumps(transcript)),
        )
        session_id = int(cursor.lastrowid)
    session = get_jordan_session(session_id)
    if session is None:
        raise RuntimeError("Failed to load Jordan session")
    return session


def get_jordan_session(session_id: int) -> JordanSession | None:
    """Return one Jordan session."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, mode, context_id, transcript, created_at FROM jordan_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["transcript"] = json.loads(payload["transcript"])
    return JordanSession(**payload)


def update_jordan_session(session_id: int, transcript: list[dict[str, Any]]) -> JordanSession | None:
    """Replace transcript content for a Jordan session."""
    with get_connection() as connection:
        connection.execute(
            "UPDATE jordan_sessions SET transcript = ? WHERE id = ?",
            (json.dumps(transcript), session_id),
        )
    return get_jordan_session(session_id)


def get_candidate_profile(track_key: str) -> CandidateProfile | None:
    """Return the candidate profile for a track key, or None if no sessions yet."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM candidate_profiles WHERE track_key = ?",
            (track_key,),
        ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["known_strengths"] = json.loads(payload["known_strengths"])
    payload["known_weaknesses"] = json.loads(payload["known_weaknesses"])
    payload["patterns"] = json.loads(payload["patterns"])
    return CandidateProfile(**payload)


def upsert_candidate_profile(
    track_key: str,
    readiness_score: float,
    known_strengths: list[str],
    known_weaknesses: list[str],
    patterns: list[str],
    last_session_summary: str,
) -> CandidateProfile:
    """Create or update the candidate profile for a track."""
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT session_count FROM candidate_profiles WHERE track_key = ?",
            (track_key,),
        ).fetchone()
        session_count = (existing["session_count"] + 1) if existing else 1
        connection.execute(
            """
            INSERT INTO candidate_profiles
              (track_key, readiness_score, session_count, known_strengths, known_weaknesses, patterns, last_session_summary, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(track_key) DO UPDATE SET
              readiness_score = excluded.readiness_score,
              session_count = excluded.session_count,
              known_strengths = excluded.known_strengths,
              known_weaknesses = excluded.known_weaknesses,
              patterns = excluded.patterns,
              last_session_summary = excluded.last_session_summary,
              last_updated = CURRENT_TIMESTAMP
            """,
            (
                track_key,
                readiness_score,
                session_count,
                json.dumps(known_strengths),
                json.dumps(known_weaknesses),
                json.dumps(patterns),
                last_session_summary,
            ),
        )
    result = get_candidate_profile(track_key)
    if result is None:
        raise RuntimeError("Failed to load candidate profile")
    return result
