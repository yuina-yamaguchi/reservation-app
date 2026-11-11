import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "reservation_app.db"


def _create_engine():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        if "libsql" in database_url:
            return create_engine(
                database_url,
                connect_args=connect_args,
                poolclass=NullPool,
                pool_reset_on_return=None,
            )
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
            poolclass=NullPool,
            pool_reset_on_return=None,
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


SCHEMA_ADDITIONS = (
    ("reservations", "note_public", "BOOLEAN NOT NULL DEFAULT 0"),
    ("ride_shares", "note_public", "BOOLEAN NOT NULL DEFAULT 0"),
    ("digital_keys", "lock_state", "VARCHAR(20) NOT NULL DEFAULT 'locked'"),
)


def _widen_payment_type_column() -> None:
    """reservation_charges.payment_type を VARCHAR(20) に拡張（SQLite 再構築）。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "reservation_charges" not in tables:
        return
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reservation_charges_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reservation_id INTEGER UNIQUE REFERENCES reservations(id),
                    car_id INTEGER NOT NULL REFERENCES cars(id),
                    ticket_user_id INTEGER REFERENCES users(id),
                    ticket_id INTEGER REFERENCES time_tickets(id),
                    payment_type VARCHAR(20) NOT NULL DEFAULT 'time',
                    duration_minutes INTEGER NOT NULL DEFAULT 0,
                    vehicle_value INTEGER NOT NULL DEFAULT 0,
                    incremental_amount INTEGER NOT NULL DEFAULT 0,
                    overflow_amount INTEGER NOT NULL DEFAULT 0,
                    seat_fee_total INTEGER NOT NULL DEFAULT 0,
                    discount_applied INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    reservation_start DATETIME,
                    reservation_end DATETIME,
                    snapshot TEXT NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT OR IGNORE INTO reservation_charges_new
                SELECT id, reservation_id, car_id, ticket_user_id, ticket_id,
                       payment_type, duration_minutes, vehicle_value,
                       incremental_amount, overflow_amount, seat_fee_total,
                       discount_applied, status, reservation_start,
                       reservation_end, snapshot, created_at
                FROM reservation_charges
                """
            )
        )
        connection.execute(text("DROP TABLE reservation_charges"))
        connection.execute(
            text("ALTER TABLE reservation_charges_new RENAME TO reservation_charges")
        )


def apply_schema_upgrades() -> None:
    """既存テーブルに後から追加した列を作成する。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, column, definition in SCHEMA_ADDITIONS:
        if table not in tables:
            continue
        columns = {item["name"] for item in inspector.get_columns(table)}
        if column in columns:
            continue
        with engine.begin() as connection:
            connection.execute(
                text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            )
    _widen_payment_type_column()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
