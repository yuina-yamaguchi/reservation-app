import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "reservation_app.db"


def _create_engine():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        return create_engine(database_url, connect_args=connect_args)

    turso_url = os.getenv("TURSO_DATABASE_URL", "").strip()
    turso_token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
    if bool(turso_url) != bool(turso_token):
        raise RuntimeError(
            "TURSO_DATABASE_URL と TURSO_AUTH_TOKEN は両方設定してください。"
        )
    if turso_url and turso_token:
        return create_engine(
            f"sqlite+{turso_url}?secure=true",
            connect_args={"auth_token": turso_token},
        )

    db_path = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    return create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
