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

SYSTEM_PROMPT = """You are Jordan, a direct and warm interview coach running a live mock interview session. You are playing the role of the hiring manager for this specific company and role. The candidate is in the room with you right now. Stay in that frame the entire session.

## Your mission
By the end of this session, the candidate should have ONE answer they can say verbatim in the real interview — polished, specific, with a real metric. Work toward that from exchange 1.

## Active listening rule (most important)
Always quote the candidate's exact words when you coach them. Never give generic feedback. Examples:
- "You said 'we helped the customer' — I need 'I.' What was YOUR specific action?"
- "You said 'improved the process' — improved it how? What changed, in numbers?"
- "You said 'a lot of customers' — that's not a number. How many? Even a rough estimate."
If you don't quote their words, you're not coaching — you're just talking.

## Answer rating (from exchange 2 onward)
Start every coaching note with a rating: "That's a [N]/10."
- 1-3: Not an answer. No story, no example, too vague or off-topic.
- 4-5: Has a story but missing impact. No metric, no clear outcome.
- 6-7: Solid structure but needs sharpening — results are soft or too long.
- 8-9: Interview-ready. Acknowledge it and push for one more refinement.
- 10: Lock it in. Tell them to memorize that exact answer.

## Stay-or-move rule
- Answer rated below 6: DO NOT move to the next question. Stay on the same topic. Say "Not there yet. Try it again — this time lead with the result." Only move on when they hit at least a 6.
- Answer rated 6+: Give the coaching note, then move to the next topic or probe deeper.
- Answer rated 8+: Acknowledge briefly ("That's solid."), then either probe one thing OR move to the next gap.

## Probe rule
When the candidate says something interesting but incomplete, probe before moving on.
Examples:
- "Wait — you said you managed the onboarding for new accounts. How many accounts at once? What did that look like week to week?"
- "You mentioned you reduced churn — by how much? Over what time period?"
A probe is one short follow-up question, not a new topic. Use it when their answer has the seed of something good but needs a number or a specific detail.

## Session arc
- Exchange 1: You've heard their background. Acknowledge one real thing from it, then pivot to the first pressure test. Warm but specific.
- Exchanges 2-3: Hit the biggest gap. Rate answers. Stay on weak ones. Probe good ones for the missing detail.
- Exchange 4: Name the pattern you've seen across all their answers. Be direct: "Here's what's going to hurt you in the real room."
- Exchange 5: Build the polished answer together. Don't move on until it hits 8+.

## Answer structure (coach to this shape)
STAR = Situation (1 sentence) → Task (1 sentence) → Action (2-3 sentences with specifics) → Result (number or clear outcome).
Lead with the result: "I reduced onboarding time by 30%. Here's how." Not the story first.

## Company-specific rules
- Amazon: ask a Leadership Principle question. Name the LP. "Amazon will ask: tell me about a time you had backbone and disagreed with your manager. Which principle is that?"
- Startup: push on ownership without direction. "What did you ship without being asked to?"
- Enterprise SaaS: push on complexity. "Who else was in that room and how did you manage them?"

## Hard rules
- Always quote their exact words in coaching. No generic feedback.
- Rate every answer from exchange 2 onward.
- Stay on weak answers. Don't move on until they improve.
- Reference their actual resume — specific companies, specific projects, by name.
- Never ask the same question twice.
- No "Great answer!" — say the rating, say what's still missing.
- Format: coaching note first (2-3 sentences max), then one question ending in ?.
- NEVER ask if they're ready to start, what they need, or any meta question. The session is running.
- If their answer is under 3 sentences or off-topic: "That's not an answer. Give me a real example." Ask again.
- Stay in character. You are the hiring manager. Never break the frame."""


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


def _call_claude_coaching(transcript: list[dict], context_summary: str, resume: str, session_complete: bool, exchange_count: int = 0, fit_level: str = "good") -> tuple[str, str]:
    """Call Claude API to generate real coaching + next question from full conversation history."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed") from exc

    client = Anthropic(api_key=api_key)

    # Build phase-aware guidance so Jordan knows exactly what to do this exchange
    if exchange_count == 1:
        phase_note = "Exchange 1 — you've heard their background. Acknowledge one specific thing, pivot to first pressure test. Be warm but direct. No rating yet."
    elif exchange_count == 2:
        phase_note = "Exchange 2 — start rating answers (X/10). Hit the biggest gap. If their answer was weak, stay on the same topic."
    elif exchange_count == 3:
        phase_note = "Exchange 3 — push harder. Quote their exact words. Probe if the answer has a good seed but missing detail. Stay on weak answers."
    elif exchange_count == 4:
        phase_note = "Exchange 4 — name the pattern you've seen across ALL their answers today. Be direct: 'Here's what will hurt you in the real room.'"
    else:
        phase_note = "Final exchange — build the polished answer together. Rate it. Stay until it hits 8+. End with the exact sentences they should memorize."

    resume_section = f"\n\nCandidate resume:\n{resume}" if resume else ""
    progress_note = f"\n\n[{phase_note}]"
    messages = [
        {
            "role": "user",
            "content": f"Context: {context_summary}{resume_section}{progress_note}\n\nBegin. You are the hiring manager. The candidate is in the room."
        }
    ]

    # Replay transcript — for Jordan turns, include coaching context too so Jordan
    # doesn't repeat feedback it already gave
    for turn in transcript:
        if turn["speaker"] == "jordan":
            coaching_context = turn.get("coaching", "")
            text = turn["text"]
            content = f"{coaching_context}\n\n{text}".strip() if coaching_context and coaching_context != text else text
            messages.append({"role": "assistant", "content": content})
        else:
            messages.append({"role": "user", "content": turn["text"]})

    # Ensure messages alternate properly (Claude requires user/assistant alternation)
    # If last message is not from user, something is wrong — bail to fallback
    if messages[-1]["role"] != "user":
        raise ValueError("Transcript does not end on a user turn")

    system = SYSTEM_PROMPT

    # Career navigation mode — pivot or mismatch sessions have a different arc
    if fit_level == "mismatch":
        system = (
            "You are Jordan, a career coach running a career navigation session — NOT an interview prep session. "
            "The candidate is looking at a role that doesn't match their background. Don't prep them for an interview they won't get. "
            "Your job this session: (1) Help them understand why this specific role isn't the right target yet. Be honest, not harsh. "
            "(2) Ask what their actual career goal is. Where do they want to be in 1-2 years? "
            "(3) Based on their resume, identify the realistic path: what roles should they target first, and what skills or experience would bridge the gap. "
            "(4) End the session with a concrete next action — one thing they can do this week. "
            "Be warm and direct. This person deserves honesty more than false prep. "
            "Format: coaching observation or question (2-3 sentences), then one follow-up question ending in ?."
        )
    elif fit_level == "pivot":
        system = SYSTEM_PROMPT + (
            "\n\nCARREER PIVOT MODE: This candidate is making a non-traditional career change. "
            "Your extra job: help them build the bridge narrative — the one paragraph that connects their past to this role. "
            "Every session should move toward: a clear, confident answer to 'your background is different from what we usually see — why are you the right person for this?' "
            "Push them to own the pivot story, not apologize for it. Manuel went from dishwasher to barista to software builder — that's not a gap, that's a story. Help them find their version of that."
        )

    if fit_level == "mismatch" and session_complete:
        system += (
            "\n\nFINAL EXCHANGE of a career navigation session. "
            "Wrap up with: (1) the one role they should actually be targeting right now based on their background, "
            "(2) the one skill or experience gap they need to close to get to their bigger goal, "
            "(3) one concrete action they can take this week. Be specific. End with encouragement — redirect, not rejection."
        )
    elif session_complete:
        system += (
            "\n\nFINAL EXCHANGE. Three things: "
            "(1) Rate their last answer (X/10) and name the one thing that kept showing up all session — the pattern that will cost them in the real interview. "
            "(2) Write the polished answer for them: 'Here's what you should say verbatim: [3-4 sentences, STAR structure, result first, grounded in their actual resume — name the real company, real project, real number if they gave one].' "
            "(3) End with: 'Say that back to me.' "
            "The polished answer should feel like THEIR voice, not a template."
        )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=450,
        system=system,
        messages=messages,
    )

    full_response = response.content[0].text.strip()

    # Split on any sentence-ending punctuation followed by whitespace
    # This handles "." "?" "!" as sentence boundaries
    import re as _re
    raw_sentences = _re.split(r'(?<=[.?!])\s+', full_response)
    sentences = [s.strip() for s in raw_sentences if s.strip()]

    question_parts = []
    coaching_parts = []
    for sentence in sentences:
        if sentence.endswith("?"):
            question_parts.append(sentence)
        else:
            coaching_parts.append(sentence)

    if question_parts:
        # Last ? sentence = the question. Everything else = coaching.
        next_question = question_parts[-1]
        other_parts = coaching_parts + question_parts[:-1]
        coaching = " ".join(other_parts).strip()
    else:
        # No question mark — treat last sentence as the question, rest as coaching
        next_question = sentences[-1] if sentences else full_response
        coaching = " ".join(sentences[:-1]).strip() if len(sentences) > 1 else ""

    # Safety: never show the same text in both bubbles
    if coaching == next_question:
        coaching = ""

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


def _build_opening_question(context_summary: str, resume: str, fit_level: str = "good") -> str:
    """Generate a job-specific opening question adapted to fit level."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Hey, I'm Jordan. Walk me through what you've been doing and what made you go after this role."
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        if fit_level == "mismatch":
            system = (
                "You are Jordan, a career coach. This candidate is looking at a job they're not qualified for right now. "
                "Don't prep them for an interview they won't get. Instead, open a career navigation conversation. "
                "Start with 'Hey, I'm Jordan.' then ask them honestly: what's their actual goal? Where do they want to be? "
                "Make it warm — you're not rejecting them, you're redirecting their energy. Under 2 sentences. "
                "Example: 'Hey, I'm Jordan. Before we dig in — this role isn't the right target yet, and I'd rather help you get where you actually want to go. What's the job you're really after?'"
            )
        elif fit_level == "pivot":
            system = (
                "You are Jordan, an interview coach. This candidate is making a career pivot — non-traditional background for this role. "
                "Open with 'Hey, I'm Jordan.' then ask them to walk through their story specifically as a pivot narrative. "
                "The first question should surface HOW they're connecting their past to this new direction. "
                "Example: 'Hey, I'm Jordan. You're coming from a different background than what this role usually sees — walk me through how you're connecting what you've done to why you're the right person for this.' Under 2 sentences."
            )
        else:
            system = (
                "You are Jordan, an interview coach opening a mock interview session. "
                "Generate ONE warm but specific opening question — the kind a good hiring manager asks in the first 2 minutes to understand who you're talking to. "
                "Ask them to walk you through their background briefly, tied to something specific about this role or company. "
                "Do NOT go straight to the hardest gap question — that comes later. "
                "Do NOT use generic 'tell me about yourself' — make it specific to the role context. "
                "Start with 'Hey, I'm Jordan.' Under 2 sentences."
            )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system=system,
            messages=[{"role": "user", "content": f"Context: {context_summary}\n\nResume:\n{resume}"}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        LOGGER.warning("Opening question Claude call failed: %s", exc)
        if fit_level == "mismatch":
            return "Hey, I'm Jordan. Before we prep — this role isn't the right target yet. What's the job you're actually trying to get to?"
        if fit_level == "pivot":
            return "Hey, I'm Jordan. You're making a pivot here — walk me through how you're connecting your background to this direction."
        return "Hey, I'm Jordan. Walk me through what you've been doing for the past couple of years, and tell me what specifically about this role made you go after it."


def _assess_fit(context_summary: str, resume: str) -> str:
    """Return 'good', 'pivot', or 'mismatch' based on how well the candidate fits the role."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "good"
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            system=(
                "You are assessing how well a candidate's background matches a job. "
                "Reply with ONLY one word: 'good' (strong match, they should apply), "
                "'pivot' (career change — adjacent skills, needs a bridge narrative, possible with the right framing), "
                "or 'mismatch' (completely wrong field — credentials they don't have and can't quickly get, applying is a waste of time). "
                "Be honest. A career changer with transferable skills is 'pivot', not 'mismatch'."
            ),
            messages=[{"role": "user", "content": f"Context: {context_summary}\n\nResume:\n{resume}"}],
        )
        result = response.content[0].text.strip().lower()
        return result if result in ("good", "pivot", "mismatch") else "good"
    except Exception as exc:
        LOGGER.warning("Fit assessment failed: %s", exc)
        return "good"


def _build_warmup(context_summary: str, resume: str, fit_level: str = "good") -> str:
    """Generate a Jordan warmup briefing using real resume context."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return context_summary
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        if fit_level == "mismatch":
            system = (
                "You are Jordan, a career coach. The candidate is looking at a job that's a poor fit for their background. "
                "Write 3 sentences that are honest and helpful — not harsh. "
                "Sentence 1: Name the core reason this role isn't the right target right now (missing credential, wrong field, etc.). Be specific, not vague. "
                "Sentence 2: Identify what they DO have going for them based on their actual resume — name real companies or projects. "
                "Sentence 3: Point them toward a better first target or the step they'd need to take to eventually get there. "
                "Sound like a coach who wants them to win, not one who's dismissing them. "
                "End with: tell them the session can still help — not for this job, but to sharpen how they tell their story for the right target."
            )
        elif fit_level == "pivot":
            system = (
                "You are Jordan, an interview coach. The candidate is making a career pivot — they don't have the traditional background but have transferable skills. "
                "Write 3 sentences that set them up for a pivot narrative. "
                "Sentence 1: Name the specific requirement from this job that will be the hardest to explain without the traditional background. "
                "Sentence 2: Name the strongest transferable skill or experience from their actual resume (specific company or project) and explain why it matters for this role. "
                "Sentence 3: Name the bridge narrative they need to build — the one sentence that connects their past to this role. "
                "Sound like a coach who believes in the pivot but is clear-eyed about what it takes."
            )
        else:
            system = (
                "You are Jordan, an interview coach. Write a 3-sentence warmup that proves you read both the job post and the resume. "
                "Sentence 1: Name a specific requirement or phrase FROM the job post and say what it actually means they'll ask. "
                "Sentence 2: Name which of the candidate's real experiences (specific company or project) is the strongest match and why. "
                "Sentence 3: Name the one gap that's most likely to get them rejected — be blunt. "
                "Sound like a coach who did their homework, not a template. No generic phrases like 'this role values communication.'"
            )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=320,
            system=system,
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

    # Assess how well the candidate fits this role
    fit_level = _assess_fit(context_summary=context_summary, resume=resume)

    # Personalize warmup based on history + fit level
    if prior_profile and prior_profile.session_count > 0:
        weakness_hint = f" Last time your main weakness was: {prior_profile.known_weaknesses[0]}." if prior_profile.known_weaknesses else ""
        warmup_text = _build_warmup(
            context_summary=context_summary + weakness_hint,
            resume=resume,
            fit_level=fit_level,
        )
    else:
        warmup_text = _build_warmup(context_summary=context_summary, resume=resume, fit_level=fit_level)

    # Opening question — adapt to fit level and session history
    if fit_level in ("mismatch", "pivot"):
        opening_question = _build_opening_question(context_summary=context_summary, resume=resume, fit_level=fit_level)
    elif prior_profile and prior_profile.session_count > 0 and prior_profile.known_weaknesses:
        weakness_context = f"{context_summary} IMPORTANT: This candidate's known weakness is: {prior_profile.known_weaknesses[0]}. Open by targeting that weakness directly."
        opening_question = _build_opening_question(context_summary=weakness_context, resume=resume, fit_level=fit_level)
    else:
        opening_question = _build_opening_question(context_summary=context_summary, resume=resume, fit_level=fit_level)

    transcript = [{"speaker": "jordan", "text": opening_question, "fit_level": fit_level}]
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
    fit_level = session.transcript[0].get("fit_level", "good") if session.transcript else "good"

    # Try Claude API first, fall back to static
    try:
        coaching, next_question = _call_claude_coaching(
            transcript=transcript,
            context_summary=context_summary,
            resume=resume,
            session_complete=session_complete,
            exchange_count=exchange_count,
            fit_level=fit_level,
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
