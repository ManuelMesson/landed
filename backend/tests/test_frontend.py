from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_auth_pages_exist() -> None:
    login_html = (PROJECT_ROOT / "frontend" / "login.html").read_text()
    register_html = (PROJECT_ROOT / "frontend" / "register.html").read_text()

    assert 'id="auth-form"' in login_html
    assert 'id="auth-form"' in register_html
    assert 'name="name"' in register_html
    assert "/static/auth.js" in login_html
    assert "/static/auth.js" in register_html
    assert "/static/login.js" in login_html
    assert "/static/register.js" in register_html


def test_app_pages_load_shared_auth_script() -> None:
    for page in ["index.html", "tracker.html", "jordan.html"]:
        html = (PROJECT_ROOT / "frontend" / page).read_text()
        assert "/static/auth.js" in html
        assert "data-auth-slot" in html


def test_client_scripts_reference_cookie_auth_flow() -> None:
    auth_js = (PROJECT_ROOT / "static" / "auth.js").read_text()
    index_js = (PROJECT_ROOT / "static" / "index.js").read_text()
    register_js = (PROJECT_ROOT / "static" / "register.js").read_text()

    assert "landed_has_session" in auth_js
    assert "landed_jwt" not in auth_js
    assert 'credentials: "include"' in auth_js
    assert "/auth/me" in auth_js
    assert "/auth/resume" in index_js
    assert "isLoggedIn()" in index_js
    assert 'name: form.get("name")' in register_js
