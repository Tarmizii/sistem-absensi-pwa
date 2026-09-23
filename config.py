"""Configuration for the minimal application foundation."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path


class Config:
    """Environment-backed settings shared by the Flask application."""

    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-only-change-me"
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = APP_ENV == "development"
    TESTING = APP_ENV == "testing"
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "sistem_absensi")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Jakarta")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    STORAGE_ROOT = os.getenv("STORAGE_ROOT") or str(Path(__file__).parent / "storage")
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    MAX_FORM_MEMORY_SIZE = 64 * 1024
    MAX_FORM_PARTS = 20

    @classmethod
    def validate(cls, config=None) -> None:
        """Fail clearly when production is started without a real secret."""

        if config is None:
            config = {
                "APP_ENV": cls.APP_ENV,
                "SECRET_KEY": cls.SECRET_KEY,
                "DB_PASSWORD": cls.DB_PASSWORD,
                "DEBUG": cls.DEBUG,
                "SESSION_COOKIE_SECURE": cls.SESSION_COOKIE_SECURE,
            }
        if config["APP_ENV"] != "production":
            return
        if not config["SECRET_KEY"] or config["SECRET_KEY"] in {
            "dev-only-change-me", "change-me-local-only", "dev-local-only"
        }:
            raise RuntimeError("SECRET_KEY production harus diganti dari contoh development.")
        if not config["DB_PASSWORD"]:
            raise RuntimeError("DB_PASSWORD wajib diisi saat APP_ENV=production.")
        if config["DEBUG"] or not config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("Production memerlukan DEBUG=False dan cookie Secure.")
