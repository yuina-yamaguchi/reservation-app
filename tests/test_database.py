from sqlalchemy.pool import NullPool

from app import database


def test_turso_engine_uses_nullpool(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "token")
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)

    database._create_engine()

    assert captured["url"] == "sqlite+libsql://example.turso.io?secure=true"
    assert captured["connect_args"] == {"auth_token": "token"}
    assert captured["poolclass"] is NullPool
    assert captured["pool_reset_on_return"] is None


def test_libsql_database_url_uses_nullpool(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+libsql://example.turso.io")
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)

    database._create_engine()

    assert captured["url"] == "sqlite+libsql://example.turso.io"
    assert captured["connect_args"] == {"check_same_thread": False}
    assert captured["poolclass"] is NullPool
    assert captured["pool_reset_on_return"] is None
