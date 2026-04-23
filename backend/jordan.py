from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from pathlib import Path

import database
from models import JordanRespondResponse, JordanStartResponse

LOGGER = logging.getLogger(__name__)
GREETING = "Hey, I'm Jordan. Let's make sure you're ready for this one. Tell me — what draws you to this role?"
MIN_EXCHANGES = 3


def audio_dir() -> Path:
    """Return the directory used for generated Jordan audio."""
    env_path = os.getenv("LANDED_AUDIO_DIR")
    path = Path(env_path) if env_path else database.repo_root() / "static" / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _write_edge_tts(text: str, output_path: Path) -> None:
    """Write mp3 audio using edge_tts when available."""
    import edge_tts

    communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
    await communicate.save(str(output_path))


async def synthesize_audio(text: str) -> str:
    """Create a stable audio file for text and return its public URL."""
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    output_path = audio_dir() / f"jordan-{digest}.mp3"
    if not output_path.exists():
        try:
            if os.getenv("LANDED_DISABLE_TTS") == "1":
                raise RuntimeError("TTS disabled for this environment")
            await _write_edge_tts(text=text, output_path=output_path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Falling back to placeholder audio: %s", exc)
            output_path.write_bytes(b"ID3Landed placeholder audio")
    return f"/static/audio/{output_path.name}"


def build_context(mode: str, context_id: int) -> str:
    """Build a short summary for either track or job coaching."""
    if mode == "job":
        job = database.get_job(context_id)
        if job is None:
            raise ValueError("Job not found")
        gap_text = ", ".join(job.analysis.gaps_to_address[:3])
        return f"Job prep for {job.company} {job.role}. Focus gaps: {gap_text or 'specific examples and metrics'}."
    track = database.get_track(context_id)
    if track is None:
        raise ValueError("Track not found")
    return f"Track prep for {track.display_name}. Focus on customer empathy, clear communication, and measurable outcomes."


def build_next_questions(mode: str, context_summary: str) -> list[str]:
    """Return the first question plus a couple of follow-ups."""
    return [
        GREETING,
        f"Give me one specific example from your background that proves you can handle this. Context: {context_summary}",
        "What's the clearest metric, result, or customer outcome you can point to from that example?",
        "Now tighten that into a concise interview answer: situation, action, result.",
    ]


def answer_is_vague(answer: str) -> bool:
    """Detect answers that lack specifics, metrics, or examples."""
    lowered = answer.lower()
    vague_terms = {"helped", "worked", "good", "great", "stuff", "things", "support", "customers"}
    has_metric = any(char.isdigit() for char in lowered)
    has_example_marker = any(term in lowered for term in {"for example", "for instance", "when", "because", "after"})
    token_count = len(answer.split())
    vague_hits = sum(1 for term in vague_terms if term in lowered)
    return token_count < 18 or (not has_metric and not has_example_marker) or vague_hits >= 2


def _challenge(answer: str) -> str:
    """Return push-back coaching for vague answers."""
    return (
        "That's a start, but it still sounds broad. Give me a concrete example with a specific result or number. "
        "What changed because of your work?"
    )


def _affirm(answer: str) -> str:
    """Return concise coaching for stronger answers."""
    return (
        "Better. Keep the answer grounded in customer impact, your action, and the measurable result. "
        "Trim extra setup and lead with the outcome."
    )


async def start_session(mode: str, context_id: int) -> JordanStartResponse:
    """Create a Jordan session with prefetched audio for the first two questions."""
    context_summary = build_context(mode=mode, context_id=context_id)
    questions = build_next_questions(mode=mode, context_summary=context_summary)
    transcript = [{"speaker": "jordan", "text": question} for question in questions[:2]]
    session = database.create_jordan_session(mode=mode, context_id=context_id, transcript=transcript)
    return JordanStartResponse(
        session_id=session.id,
        question_text=questions[0],
        audio_url=await synthesize_audio(questions[0]),
        prefetched_audio_urls=[await synthesize_audio(questions[1])],
    )


async def respond(session_id: int, answer: str) -> JordanRespondResponse:
    """Append a user answer, coach it, and deliver the next question."""
    session = database.get_jordan_session(session_id)
    if session is None:
        raise ValueError("Session not found")
    transcript = list(session.transcript)
    transcript.append({"speaker": "user", "text": answer})
    coaching = _challenge(answer) if answer_is_vague(answer) else _affirm(answer)
    exchange_count = sum(1 for item in transcript if item["speaker"] == "user")
    session_complete = exchange_count >= MIN_EXCHANGES
    next_question = (
        "Good. Close by telling me why this role and this company fit your trajectory right now."
        if session_complete
        else "Push this further. What did you do, how did you do it, and what was the result?"
    )
    transcript.append({"speaker": "jordan", "text": next_question, "coaching": coaching})
    database.update_jordan_session(session_id=session_id, transcript=transcript)
    return JordanRespondResponse(
        coaching=coaching,
        next_question_text=next_question,
        audio_url=await synthesize_audio(next_question),
        session_complete=session_complete,
    )
