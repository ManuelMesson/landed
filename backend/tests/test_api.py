import pytest

from models import AnalyzeRequest


async def _register_and_auth(client, email: str = "sam@example.com") -> dict[str, str]:
    response = await client.post("/auth/register", json={"email": email, "password": "password123"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_job(client, headers: dict[str, str]) -> int:
    analysis = (
        await client.post(
        "/analyze",
        headers=headers,
        json=AnalyzeRequest(
            job_post="Customer support role focused on onboarding, retention, and issue resolution.",
            resume="Customer onboarding, retention, issue resolution, and metrics like 20 percent growth.",
            track_id=1,
        ).model_dump(),
    )
    ).json()
    response = await client.post(
        "/jobs",
        headers=headers,
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
    headers = await _register_and_auth(client)
    job_id = await _create_job(client, headers)
    response = await client.get(f"/jobs/{job_id}", headers=headers)
    payload = response.json()
    assert payload["track_id"] == 1
    assert payload["company"] == "Amazon"


@pytest.mark.anyio
async def test_get_applications_by_track(client) -> None:
    headers = await _register_and_auth(client)
    await _create_job(client, headers)
    response = await client.get("/jobs", params={"track_id": 1}, headers=headers)
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["track_name"] == "customer-success"


@pytest.mark.anyio
async def test_update_application_status(client) -> None:
    headers = await _register_and_auth(client)
    job_id = await _create_job(client, headers)
    response = await client.patch(f"/jobs/{job_id}", json={"status": "Interview"}, headers=headers)
    payload = response.json()
    assert payload["status"] == "Interview"
