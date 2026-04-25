from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any


ACCESS_TOKEN_EXPIRE_DAYS = 30
ALGORITHM = "HS256"


try:
    from jose import JWTError, jwt
except ImportError:  # pragma: no cover - exercised only in dependency-light sandboxes
    JWTError = ValueError
    jwt = None


try:
    from passlib.context import CryptContext
except ImportError:  # pragma: no cover - exercised only in dependency-light sandboxes
    CryptContext = None


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


def get_jwt_secret() -> str:
    """Return the JWT secret or raise if not configured."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return secret


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt when available, otherwise a deterministic scrypt fallback."""
    if pwd_context is not None:
        return pwd_context.hash(password)

    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=2**14, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against the stored hash."""
    if pwd_context is not None:
        return pwd_context.verify(password, password_hash)

    if not password_hash.startswith("scrypt$"):
        return False
    _, salt, expected = password_hash.split("$", 2)
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=2**14, r=8, p=1).hex()
    return hmac.compare_digest(actual, expected)


def create_access_token(*, subject: str, user_id: int, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    expire_at = datetime.now(UTC) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    payload = {"sub": subject, "user_id": user_id, "exp": int(expire_at.timestamp())}
    secret = get_jwt_secret()
    if jwt is not None:
        return jwt.encode(payload, secret, algorithm=ALGORITHM)
    return _encode_fallback_jwt(payload, secret)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token."""
    secret = get_jwt_secret()
    if jwt is not None:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    return _decode_fallback_jwt(token, secret)


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _encode_fallback_jwt(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": ALGORITHM, "typ": "JWT"}
    header_segment = _urlsafe_b64encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_segment = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{_urlsafe_b64encode(signature)}"


def _decode_fallback_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise JWTError("Invalid token format") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _urlsafe_b64decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise JWTError("Invalid token signature")

    payload = json.loads(_urlsafe_b64decode(payload_segment).decode("utf-8"))
    exp = payload.get("exp")
    if exp is None or datetime.now(UTC).timestamp() >= float(exp):
        raise JWTError("Token expired")
    return payload
