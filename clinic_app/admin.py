from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from clinic_app.db import get_db
from clinic_app.deps import CurrentUser, require_role
from clinic_app.models import Tenant, User
from clinic_app.security import hash_password


router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="clinic_app/templates")


@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users = (
        db.query(User)
        .filter(User.tenant_id == user.tenant_id)
        .order_by(User.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "user": user, "users": users},
    )


@router.post("/users/new")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    uname = username.strip()
    role_v = (role or "staff").strip().lower()
    if role_v not in {"admin", "staff", "demo"}:
        role_v = "staff"

    new_user = User(
        tenant_id=user.tenant_id,
        username=uname,
        password_hash=hash_password(password),
        role=role_v,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/tenants", response_class=HTMLResponse)
def tenants_page(
    request: Request,
    user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_tenants.html",
        {"request": request, "user": user, "tenants": tenants},
    )


@router.post("/tenants/new")
def create_tenant(
    name: str = Form(...),
    admin_password: str = Form(...),
    user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    tname = name.strip()
    tenant = db.query(Tenant).filter(Tenant.name == tname).first()
    if tenant is None:
        tenant = Tenant(name=tname)
        db.add(tenant)
        db.flush()

        admin = User(
            tenant_id=tenant.id,
            username="admin",
            password_hash=hash_password(admin_password),
            role="admin",
            is_active=True,
        )
        db.add(admin)

    db.commit()
    return RedirectResponse(url="/admin/tenants", status_code=302)

