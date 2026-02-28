from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from clinic_app.settings import settings


BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "clinic_app_data"
DB_DIR.mkdir(exist_ok=True)


def _db_url() -> str:
    env = (settings.app_env or "demo").lower().strip()
    if env not in {"demo", "prod"}:
        env = "demo"
    db_path = DB_DIR / f"{env}.sqlite3"
    return f"sqlite:///{db_path.as_posix()}"


engine = create_engine(
    _db_url(),
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
