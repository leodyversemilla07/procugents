"""Tests for the prod-safe ``init_db`` and Alembic migrations.

Validates:

* SQLite: ``init_db()`` recreates the schema on demand (dev convenience).
* PostgreSQL: ``init_db()`` refuses to silently create the schema unless
  the ``alembic_version`` table is present.
* Alembic migrations apply cleanly against a fresh SQLite database
  (proxy for the production PostgreSQL behaviour: identical DDL minus
  dialect-specific options).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def fresh_sqlite(tmp_path, monkeypatch):
    """Return a fresh sqlite URL with a clean DB file."""
    db_path = tmp_path / "procugents_test.db"
    url = f"sqlite:///{db_path}"
    # Reset DATABASE_URL & re-import to pick up the new path.
    monkeypatch.setenv("POSTGRES_PASSWORD", "")  # ensure SQLite branch
    yield url, db_path


def test_init_db_creates_tables_on_sqlite(fresh_sqlite, monkeypatch):
    """SQLite dev convenience: ``Base.metadata.create_all`` runs unconditionally."""
    url, db_path = fresh_sqlite

    # Re-import database module so its module-level DATABASE_URL binding
    # takes the new env.
    import importlib
    import src.services.database as database_mod
    importlib.reload(database_mod)
    monkeypatch.setattr(database_mod, "DATABASE_URL", url)
    monkeypatch.setattr(database_mod, "engine", database_mod._build_engine(url))

    database_mod.init_db()

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        table_names = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        # The dev branch deliberately does NOT populate alembic_version.
        assert "procurement_analysis" in table_names
        assert "alerts" in table_names
        assert "agencies" in table_names
        assert "alembic_version" not in table_names
    finally:
        con.close()


def test_init_db_refuses_postgres_without_alembic(monkeypatch):
    """When the DATABASE_URL points to PostgreSQL but the schema is unmanaged,
    ``init_db`` raises a clear error.
    """
    import src.services.database as database_mod

    fake_url = "postgresql://user:pass@localhost:5432/db"
    fake_engine = MagicMock()
    fake_inspector = MagicMock()
    fake_inspector.get_table_names.return_value = {"procurement_analysis"}

    monkeypatch.setattr(database_mod, "DATABASE_URL", fake_url)
    monkeypatch.setattr(database_mod, "_using_sqlite", lambda: False)
    monkeypatch.setattr(database_mod, "engine", fake_engine)
    monkeypatch.setattr(
        "sqlalchemy.inspect",
        lambda _e: fake_inspector,
        raising=True,
    )

    with pytest.raises(RuntimeError) as excinfo:
        database_mod.init_db()
    assert "alembic upgrade head" in str(excinfo.value)


def test_init_db_succeeds_when_alembic_present(monkeypatch):
    """The PostgreSQL path passes when alembic_version + required tables exist."""
    import src.services.database as database_mod

    fake_inspector = MagicMock()
    fake_inspector.get_table_names.return_value = {
        "procurement_analysis",
        "alerts",
        "agencies",
        "alembic_version",
    }
    monkeypatch.setattr(database_mod, "_using_sqlite", lambda: False)
    monkeypatch.setattr(database_mod, "DATABASE_URL", "postgresql://x/y")
    monkeypatch.setattr(database_mod, "engine", MagicMock())
    monkeypatch.setattr(
        "sqlalchemy.inspect", lambda _e: fake_inspector, raising=True
    )

    # Should not raise.
    database_mod.init_db()


def test_init_db_blocked_when_required_table_missing(monkeypatch):
    """Even with alembic_version present, missing required tables raise."""
    import src.services.database as database_mod

    fake_inspector = MagicMock()
    fake_inspector.get_table_names.return_value = {"alembic_version"}  # no procurement_analysis
    monkeypatch.setattr(database_mod, "_using_sqlite", lambda: False)
    monkeypatch.setattr(database_mod, "engine", MagicMock())
    monkeypatch.setattr(
        "sqlalchemy.inspect", lambda _e: fake_inspector, raising=True
    )

    with pytest.raises(RuntimeError) as excinfo:
        database_mod.init_db()
    assert "Required tables missing" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Migration round-trip
# ---------------------------------------------------------------------------


def test_alembic_baseline_migration_creates_tables(tmp_path):
    """``alembic upgrade head`` from a clean SQLite DB materializes all tables.

    Validates the migration by running it programmatically (avoids spawning
    a subprocess; the env imports ``src.services.database`` like the CLI does).
    """
    db_path = tmp_path / "procugents_alembic.db"
    import os
    os.environ["PROCU_TEST_DB_URL"] = f"sqlite:///{db_path}"

    # Configure Alembic programmatically per test.
    from alembic.config import Config
    from alembic import command

    repo_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["PROCU_TEST_DB_URL"])

    # Sanity: db file is empty.
    assert not db_path.exists() or db_path.stat().st_size < 4096

    command.upgrade(cfg, "head")

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        tables = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "procurement_analysis" in tables
        assert "alerts" in tables
        assert "agencies" in tables
        assert "alembic_version" in tables
        revision = next(
            cur.execute("SELECT version_num FROM alembic_version")
        )[0]
        assert revision == "311a544d848f"
    finally:
        con.close()


def test_alembic_downgrade_then_upgrade(tmp_path):
    """``downgrade base`` then ``upgrade head`` is the full round-trip."""
    db_path = tmp_path / "procugents_downgrade.db"
    url = f"sqlite:///{db_path}"

    from alembic.config import Config
    from alembic import command

    repo_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        tables = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        # After downgrade to base, application tables are dropped.
        # alembic empties the version row (downgrading to base clears it).
        assert "procurement_analysis" not in tables
        assert "alerts" not in tables
        assert "agencies" not in tables
        rows = list(cur.execute("SELECT version_num FROM alembic_version"))
        if rows:
            assert rows[0][0] == ""
    finally:
        con.close()

    # Re-upgrade should rebuild everything; we open a fresh connection
    # since the previous cursor/connection is closed.
    command.upgrade(cfg, "head")
    con = sqlite3.connect(str(db_path))
    try:
        rows = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        assert "procurement_analysis" in rows
        assert "alembic_version" in rows
        rev = next(con.execute("SELECT version_num FROM alembic_version"))[0]
        assert rev == "311a544d848f"
    finally:
        con.close()
