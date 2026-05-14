import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
SQLITE_DATABASE_PATH = INSTANCE_DIR / "lido.sqlite3"


class Config:
    SECRET_KEY = os.environ.get(
        "LIDO_SECRET_KEY",
        "dev-secret-key-change-this-before-production",
    )

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "LIDO_DATABASE_URL",
        f"sqlite:///{SQLITE_DATABASE_PATH.as_posix()}",
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    APP_NAME = "Lido Masa Takip Sistemi"