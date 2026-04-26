from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

import httpx
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext


ACCESS_TOKEN_EXPIRE_DAYS = 30
ALGORITHM = "HS256"
COOKIE_NAME = "landed_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


def get_jwt_secret() -> str:
    """Return the JWT secret or raise if not configured."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return secret


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against the stored hash."""
    return pwd_context.verify(password, password_hash)


def create_access_token(*, subject: str, user_id: int, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    expire_at = datetime.now(UTC) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    payload = {"sub": subject, "user_id": user_id, "exp": int(expire_at.timestamp())}
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token."""
    return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])


def _cookie_secure_flag() -> bool:
    """Only mark the auth cookie as secure in production deployments."""
    return os.getenv("ENVIRONMENT", "development") == "production"


def set_auth_cookie(response, token: str) -> None:
    """Store the signed JWT in an httpOnly session cookie."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=_cookie_secure_flag(),
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response) -> None:
    """Clear the auth session cookie."""
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_cookie_secure_flag(),
        samesite="lax",
    )


def get_landed_base_url() -> str:
    """Return the canonical public URL used in password reset emails."""
    return os.getenv("LANDED_BASE_URL", "https://landed-cz99.onrender.com").rstrip("/")


def build_password_reset_url(token: str) -> str:
    """Return the full password reset URL for a given token."""
    query = urlencode({"token": token})
    return f"{get_landed_base_url()}/reset-password?{query}"


def send_reset_email(to_email: str, reset_url: str) -> None:
    """Send a password reset email via Resend."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("Skipping password reset email because RESEND_API_KEY is not configured")
        return

    from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": f"Jordan at Landed <{from_email}>",
            "to": [to_email],
            "subject": "Reset your Landed password",
            "html": f"""
            <div style="font-family: Inter, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 24px; background: #08080f; color: #f0f0ff;">
              <h2 style="font-size: 1.4rem; font-weight: 700; margin-bottom: 8px;">Reset your password</h2>
              <p style="color: #8888aa; margin-bottom: 24px;">Jordan here. Click the link below to set a new password. It expires in 1 hour.</p>
              <a href="{reset_url}" style="display: inline-block; background: #7c3aed; color: white; text-decoration: none; padding: 12px 24px; border-radius: 999px; font-weight: 600; font-size: 0.95rem;">Set new password -&gt;</a>
              <p style="color: #8888aa; font-size: 0.8rem; margin-top: 32px;">If you didn't request this, ignore this email. Your password won't change.</p>
            </div>
            """,
        },
        timeout=10.0,
    )
    response.raise_for_status()
