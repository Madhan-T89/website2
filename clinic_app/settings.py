from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "demo"  # demo|prod
    jwt_secret: str | None = None
    jwt_issuer: str = "clinic-app"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    cookie_name_access: str = "access_token"
    cookie_name_refresh: str = "refresh_token"

    clinic_name_default: str = "MP Sidha Medicines Clinic"
    clinic_phone_default: str = ""
    clinic_address_default: str = ""


settings = Settings()
