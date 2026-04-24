from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from pathlib import Path

import database
from models import JordanRespondResponse, JordanStartResponse

LOGGER = logging.getLogger(__name__)
GREETING_INTRO = "Hey, I'm Jordan."
MIN_EXCHANGES = 5

SYSTEM_PROMPT = """You are Jordan, a direct and warm interview coach. Your job is to prepare this specific candidate for this specific role in a structured session.

## Your mission for this session
You have a session map: the analyzer found the candidate's key gaps and talking points. Work through them systematically — don't ask random questions. By the end of the session, the candidate should have ONE polished STAR answer they can say verbatim in the real interview.

## Session structure (follow this arc)
- Exchange 1: Warm but specific — you already heard their background answer. Acknowledge one thing from it, then pivot to the first real pressure point. Not generic coaching, but not the hardest question yet either. Example: "That makes sense. Given your background in [X], this role is going to test whether you can [specific thing]. Walk me through a time you did that."
- Exchanges 2-3: Hit the biggest gap directly. Push for STAR structure. Name their actual companies.
- Exchange 4: Pattern recognition — call out what keeps showing up (vague answers, no metrics, team instead of "I"). Be direct.
- Exchange 5: Polish one complete answer until it's tight. Say "Let's build your answer for X question right now. Give me the full version."

## Answer structure coaching (use this every time)
If an answer is vague or out of order, call it out and name the fix:
- Lead with the RESULT first, then walk back to the situation
- STAR = Situation (1 sentence) → Task (1 sentence) → Action (2-3 sentences with specifics) → Result (number or clear outcome)
- If they buried the result: "You gave me the story before the punch line. Lead with what changed."
- If they have no number: "You need a number. Even an estimate. How many customers? What percentage? What timeframe?"
- If they're too long: "Cut the setup in half. The interviewer doesn't need the context — they need your action and the result."

## Pattern recognition (call this out mid-session)
- If they deflect a metric question twice: "I've asked for a number twice. You keep avoiding it. That's going to hurt you. Give me something — 10 customers? 20%? Anything real."
- If answers keep being generic: "You're answering for a generic CS role. This is [company]. Tie it to what they specifically care about."
- If they talk about the team instead of themselves: "I need what YOU did. Not 'we.' What was your specific contribution?"

## Company-specific rules
- If Amazon: always ask a Leadership Principle question. Frame it as "Amazon will ask: tell me about a time you [LP behavior]. Which principle does your answer demonstrate?"
- If a startup: push on ownership and speed. "What did you ship without being asked to?"
- If enterprise SaaS: push on multi-stakeholder complexity. "Who else was in the room and how did you manage them?"

## Rules
- One coaching note + one follow-up question per response. Never more.
- Reference their actual resume items (specific company names, projects) every time.
- Never ask the same question twice.
- No "Great answer!" — acknowledge improvement briefly, then push further.
- Format: coaching observation first (1-2 sentences), then next question (1 sentence ending in ?).
- NEVER ask meta questions like "Are you ready to start?" or "What do you need?" — the session is already running.
- If the candidate's answer is very short or off-topic, say so directly: "That's not an answer. Give me a real example." Then ask the question again.
- Always stay in coach mode. Never break character."""


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


TRACK_FOCUS = {
    "customer-success": (
        "Customer Success Specialist prep. Interviewers will test: (1) how you retain and grow accounts, "
        "(2) how you handle churn risk and escalations, (3) your ability to run QBRs and prove value to customers, "
        "(4) specific metrics — NPS, churn rate, expansion revenue, CSAT. "
        "They want someone who proactively drives customer outcomes, not someone who just responds to tickets."
    ),
    "onboarding-implementation": (
        "Onboarding & Implementation Specialist prep. Interviewers will test: (1) how you manage time-to-value "
        "for new customers, (2) how you handle a customer who's confused, behind schedule, or resistant to change, "
        "(3) your ability to manage multiple implementations simultaneously with different timelines, "
        "(4) specific metrics — time-to-first-value, onboarding completion rate, customer satisfaction at go-live. "
        "They want someone who drives adoption fast and doesn't let customers get stuck."
    ),
    "product-support": (
        "Product Support Specialist prep. Interviewers will test: (1) how you diagnose and resolve technical issues, "
        "(2) how you handle frustrated or escalating customers under pressure, "
        "(3) your ability to document issues and improve processes so the same problem doesn't repeat, "
        "(4) specific metrics — first response time, ticket resolution rate, CSAT, escalation rate. "
        "They want someone who solves problems fast and makes the product better in the process."
    ),
}


def build_context(mode: str, context_id: int) -> tuple[str, str]:
    """Returns (context_summary, resume_text)."""
    if mode == "job":
        job = database.get_job(context_id)
        if job is None:
            raise ValueError("Job not found")
        gap_text = ", ".join(job.analysis.gaps_to_address[:3]) if job.analysis else ""
        strength_text = ", ".join(job.analysis.your_strengths[:2]) if job.analysis else ""
        company_values = job.analysis.company_values if job.analysis else []
        interview_style = job.analysis.interview_style if job.analysis else ""
        track = database.get_track(job.track_id) if job.track_id else None
        resume = track.base_resume if track else ""
        track_focus = TRACK_FOCUS.get(track.name, "") if track else ""
        talking_points = job.analysis.talking_points if job.analysis else []
        key_requirements = job.analysis.key_requirements if job.analysis else []

        company_section = ""
        if company_values:
            company_section += f"\nCompany values/principles: {', '.join(company_values[:5])}."
        if interview_style:
            company_section += f"\nInterview style: {interview_style}."

        # Company-specific question hints
        company_lower = (job.company or "").lower()
        company_questions = ""
        if "amazon" in company_lower:
            company_questions = "\nAmazon-specific: Must ask a Leadership Principle behavioral question. Common ones: 'Tell me about a time you disagreed with a decision' (Have Backbone), 'Tell me about a time you failed' (Learn and Be Curious), 'Tell me about a time you improved a process' (Invent and Simplify)."
        elif any(w in company_lower for w in ["salesforce", "servicenow", "workday"]):
            company_questions = "\nEnterprise SaaS: Ask about multi-stakeholder selling, navigating complex organizations, and long implementation cycles."
        elif any(w in company_lower for w in ["startup", "series", "seed"]) or job.analysis and job.analysis.hm_score < 6:
            company_questions = "\nStartup: Ask about ownership without direction, shipping fast, wearing multiple hats, handling ambiguity."

        session_map = ""
        if talking_points:
            session_map += f"\nSession map — talking points to prove: {'; '.join(talking_points[:3])}."
        if key_requirements:
            session_map += f"\nMust test these requirements: {', '.join(key_requirements[:3])}."

        # Include the actual job post so Jordan can reference specific language
        job_post_section = ""
        if job.job_post:
            # Trim to first 800 chars to stay within context limits but keep the most important parts
            job_excerpt = job.job_post[:800].strip()
            job_post_section = f"\n\nActual job post (read this to reference specific requirements and language in your questions):\n{job_excerpt}"

        summary = (
            f"Job prep: {job.company} — {job.role}. "
            f"{track_focus}"
            f"{company_section}"
            f"{company_questions}"
            f"{session_map} "
            f"Candidate's gaps: {gap_text or 'specific examples and metrics'}. "
            f"Candidate's strengths: {strength_text or 'operational experience, customer-facing work'}."
            f"{job_post_section}"
        )
        return summary, resume
    track = database.get_track(context_id)
    if track is None:
        raise ValueError("Track not found")
    track_focus = TRACK_FOCUS.get(track.name, f"Prep for {track.display_name} roles.")
    summary = f"Track prep: {track.display_name}. {track_focus}"
    return summary, track.base_resume


def _call_claude_coaching(transcript: list[dict], context_summary: str, resume: str, session_complete: bool, exchange_count: int = 0) -> tuple[str, str]:
    """Call Claude API to generate real coaching + next question from full conversation history."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed") from exc

    client = Anthropic(api_key=api_key)

    # Build conversation directly from transcript
    resume_section = f"\n\nCandidate resume:\n{resume}" if resume else ""
    progress_note = f"\n\n[Session progress: exchange {exchange_count} of {MIN_EXCHANGES}. {'Final exchange — build the polished answer.' if session_complete else 'Keep working through the session map.'}]"
    messages = [
        {
            "role": "user",
            "content": f"Context: {context_summary}{resume_section}{progress_note}\n\nStart the mock interview session."
        }
    ]

    # Replay the full transcript as alternating assistant/user turns
    for turn in transcript:
        role = "assistant" if turn["speaker"] == "jordan" else "user"
        messages.append({"role": role, "content": turn["text"]})

    # Ensure messages alternate properly (Claude requires user/assistant alternation)
    # If last message is not from user, something is wrong — bail to fallback
    if messages[-1]["role"] != "user":
        raise ValueError("Transcript does not end on a user turn")

    # If session is closing, tell Claude via the system prompt extension (not fake turns)
    system = SYSTEM_PROMPT
    if session_complete:
        system += (
            "\n\nThis is the FINAL exchange. Do two things: "
            "(1) Give your sharpest coaching note on the pattern you noticed across this whole session — one thing that kept showing up. "
            "(2) Build their polished answer with them: say 'Here's the one answer you should have ready verbatim: [write a complete 3-4 sentence STAR answer grounded in their actual resume experience and the specific role]. Say this back to me.' "
            "End with that full polished answer they can memorize."
        )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=system,
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
        # coaching = everything that isn't a question; question = last sentence with ?
        # Earlier question sentences (if any) get folded into coaching so they're not lost
        extra_questions = question_parts[:-1]
        coaching_sentences = coaching_parts + extra_questions
        coaching = ". ".join(coaching_sentences).strip()
        next_question = question_parts[-1]
    else:
        # Claude returned a statement block — treat last sentence as question, rest as coaching
        coaching = ". ".join(sentences[:-1]).strip() if len(sentences) > 1 else ""
        next_question = sentences[-1] if sentences else full_response

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


def _build_opening_question(context_summary: str, resume: str) -> str:
    """Generate a job-specific opening question — not a generic 'what draws you here?'"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Hey, I'm Jordan. Tell me what specifically about this role made you apply."
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system=(
                "You are Jordan, an interview coach opening a mock interview session. "
                "Generate ONE warm but specific opening question — the kind a good hiring manager asks in the first 2 minutes to understand who you're talking to. "
                "Ask them to walk you through their background briefly, and tie it to something specific about this role or company. "
                "Do NOT go straight to the hardest gap question — that comes later. "
                "Do NOT ask generic 'tell me about yourself' — make it specific to the role context. "
                "Example tone: 'Hey, I'm Jordan. Walk me through what you've been doing for the past couple of years, and tell me what specifically about [company/role] made you go after it.' "
                "Adjust for the actual company and role. Start with 'Hey, I'm Jordan.' Under 2 sentences."
            ),
            messages=[{"role": "user", "content": f"Context: {context_summary}\n\nResume:\n{resume}"}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        LOGGER.warning("Opening question Claude call failed: %s", exc)
        return "Hey, I'm Jordan. Walk me through what you've been doing for the past couple of years, and tell me what specifically about this role made you go after it."


def _build_warmup(context_summary: str, resume: str) -> str:
    """Generate a Jordan warmup briefing using real resume context."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return context_summary
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=280,
            system=(
                "You are Jordan, an interview coach. Write a 3-sentence warmup that proves you read both the job post and the resume. "
                "Sentence 1: Name a specific requirement or phrase FROM the job post and say what it actually means they'll ask. "
                "Sentence 2: Name which of the candidate's real experiences (specific company or project) is the strongest match and why. "
                "Sentence 3: Name the one gap that's most likely to get them rejected — be blunt. "
                "Sound like a coach who did their homework, not a template. No generic phrases like 'this role values communication.'"
            ),
            messages=[{"role": "user", "content": f"Context: {context_summary}\n\nResume:\n{resume}"}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        LOGGER.warning("Warmup Claude call failed: %s", exc)
        return context_summary


def _build_profile_update(
    transcript: list[dict],
    context_summary: str,
    resume: str,
    prior_profile: "database.CandidateProfile | None",
) -> dict:
    """Generate updated candidate profile data from Claude after session ends."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"readiness_score": 5.0, "known_strengths": [], "known_weaknesses": [], "patterns": []}
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        prior_context = ""
        if prior_profile and prior_profile.session_count > 0:
            prior_context = f"\nPrior profile ({prior_profile.session_count} sessions, readiness {prior_profile.readiness_score}/10):\n- Strengths: {prior_profile.known_strengths}\n- Weaknesses: {prior_profile.known_weaknesses}\n- Patterns: {prior_profile.patterns}"
        conversation = "\n".join([
            f"{'Jordan' if t['speaker'] == 'jordan' else 'Candidate'}: {t['text']}"
            for t in transcript
        ])
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system='You are Jordan analyzing a coaching session. Return ONLY valid JSON with these keys: readiness_score (float 1-10), known_strengths (list of short strings), known_weaknesses (list of short strings), patterns (list of behavioral observations like "deflects on metrics"). Be specific and based only on what happened in this session. If prior profile exists, adjust scores gradually.',
            messages=[{"role": "user", "content": f"Context: {context_summary}{prior_context}\n\nResume:\n{resume}\n\nSession:\n{conversation}"}],
        )
        import json as _json
        text = response.content[0].text.strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return _json.loads(text.strip())
    except Exception as exc:
        LOGGER.warning("Profile update Claude call failed: %s", exc)
        return {"readiness_score": 5.0, "known_strengths": [], "known_weaknesses": [], "patterns": []}


def _get_track_key(mode: str, context_id: int) -> str:
    """Return a stable string key for the candidate profile."""
    return f"{mode}:{context_id}"


def _build_summary(transcript: list[dict], context_summary: str, resume: str = "") -> str:
    """Generate end-of-session coaching summary."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Session complete. Review your answers and focus on adding specific metrics and examples."
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        conversation = "\n".join([
            f"{'Jordan' if t['speaker'] == 'jordan' else 'Candidate'}: {t['text']}"
            for t in transcript
        ])
        resume_section = f"\n\nCandidate resume:\n{resume}" if resume else ""
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=350,
            system="You are Jordan, an interview coach. After reviewing the mock interview, give feedback in exactly this format — no intro, no labels, just the content:\n\n✅ [What they did well — reference their exact words from the session, name the specific moment]\n\n🔧 [What to sharpen — 1-2 concrete actions, e.g. 'Add the actual number: how many orders per day at Nufours?']\n\n💬 Memorize this: \"[one sentence grounded in their real resume experience — name the actual company, role, or project. Should be something they can say verbatim in the real interview.]\"",
            messages=[{"role": "user", "content": f"Context: {context_summary}{resume_section}\n\nConversation:\n{conversation}"}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        LOGGER.warning("Summary Claude call failed: %s", exc)
        return "Session complete. Focus on adding specific metrics and examples to your answers."


async def start_session(mode: str, context_id: int) -> JordanStartResponse:
    context_summary, resume = build_context(mode=mode, context_id=context_id)
    track_key = _get_track_key(mode, context_id)
    prior_profile = database.get_candidate_profile(track_key)

    # Personalize warmup based on history
    if prior_profile and prior_profile.session_count > 0:
        weakness_hint = f" Last time your main weakness was: {prior_profile.known_weaknesses[0]}." if prior_profile.known_weaknesses else ""
        warmup_text = _build_warmup(
            context_summary=context_summary + weakness_hint,
            resume=resume,
        )
    else:
        warmup_text = _build_warmup(context_summary=context_summary, resume=resume)

    # Opening question — if repeat session, target known weakness directly
    if prior_profile and prior_profile.session_count > 0 and prior_profile.known_weaknesses:
        weakness_context = f"{context_summary} IMPORTANT: This candidate's known weakness is: {prior_profile.known_weaknesses[0]}. Open by targeting that weakness directly."
        opening_question = _build_opening_question(context_summary=weakness_context, resume=resume)
    else:
        opening_question = _build_opening_question(context_summary=context_summary, resume=resume)

    transcript = [{"speaker": "jordan", "text": opening_question}]
    session = database.create_jordan_session(mode=mode, context_id=context_id, transcript=transcript)

    return JordanStartResponse(
        session_id=session.id,
        question_text=opening_question,
        audio_url=await synthesize_audio(opening_question),
        prefetched_audio_urls=[],
        warmup_text=warmup_text,
        context_summary=context_summary,
        readiness_score=prior_profile.readiness_score if prior_profile else 0,
        session_count=prior_profile.session_count if prior_profile else 0,
        known_weaknesses=prior_profile.known_weaknesses if prior_profile else [],
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
    context_summary, resume = build_context(mode=session.mode, context_id=session.context_id)

    # Try Claude API first, fall back to static
    try:
        coaching, next_question = _call_claude_coaching(
            transcript=transcript,
            context_summary=context_summary,
            resume=resume,
            session_complete=session_complete,
            exchange_count=exchange_count,
        )
    except Exception as exc:
        LOGGER.warning("Jordan Claude call failed, using fallback: %s", exc)
        coaching, next_question = _fallback_coaching(answer=answer, exchange_count=exchange_count)

    transcript.append({"speaker": "jordan", "text": next_question, "coaching": coaching})
    database.update_jordan_session(session_id=session_id, transcript=transcript)

    summary = None
    readiness_score = None
    if session_complete:
        summary = _build_summary(transcript=transcript, context_summary=context_summary, resume=resume)
        # Update candidate profile
        track_key = _get_track_key(session.mode, session.context_id)
        prior_profile = database.get_candidate_profile(track_key)
        profile_data = _build_profile_update(
            transcript=transcript,
            context_summary=context_summary,
            resume=resume,
            prior_profile=prior_profile,
        )
        readiness_score = float(profile_data.get("readiness_score", 5.0))
        database.upsert_candidate_profile(
            track_key=track_key,
            readiness_score=readiness_score,
            known_strengths=profile_data.get("known_strengths", []),
            known_weaknesses=profile_data.get("known_weaknesses", []),
            patterns=profile_data.get("patterns", []),
            last_session_summary=summary or "",
        )

    return JordanRespondResponse(
        coaching=coaching,
        next_question_text=next_question,
        audio_url=await synthesize_audio(next_question),
        session_complete=session_complete,
        summary=summary,
        readiness_score=readiness_score,
    )
