from analyzer import analyze_job_post


JOB_POST = """
Amazon is hiring a Customer Success Specialist to manage onboarding, resolve escalations,
drive adoption, partner with account teams, and improve retention using data.
Candidates should communicate clearly, work cross-functionally, and share examples with metrics.
"""

RESUME = """
Managed onboarding for new bakery wholesale clients, resolved customer issues,
and improved order accuracy by 18 percent while coordinating with operations and sales.
"""


def test_analyze_job_post() -> None:
    result = analyze_job_post(job_post=JOB_POST, resume=RESUME, track_label="Customer Success Specialist")
    assert 0 <= result.ats_score <= 100
    assert 0.0 <= result.hm_score <= 10.0
    assert result.key_requirements
    assert result.talking_points


def test_live_score_changes_with_resume() -> None:
    weak_resume = "Handled customers and worked hard with teams."
    strong_resume = RESUME + " Improved retention by 12 percent and presented weekly adoption reports."
    weak = analyze_job_post(job_post=JOB_POST, resume=weak_resume, track_label="Customer Success Specialist")
    strong = analyze_job_post(job_post=JOB_POST, resume=strong_resume, track_label="Customer Success Specialist")
    assert strong.ats_score >= weak.ats_score
    assert strong.hm_score >= weak.hm_score
