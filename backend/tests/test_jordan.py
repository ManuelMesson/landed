import pytest


@pytest.mark.anyio
async def test_jordan_session_start(client) -> None:
    response = await client.post("/jordan/session/start", json={"mode": "track", "track_id": 1})
    payload = response.json()
    assert response.status_code == 200
    assert payload["question_text"].startswith("Hey, I'm Jordan.")
    assert payload["audio_url"].startswith("/static/audio/")


@pytest.mark.anyio
async def test_jordan_session_respond(client) -> None:
    start = (await client.post("/jordan/session/start", json={"mode": "track", "track_id": 1})).json()
    response = await client.post(
        "/jordan/session/respond",
        json={"session_id": start["session_id"], "answer": "I improved onboarding time by 22 percent after redesigning the support checklist."},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["next_question_text"]
    assert payload["audio_url"].startswith("/static/audio/")


@pytest.mark.anyio
async def test_jordan_pushback(client) -> None:
    start = (await client.post("/jordan/session/start", json={"mode": "track", "track_id": 1})).json()
    response = await client.post(
        "/jordan/session/respond",
        json={"session_id": start["session_id"], "answer": "I helped customers with things and worked with support."},
    )
    payload = response.json()
    assert "specific result or number" in payload["coaching"]
