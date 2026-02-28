from __future__ import annotations

from sqlalchemy.orm import Session

from clinic_app.models import Tenant, User
from clinic_app.security import hash_password


def ensure_seed(db: Session) -> None:
    tenant = db.query(Tenant).filter(Tenant.name == "default").first()
    if tenant is None:
        tenant = Tenant(name="default")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

    admin = (
        db.query(User)
        .filter(User.tenant_id == tenant.id)
        .filter(User.username == "admin")
        .first()
    )
    if admin is None:
        admin = User(
            tenant_id=tenant.id,
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()

