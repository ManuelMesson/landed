import pytest


async def _register(client, *, email: str, password: str = "password123", name: str | None = None) -> dict:
    payload = {"email": email, "password": password}
    if name is not None:
        payload["name"] = name
    response = await client.post("/auth/register", json=payload)
    return {"status_code": response.status_code, "json": response.json(), "headers": dict(response.headers)}


async def _login(client, *, email: str, password: str = "password123") -> dict:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    return {"status_code": response.status_code, "json": response.json(), "headers": dict(response.headers)}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_register_new_user(client) -> None:
    result = await _register(client, email="sam@example.com")

    assert result["status_code"] == 201
    assert result["json"]["access_token"]
    assert result["json"]["user"]["email"] == "sam@example.com"
    assert result["json"]["user"]["display_name"] == "Sam"
    assert result["json"]["user"]["has_resume"] is False


@pytest.mark.anyio
async def test_register_with_name(client) -> None:
    result = await _register(client, email="sam@example.com", name="Sam")

    assert result["status_code"] == 201
    assert result["json"]["user"]["display_name"] == "Sam"


@pytest.mark.anyio
async def test_register_without_name(client) -> None:
    result = await _register(client, email="manuelmesson@example.com")

    assert result["status_code"] == 201
    assert result["json"]["user"]["display_name"] == "Manuelmesson"


@pytest.mark.anyio
async def test_register_duplicate_email_fails(client) -> None:
    await _register(client, email="sam@example.com")
    result = await _register(client, email="sam@example.com")

    assert result["status_code"] == 409
    assert result["json"]["detail"] == "Email already registered"


@pytest.mark.anyio
async def test_login_valid_credentials(client) -> None:
    await _register(client, email="alex@example.com", name="Alex")
    result = await _login(client, email="alex@example.com")

    assert result["status_code"] == 200
    assert result["json"]["access_token"]
    assert result["json"]["user"]["email"] == "alex@example.com"
    assert result["json"]["user"]["display_name"] == "Alex"


@pytest.mark.anyio
async def test_login_returns_display_name(client) -> None:
    await _register(client, email="alex@example.com", name="Alex")
    result = await _login(client, email="alex@example.com")

    assert result["status_code"] == 200
    assert result["json"]["user"]["display_name"] == "Alex"


@pytest.mark.anyio
async def test_login_sets_httponly_cookie(client) -> None:
    await _register(client, email="alex@example.com", name="Alex")
    result = await _login(client, email="alex@example.com")

    cookie = result["headers"]["set-cookie"]

    assert result["status_code"] == 200
    assert "landed_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


@pytest.mark.anyio
async def test_login_wrong_password_fails(client) -> None:
    await _register(client, email="alex@example.com")
    result = await _login(client, email="alex@example.com", password="wrongpass")

    assert result["status_code"] == 401
    assert result["json"]["detail"] == "Invalid email or password"


@pytest.mark.anyio
async def test_protected_endpoint_without_token_fails(client) -> None:
    response = await client.get("/jobs")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


@pytest.mark.anyio
async def test_protected_endpoint_with_valid_token_succeeds(client) -> None:
    result = await _register(client, email="sam@example.com")
    token = result["json"]["access_token"]

    response = await client.get("/jobs", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_cookie_auth_accesses_protected_endpoint(client) -> None:
    await _register(client, email="cookie@example.com")

    response = await client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_jobs_scoped_to_user(client) -> None:
    user_a = await _register(client, email="a@example.com")
    user_b = await _register(client, email="b@example.com")
    headers_a = _auth_headers(user_a["json"]["access_token"])
    headers_b = _auth_headers(user_b["json"]["access_token"])

    analysis = (
        await client.post(
            "/analyze",
            headers=headers_a,
            json={
                "job_post": "Customer success role focused on onboarding and renewals.",
                "resume": "Helped customers onboard and improve adoption by 20 percent.",
                "track_id": 1,
            },
        )
    ).json()

    await client.post(
        "/jobs",
        headers=headers_a,
        json={
            "track_id": 1,
            "company": "Company A",
            "role": "CSM",
            "job_post": "Customer success role focused on onboarding and renewals.",
            "date_applied": "2026-04-24",
            "ats_score": analysis["ats_score"],
            "hm_score": analysis["hm_score"],
            "analysis": analysis,
            "interview_prep": "Talk through onboarding metrics.",
            "notes": "",
        },
    )

    response_a = await client.get("/jobs", headers=headers_a)
    response_b = await client.get("/jobs", headers=headers_b)

    assert response_a.status_code == 200
    assert len(response_a.json()) == 1
    assert response_b.status_code == 200
    assert response_b.json() == []


@pytest.mark.anyio
async def test_auth_me_returns_display_name(client) -> None:
    result = await _register(client, email="sam@example.com", name="Sam")
    token = result["json"]["access_token"]

    response = await client.get("/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["display_name"] == "Sam"


@pytest.mark.anyio
async def test_logout_clears_cookie(client) -> None:
    await _register(client, email="logout@example.com")

    response = await client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"status": "logged out"}
    assert "landed_session=\"\"" in response.headers["set-cookie"]


@pytest.mark.anyio
async def test_bearer_token_still_works(client) -> None:
    result = await _register(client, email="bearer@example.com")
    token = result["json"]["access_token"]
    client.cookies.clear()

    response = await client.get("/jobs", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_register_name_too_long_fails(client) -> None:
    result = await _register(client, email="sam@example.com", name="s" * 51)

    assert result["status_code"] == 422
