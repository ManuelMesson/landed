import pytest

from models import AnalyzeRequest


async def _create_job(client) -> int:
    analysis = (
        await client.post(
        "/analyze",
        json=AnalyzeRequest(
            job_post="Customer support role focused on onboarding, retention, and issue resolution.",
            resume="Customer onboarding, retention, issue resolution, and metrics like 20 percent growth.",
            track_id=1,
        ).model_dump(),
    )
    ).json()
    response = await client.post(
        "/jobs",
        json={
            "track_id": 1,
            "company": "Amazon",
            "role": "Customer Success Specialist",
            "job_post": "Customer support role focused on onboarding, retention, and issue resolution.",
            "date_applied": "2026-04-23",
            "ats_score": analysis["ats_score"],
            "hm_score": analysis["hm_score"],
            "analysis": analysis,
            "interview_prep": "Talk through retention work.",
            "notes": "Referral path",
        },
    )
    return response.json()["id"]


@pytest.mark.anyio
async def test_log_application_with_track(client) -> None:
    job_id = await _create_job(client)
    response = await client.get(f"/jobs/{job_id}")
    payload = response.json()
    assert payload["track_id"] == 1
    assert payload["company"] == "Amazon"


@pytest.mark.anyio
async def test_get_applications_by_track(client) -> None:
    await _create_job(client)
    response = await client.get("/jobs", params={"track_id": 1})
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["track_name"] == "customer-success"


@pytest.mark.anyio
async def test_update_application_status(client) -> None:
    job_id = await _create_job(client)
    response = await client.patch(f"/jobs/{job_id}", json={"status": "Interview"})
    payload = response.json()
    assert payload["status"] == "Interview"
