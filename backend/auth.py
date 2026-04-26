from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext


ACCESS_TOKEN_EXPIRE_DAYS = 30
ALGORITHM = "HS256"
COOKIE_NAME = "landed_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
