import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )


class Config:
    BASE_DIR = BASE_DIR

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "campus-attendance-dev-secret-change-me"
    )

    SQLALCHEMY_DATABASE_URI = (
        database_url
        or "sqlite:///" + os.path.join(
            BASE_DIR,
            "instance",
            "attendance.db"
        )
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET = os.environ.get(
        "JWT_SECRET",
        "jwt-campus-attendance-dev-secret-change-me"
    )

    JWT_ALGORITHM = "HS256"

    JWT_EXPIRY = timedelta(hours=12)

    FACE_MATCH_THRESHOLD = 0.50
    FACE_DESCRIPTOR_LENGTH = 128

    SESSION_TOKEN_LENGTH = 6
    DEFAULT_SESSION_DURATION_MINUTES = 10

    DEFAULT_GEOFENCE_RADIUS_METERS = 100

    CLASS_JOIN_CODE_LENGTH = 6

    ADMIN_EMAIL = os.environ.get(
        "ADMIN_EMAIL",
        "admin@attendai.local"
    )

    ADMIN_PASSWORD = os.environ.get(
        "ADMIN_PASSWORD",
        "admin123"
    )

    ADMIN_NAME = os.environ.get(
        "ADMIN_NAME",
        "Administrator"
    )

    # --- Email / OTP settings ---
    # Leave SMTP_USER/SMTP_PASSWORD unset to run in "dev mode": OTP codes
    # are printed to the server console instead of being emailed, so the
    # app works out of the box without any email account configured.
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = os.environ.get("SMTP_PORT", "587")
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "")

    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    OTP_MAX_ATTEMPTS = 5

    # --- Password rules ---
    PASSWORD_MIN_LENGTH = 7