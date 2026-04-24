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

SYSTEM_PROMPT = """You are Jordan, a direct and warm interview coach for job seekers.

Your job is to prepare the candidate for real interviews through back-and-forth conversation.

Rules:
- Be concise. One coaching observation + one follow-up question per response. Never more.
- Push back on vague answers. If the answer has no specific example, metric, or concrete outcome, challenge it: "That's a start — give me a specific example with a result."
- Affirm progress when the answer improves — then push further.
- Adapt to what the candidate actually said. Never repeat the same question or coaching.
- Ask questions relevant to the specific role and their actual answer.
- Sound like a real person, not a chatbot. Warm but not soft.
- Never be sycophantic. "Great answer!" is not allowed.
- Format: coaching observation first (1-2 sentences), then follow-up question (1 sentence ending in ?)."""


def audio_dir() -> Path:
    env_path = os.getenv("LANDED_AUDIO_DIR")
    path = Path(env_path) if env_path else database.repo_root() / "static" / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _write_edge_tts(text: str, output_path: Path) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
    await communicate.save(str(output_path))


async def synthesize_audio(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    output_path = audio_dir() / f"jordan-{digest}.mp3"
    if not output_path.exists():
        try:
            if os.getenv("LANDED_DISABLE_TTS") == "1":
                raise RuntimeError("TTS disabled")
            await _write_edge_tts(text=text, output_path=output_path)
        except Exception as exc:
            LOGGER.warning("Falling back to placeholder audio: %s", exc)
            output_path.write_bytes(b"ID3Landed placeholder audio")
    return f"/static/audio/{output_path.name}"


def build_context(mode: str, context_id: int) -> str:
    if mode == "job":
        job = database.get_job(context_id)
        if job is None:
            raise ValueError("Job not found")
        gap_text = ", ".join(job.analysis.gaps_to_address[:3]) if job.analysis else ""
        return f"Job prep for {job.company} — {job.role}. Key gaps to address: {gap_text or 'specific examples and metrics'}."
    track = database.get_track(context_id)
    if track is None:
        raise ValueError("Track not found")
    return f"Track prep for {track.display_name}. Focus on customer empathy, ownership, and measurable outcomes."


def _call_claude_coaching(transcript: list[dict], context_summary: str, session_complete: bool) -> tuple[str, str]:
    """Call Claude API to generate real coaching + next question from full conversation history."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed") from exc

    client = Anthropic(api_key=api_key)

    # Build conversation for Claude
    messages = []

    # Add context as first assistant message
    messages.append({
        "role": "user",
        "content": f"Context: {context_summary}\n\nStart the coaching session."
    })
    messages.append({
        "role": "assistant",
        "content": GREETING
    })

    # Replay the conversation history (skip the greeting which is already in messages)
    user_turns = [t for t in transcript if t["speaker"] == "user"]
    jordan_turns = [t for t in transcript if t["speaker"] == "jordan" and t["text"] != GREETING]

    for i, user_turn in enumerate(user_turns):
        messages.append({"role": "user", "content": user_turn["text"]})
        # Add Jordan's previous response if it exists (i.e. not the last user turn)
        if i < len(jordan_turns):
            messages.append({"role": "assistant", "content": jordan_turns[i]["text"]})

    # If session is ending, add a closer instruction
    if session_complete:
        messages.append({
            "role": "user",
            "content": "[This is the final exchange. Give your last coaching note and ask them to close strong: why this company, why now.]"
        })

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    full_response = response.content[0].text.strip()

    # Split coaching observation from question
    # Last sentence ending with ? is the question, everything before is coaching
    sentences = [s.strip() for s in full_response.replace("\n", " ").split(". ") if s.strip()]
    question_parts = []
    coaching_parts = []

    for sentence in sentences:
        if sentence.endswith("?"):
            question_parts.append(sentence)
        else:
            coaching_parts.append(sentence)

    if question_parts:
        coaching = ". ".join(coaching_parts).strip()
        next_question = question_parts[-1]
        if not coaching:
            coaching = next_question
            next_question = question_parts[-1]
    else:
        # Claude returned a single block — use it all as the question
        coaching = full_response
        next_question = full_response

    return coaching, next_question


def _fallback_coaching(answer: str, exchange_count: int) -> tuple[str, str]:
    """Static fallback if Claude API fails."""
    words = answer.lower().split()
    has_metric = any(c.isdigit() for c in answer)
    has_example = any(w in answer.lower() for w in ["when", "because", "after", "example", "result"])

    if len(words) < 15 or (not has_metric and not has_example):
        coaching = "That's a start — but it's still broad. Give me a specific situation with an actual result."
        question = "Walk me through a concrete example: what was the situation, what did you do, and what changed?"
    elif exchange_count >= MIN_EXCHANGES:
        coaching = "Better. Tighten it: lead with the outcome, cut the setup."
        question = "Tell me why this specific company and this specific role fit where you're headed right now."
    else:
        coaching = "Good. Keep the focus on your action and the measurable impact."
        question = "Now apply that same thinking to a customer challenge you've handled. What happened?"

    return coaching, question


async def start_session(mode: str, context_id: int) -> JordanStartResponse:
    context_summary = build_context(mode=mode, context_id=context_id)
    transcript = [{"speaker": "jordan", "text": GREETING}]
    session = database.create_jordan_session(mode=mode, context_id=context_id, transcript=transcript)
    return JordanStartResponse(
        session_id=session.id,
        question_text=GREETING,
        audio_url=await synthesize_audio(GREETING),
        prefetched_audio_urls=[],
    )


async def respond(session_id: int, answer: str) -> JordanRespondResponse:
    session = database.get_jordan_session(session_id)
    if session is None:
        raise ValueError("Session not found")

    transcript = list(session.transcript)
    transcript.append({"speaker": "user", "text": answer})

    exchange_count = sum(1 for t in transcript if t["speaker"] == "user")
    session_complete = exchange_count >= MIN_EXCHANGES

    # Get context from session
    context_summary = build_context(mode=session.mode, context_id=session.context_id)

    # Try Claude API first, fall back to static
    try:
        coaching, next_question = _call_claude_coaching(
            transcript=transcript,
            context_summary=context_summary,
            session_complete=session_complete,
        )
    except Exception as exc:
        LOGGER.warning("Jordan Claude call failed, using fallback: %s", exc)
        coaching, next_question = _fallback_coaching(answer=answer, exchange_count=exchange_count)

    transcript.append({"speaker": "jordan", "text": next_question, "coaching": coaching})
    database.update_jordan_session(session_id=session_id, transcript=transcript)

    return JordanRespondResponse(
        coaching=coaching,
        next_question_text=next_question,
        audio_url=await synthesize_audio(next_question),
        session_complete=session_complete,
    )
