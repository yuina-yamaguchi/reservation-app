import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_password: str
    session_secret: str
    cookie_name: str
    cookie_secure: bool
    session_max_age: int
    login_max_attempts: int
    login_window_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_password = os.getenv("APP_PASSWORD", "").strip()
    session_secret = os.getenv("SESSION_SECRET", "").strip()

    if not app_password:
        raise RuntimeError(
            "APP_PASSWORD が設定されていません。環境変数または .env に設定してください。"
        )
    if not session_secret:
        raise RuntimeError(
            "SESSION_SECRET が設定されていません。環境変数または .env に設定してください。"
        )

    return Settings(
        app_password=app_password,
        session_secret=session_secret,
        cookie_name=(
            os.getenv("COOKIE_NAME", "reservation_session").strip()
            or "reservation_session"
        ),
        cookie_secure=_env_bool("COOKIE_SECURE", False),
        session_max_age=int(
            os.getenv("SESSION_MAX_AGE_SECONDS", str(60 * 60 * 24 * 30))
        ),
        login_max_attempts=int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")),
        login_window_seconds=int(os.getenv("LOGIN_WINDOW_SECONDS", "300")),
    )
