from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from clinic_app.db import get_db
from clinic_app.models import Tenant, User
from clinic_app.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from clinic_app.settings import settings


router = APIRouter()
templates = Jinja2Templates(directory="clinic_app/templates")


def _set_auth_cookies(resp: RedirectResponse, *, access: str, refresh: str) -> None:
    access_max_age = int(settings.access_token_minutes) * 60
    refresh_max_age = int(settings.refresh_token_days) * 24 * 60 * 60
    resp.set_cookie(
        settings.cookie_name_access,
        access,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=access_max_age,
    )
    resp.set_cookie(
        settings.cookie_name_refresh,
        refresh,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=refresh_max_age,
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "tenant": "default"})


@router.post("/login")
def login_action(
    request: Request,
    tenant: str = Form(default="default"),
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    tenant_name = (tenant or "default").strip() or "default"
    tenant_row = db.query(Tenant).filter(Tenant.name == tenant_name).first()
    if tenant_row is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Unknown tenant. Use 'default' or create one.", "tenant": tenant_name},
            status_code=500,
        )

    user = (
        db.query(User)
        .filter(User.tenant_id == tenant_row.id)
        .filter(User.username == username.strip())
        .first()
    )
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password", "tenant": tenant_name},
            status_code=401,
        )

    access = create_access_token(sub=str(user.id), tenant_id=user.tenant_id, role=user.role)
    refresh = create_refresh_token(sub=str(user.id), tenant_id=user.tenant_id, role=user.role)
    resp = RedirectResponse(url="/dashboard", status_code=302)
    _set_auth_cookies(resp, access=access, refresh=refresh)
    return resp


@router.post("/logout")
def logout_action():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(settings.cookie_name_access, path="/")
    resp.delete_cookie(settings.cookie_name_refresh, path="/")
    return resp

