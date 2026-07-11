"""Engine + session factory + ``init_db`` semantics.

Defines:
    * ``engine``     : SQLAlchemy engine built from the DATABASE_URL env.
    * ``SessionLocal``: sessionmaker bound to that engine.
    * ``get_db``     : context-managed session.
    * ``init_db``    : SQLite convenience helper. For PostgreSQL, run
                       ``alembic upgrade head`` instead.

The SQLAlchemy models live in :mod:`src.services.db_models` so that
alembic's ``env.py`` can import them without triggering this module's
runtime side-effects.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.services.db_models import (
    Base,
    Agency,
    Alert,
    AnalysisStatus,
    ProcurementAnalysis,
    utc_now,
)


__all__ = [
    "Base",
    "Alert",
    "Agency",
    "AnalysisStatus",
    "ProcurementAnalysis",
    "utc_now",
    "engine",
    "SessionLocal",
    "DATABASE_URL",
    "get_db",
    "init_db",
]


# ---------------------------------------------------------------------------
# Engine + Session
# ---------------------------------------------------------------------------


def _get_database_url() -> str:
    """Compose the database URL from ``POSTGRES_*`` env vars; fall back to SQLite."""
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5432")
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "")
    pg_db = os.environ.get("POSTGRES_DB", "redflag_agents")

    if pg_pass:
        return f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    return "sqlite:///procugents.db"


DATABASE_URL = _get_database_url()
SUPPORTS_MIGRATIONS = not DATABASE_URL.startswith("sqlite:")


def _build_engine(url: str):
    if url.startswith("sqlite:"):
        return create_engine(url, echo=False, connect_args={"check_same_thread": False})
    return create_engine(url, echo=False, pool_pre_ping=True)


engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


@contextmanager
def get_db() -> Iterator[Session]:
    """Yield a SQLAlchemy session, committing on success and rolling back on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# init_db: SQLite-only convenience. Production callers must run migrations.
# ---------------------------------------------------------------------------


def _using_sqlite() -> bool:
    return DATABASE_URL.startswith("sqlite:")


def init_db() -> None:
    """Initialise the database.

    SQLite (development):
        For convenience this creates any tables that are missing using
        ``Base.metadata.create_all``. NEVER call this on production data:
        SQLite has no concept of migrations and any schema change after a
        row of data exists silently breaks.  Use ``init_db`` only in unit
        tests / local development.

    PostgreSQL (production):
        Raises ``RuntimeError`` unless the alembic version table is present,
        so operators cannot accidentally bypass migrations. Use:

            alembic upgrade head

        We do not call ``create_all`` because that does not record the
        schema in the version table, and any later ``alembic upgrade`` will
        try to ``drop`` columns alembic has no record of.
    """
    if _using_sqlite():
        Base.metadata.create_all(bind=engine)
        return

    # Production-mode. Confirm the schema is under migration control, otherwise
    # block startup rather than silently creating tables that alembic doesn't
    # know about.
    from sqlalchemy import inspect
    from sqlalchemy.exc import DBAPIError

    insp = inspect(engine)
    try:
        tables = set(insp.get_table_names())
    except DBAPIError as exc:  # pragma: no cover - DB config issue
        raise RuntimeError(
            f"Could not connect to PostgreSQL at {DATABASE_URL!r}: {exc}"
        )

    if "alembic_version" not in tables:
        raise RuntimeError(
            "PostgreSQL database is not under migration control. Run "
            "'alembic upgrade head' before starting ProCuGents. "
            "See docs/migrations.md for details."
        )

    # Defensive: if for some reason the user meta-table is missing, raise.
    required = {"procurement_analysis", "alerts", "agencies"}
    missing = required - tables
    if missing:
        raise RuntimeError(
            f"Required tables missing from PostgreSQL: {sorted(missing)}. "
            "Run 'alembic upgrade head' to apply pending migrations."
        )


# ---------------------------------------------------------------------------
# Pydantic API models (unchanged API surface)
# ---------------------------------------------------------------------------


class ProcurementCreate(BaseModel):
    contract_id: str
    contract_description: str
    contract_amount: float
    agency: str = ""
    source: str = ""
    svp_category: str = "general"


class AnalysisResponse(BaseModel):
    id: int
    contract_id: str
    contract_description: str
    contract_amount: float
    agency: str = ""
    source: str = ""
    status: str
    legal_findings: dict | None = None
    price_findings: dict | None = None
    scraping_results: dict | None = None
    llm_analysis: dict | None = None
    anomalies: list[dict] = []
    alerts_created: list[dict] = []
    error: str | None = None
    created_at: datetime
