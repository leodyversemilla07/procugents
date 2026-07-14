"""SQLAlchemy declarative base + table definitions.

This module is intentionally dependency-free (only imports the SQLAlchemy
declarative base and column types). Alembic's ``env.py`` imports this
module to autogenerate / hand-author migrations. Keep this file free of
runtime side-effects (no engine, no sessionmaker) so it remains safe to
import from migration scripts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    LEGAL_CHECK = "legal_check"
    PRICE_CHECK = "price_check"
    SCRAPING = "scraping"
    ALERTING = "alerting"
    COMPLETED = "completed"
    ERROR = "error"


Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(UTC)


# JSON-typed columns: in production (PostgreSQL) the `JSON_TYPE` switches to
# JSONB via the Postgres dialect; for SQLite we fall back to JSON. The
# migrations store both shapes correctly because alembic tracks the column
# type per dialect.
def _json_column():
    """Return a JSON/JSONB column. Resolved once per call at class-definition time."""
    import os

    if os.environ.get("POSTGRES_PASSWORD"):
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return JSON()


class ProcurementAnalysis(Base):
    """Table for storing procurement analysis results."""

    __tablename__ = "procurement_analysis"

    id = Column(Integer, primary_key=True)
    contract_id = Column(String(100), nullable=False, index=True)
    contract_description = Column(Text, nullable=False)
    contract_amount = Column(Float, nullable=False)
    agency = Column(String(200))
    source = Column(String(50))
    svp_category = Column(String(50))

    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    legal_findings = Column(_json_column())
    price_findings = Column(_json_column())
    scraping_results = Column(_json_column())
    llm_analysis = Column(_json_column())
    anomalies = Column(_json_column())
    alerts_created = Column(_json_column())
    error = Column(Text)

    bid_findings = Column(_json_column())
    bid_flags = Column(_json_column())
    bid_risk_score = Column(Integer)
    doc_findings = Column(_json_column())
    doc_flags = Column(_json_column())
    doc_risk_score = Column(Integer)

    final_risk_score = Column(Integer)
    all_flags = Column(_json_column())
    all_citations = Column(_json_column())
    alert_triggered = Column(Integer)
    alert_report = Column(Text)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Alert(Base):
    """Table for storing alerts."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    level = Column(String(20), default="medium")
    severity = Column(String(20), default="medium")
    contract_id = Column(String(100), index=True)
    status = Column(String(20), default="pending")
    resolution_notes = Column(Text)
    false_positive = Column(Integer, default=0)  # boolean — 1 = dismissed as FP
    fp_category = Column(String(50), nullable=True)  # e.g. threshold_too_low,
    created_at = Column(DateTime, default=utc_now)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_alerts_false_positive", "false_positive"),
    )


class Agency(Base):
    """Table for government agencies."""

    __tablename__ = "agencies"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    acronym = Column(String(20))
    uacs_code = Column(String(50))
    region = Column(String(50))
    category = Column(String(50))
    created_at = Column(DateTime, default=utc_now)


__all__ = [
    "Base",
    "AnalysisStatus",
    "ProcurementAnalysis",
    "Alert",
    "Agency",
    "utc_now",
]
