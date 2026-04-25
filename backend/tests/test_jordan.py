import pytest


async def _auth_headers(client) -> dict[str, str]:
    response = await client.post("/auth/register", json={"email": "jordan@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.anyio
async def test_jordan_session_start(client) -> None:
    headers = await _auth_headers(client)
    response = await client.post("/jordan/session/start", json={"mode": "track", "track_id": 1}, headers=headers)
    payload = response.json()
    assert response.status_code == 200
    assert payload["question_text"].startswith("Hey, I'm Jordan.")
    assert payload["audio_url"].startswith("/static/audio/")


@pytest.mark.anyio
async def test_jordan_session_respond(client) -> None:
    headers = await _auth_headers(client)
    start = (await client.post("/jordan/session/start", json={"mode": "track", "track_id": 1}, headers=headers)).json()
    response = await client.post(
        "/jordan/session/respond",
        json={"session_id": start["session_id"], "answer": "I improved onboarding time by 22 percent after redesigning the support checklist."},
        headers=headers,
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["next_question_text"]
    assert payload["audio_url"].startswith("/static/audio/")


@pytest.mark.anyio
async def test_jordan_pushback(client) -> None:
    headers = await _auth_headers(client)
    start = (await client.post("/jordan/session/start", json={"mode": "track", "track_id": 1}, headers=headers)).json()
    response = await client.post(
        "/jordan/session/respond",
        json={"session_id": start["session_id"], "answer": "I helped customers with things and worked with support."},
        headers=headers,
    )
    payload = response.json()
    assert "specific result or number" in payload["coaching"]
