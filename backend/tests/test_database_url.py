"""Hosting providers hand out database URLs the async driver cannot use as-is.
Getting this wrong fails only at connect time, on the deployed service."""

from app.db.engine import prepare_database_url


def test_neon_style_url_is_rewritten_for_asyncpg():
    url, args = prepare_database_url(
        "postgresql://user:p%40ss@ep-cool.neon.tech/db"
        "?sslmode=require&channel_binding=require"
    )

    assert url.startswith("postgresql+asyncpg://user:p%40ss@ep-cool.neon.tech/db")
    assert "sslmode" not in url
    assert "channel_binding" not in url
    assert args == {"ssl": True}


def test_legacy_postgres_scheme_is_accepted():
    url, args = prepare_database_url("postgres://u:p@host:5432/db?sslmode=require")

    assert url.startswith("postgresql+asyncpg://u:p@host:5432/db")
    assert args == {"ssl": True}


def test_url_without_sslmode_gets_no_ssl_argument():
    url, args = prepare_database_url("postgresql://u:p@localhost/db")

    assert url == "postgresql+asyncpg://u:p@localhost/db"
    assert args == {}


def test_already_prefixed_url_is_left_working():
    url, _ = prepare_database_url("postgresql+asyncpg://u:p@host/db?sslmode=require")

    assert url.startswith("postgresql+asyncpg://u:p@host/db")
    assert "sslmode" not in url


def test_sqlite_url_is_untouched():
    original = "sqlite+aiosqlite:///./data/voice_ai.db"

    assert prepare_database_url(original) == (original, {})


def test_password_survives_the_round_trip():
    url, _ = prepare_database_url("postgresql://u:a%2Fb%3Fc@host/db")

    assert "a%2Fb%3Fc" in url
