from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from clinic_app.settings import settings


_SECRET = settings.jwt_secret or ("dev-" + secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    # Dev fallback so app can boot without env vars.
    return _SECRET


def create_access_token(*, sub: str, tenant_id: int, role: str, minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=minutes or settings.access_token_minutes)
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": sub,
        "tid": tenant_id,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def create_refresh_token(*, sub: str, tenant_id: int, role: str, days: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=days or settings.refresh_token_days)
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": sub,
        "tid": tenant_id,
        "role": role,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"], issuer=settings.jwt_issuer)
    except JWTError as e:
        raise ValueError("Invalid token") from e

