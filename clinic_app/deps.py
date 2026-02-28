from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from clinic_app.db import get_db
from clinic_app.models import User
from clinic_app.security import create_access_token, decode_token
from clinic_app.settings import settings


@dataclass(frozen=True)
class CurrentUser:
    id: int
    tenant_id: int
    username: str
    role: str


def _get_token_from_cookie(access_token: Optional[str]) -> str | None:
    if not access_token:
        return None
    return access_token


def get_current_user(
    response: Response,
    db: Session = Depends(get_db),
    access_token: Optional[str] = Cookie(default=None, alias=settings.cookie_name_access),
    refresh_token: Optional[str] = Cookie(default=None, alias=settings.cookie_name_refresh),
) -> CurrentUser:
    token = _get_token_from_cookie(access_token)
    payload = None
    if token:
        try:
            payload = decode_token(token)
        except ValueError:
            payload = None

    # Automatic session handling: if access token is missing/expired, use refresh token to mint a new access token.
    if payload is None:
        if not refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        try:
            refresh_payload = decode_token(refresh_token)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        if refresh_payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        try:
            user_id = int(refresh_payload.get("sub"))
            tenant_id = int(refresh_payload.get("tid"))
            role = str(refresh_payload.get("role"))
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh payload")

        new_access = create_access_token(sub=str(user_id), tenant_id=tenant_id, role=role)
        response.set_cookie(
            settings.cookie_name_access,
            new_access,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
        payload = decode_token(new_access)

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session type")

    try:
        user_id = int(payload.get("sub"))
        tenant_id = int(payload.get("tid"))
        role = str(payload.get("role"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session payload")

    user = db.query(User).filter(User.id == user_id).filter(User.tenant_id == tenant_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User disabled")

    return CurrentUser(id=user.id, tenant_id=user.tenant_id, username=user.username, role=user.role)


def require_role(*allowed: Literal["admin", "staff", "demo"]):
    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _dep


def forbid_demo_writes(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role == "demo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo role is read-only")
    return user

