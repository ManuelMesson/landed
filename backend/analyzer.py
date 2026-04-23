from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Iterable

from models import AnalysisResult

LOGGER = logging.getLogger(__name__)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in", "is",
    "it", "of", "on", "or", "that", "the", "to", "with", "you", "your", "will", "this",
    "our", "we", "us", "their", "they", "role", "team", "experience", "customer", "support",
}


@dataclass(frozen=True)
class KeywordMatch:
    """A keyword and whether the resume covered it."""

    term: str
    matched: bool


def tokenize(text: str) -> list[str]:
    """Normalize text into lowercase tokens."""
    return re.findall(r"[a-zA-Z][a-zA-Z0-9\-/+]+", text.lower())


def extract_keywords(job_post: str, limit: int = 12) -> list[str]:
    """Return the most repeated meaningful keywords from a job post."""
    counts: dict[str, int] = {}
    for token in tokenize(job_post):
        if token in STOP_WORDS or len(token) < 4:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]


def match_keywords(job_post: str, resume: str) -> list[KeywordMatch]:
    """Mark which top job keywords appear in the resume."""
    resume_tokens = set(tokenize(resume))
    return [KeywordMatch(term=term, matched=term in resume_tokens) for term in extract_keywords(job_post)]


def score_resume(matches: Iterable[KeywordMatch], resume: str) -> tuple[int, float]:
    """Compute ATS and hiring-manager scores from keyword matches and resume depth."""
    items = list(matches)
    if not items:
        return 35, 4.0
    match_ratio = sum(1 for item in items if item.matched) / len(items)
    metric_bonus = 0.08 if re.search(r"\b\d+[%+]?\b", resume) else 0.0
    ats_score = round(min(0.94, 0.28 + match_ratio * 0.62 + metric_bonus) * 100)
    hm_score = round(min(9.8, 3.6 + match_ratio * 5.2 + metric_bonus * 10), 1)
    return ats_score, hm_score


def build_fallback_analysis(job_post: str, resume: str, track_label: str) -> AnalysisResult:
    """Generate deterministic analysis without a live Claude call."""
    matches = match_keywords(job_post, resume)
    ats_score, hm_score = score_resume(matches, resume)
    matched = [item.term.replace("-", " ") for item in matches if item.matched][:4]
    missing = [item.term.replace("-", " ") for item in matches if not item.matched][:4]
    strongest = matched or ["customer communication", "process ownership"]
    biggest_gaps = missing or ["role-specific terminology", "measurable outcomes"]
    summary = f"This {track_label} resume already signals service and operations experience, but it should echo the job language more directly."
    talking_points = [
        f"Frame Compass Group and Nufours work as evidence of {strongest[0]}.",
        "Use one result with a number to prove impact in high-volume environments.",
        "Translate front-end and AI project work into problem-solving and stakeholder communication.",
    ]
    red_flags = []
    if not re.search(r"\b\d+[%+]?\b", resume):
        red_flags.append("Resume lacks hard metrics, which weakens credibility in interviews.")
    if len(resume.split()) < 80:
        red_flags.append("Resume is too thin for a confident demo and needs more specifics.")
    return AnalysisResult(
        ats_score=ats_score,
        hm_score=hm_score,
        role_summary=summary,
        key_requirements=missing[:3] + strongest[:2],
        your_strengths=strongest,
        gaps_to_address=biggest_gaps,
        talking_points=talking_points,
        red_flags=red_flags or ["No major red flags beyond tightening job-specific language."],
    )


def _call_claude(job_post: str, resume: str, track_label: str) -> AnalysisResult:
    """Attempt to call Anthropic and normalize the result."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed") from exc
    client = Anthropic(api_key=api_key)
    prompt = (
        "You are Landed, an exacting job application coach. Compare the job post to the resume. "
        "Return JSON only with keys: ats_score, hm_score, role_summary, key_requirements, "
        "your_strengths, gaps_to_address, talking_points, red_flags. "
        f"Track: {track_label}\nJob post:\n{job_post}\n\nResume:\n{resume}"
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    payload = json.loads(text)
    return AnalysisResult.model_validate(payload)


def analyze_job_post(job_post: str, resume: str, track_label: str) -> AnalysisResult:
    """Analyze a job post against a resume, preferring Claude with local fallback."""
    try:
        return _call_claude(job_post=job_post, resume=resume, track_label=track_label)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Falling back to local analyzer: %s", exc)
        return build_fallback_analysis(job_post=job_post, resume=resume, track_label=track_label)
