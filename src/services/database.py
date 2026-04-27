"""
Database models and connection for RedFlag Agents PH.
Supports both PostgreSQL (production) and SQLite (development).
"""

import os
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Enum, Float, Integer, String, Text, create_engine
# Use JSON for SQLite, JSONB for PostgreSQL
import os
if os.environ.get("POSTGRES_PASSWORD"):
    from sqlalchemy.dialects.postgresql import JSONB as JSON_TYPE
else:
    from sqlalchemy import JSON as JSON_TYPE
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    LEGAL_CHECK = "legal_check"
    PRICE_CHECK = "price_check"
    SCRAPING = "scraping"
    ALERTING = "alerting"
    COMPLETED = "completed"
    ERROR = "error"


class Base(DeclarativeBase):
    pass


class ProcurementAnalysis(Base):
    """Table for storing procurement analysis results."""
    __tablename__ = "procurement_analysis"

    id = Column(Integer, primary_key=True)
    contract_id = Column(String(100), nullable=False, index=True)
    contract_description = Column(Text, nullable=False)
    contract_amount = Column(Float, nullable=False)
    agency = Column(String(200))
    svp_category = Column(String(50))

    # Results
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    legal_findings = Column(JSON_TYPE)
    price_findings = Column(JSON_TYPE)
    scraping_results = Column(JSON_TYPE)
    llm_analysis = Column(JSON_TYPE)
    anomalies = Column(JSON_TYPE)
    alerts_created = Column(JSON_TYPE)
    error = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class Agency(Base):
    """Table for government agencies."""
    __tablename__ = "agencies"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    acronym = Column(String(20))
    uacs_code = Column(String(50))
    region = Column(String(50))
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


# Database URL - supports both PostgreSQL and SQLite
def _get_database_url() -> str:
    """Get database URL from environment or use SQLite default."""
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5432")
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "")
    pg_db = os.environ.get("POSTGRES_DB", "redflag_agents")

    if pg_pass:
        return f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"

    # Use SQLite for development
    db_path = os.environ.get("DATABASE_PATH", "/home/ubuntu/workspace/procure-agents/procure.db")
    return f"sqlite:///{db_path}"


DATABASE_URL = _get_database_url()

# Engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_db() -> Session:
    """Get database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


# Pydantic models for API
class ProcurementCreate(BaseModel):
    contract_id: str
    contract_description: str
    contract_amount: float
    agency: str = ""
    svp_category: str = "general"


class AnalysisResponse(BaseModel):
    id: int
    contract_id: str
    contract_description: str
    contract_amount: float
    agency: str = ""
    status: str
    legal_findings: dict[str, Any] | None = None
    price_findings: dict[str, Any] | None = None
    scraping_results: dict[str, Any] | None = None
    llm_analysis: dict[str, Any] | None = None
    anomalies: list[dict[str, Any]] = []
    alerts_created: list[dict[str, Any]] = []
    error: str | None = None
    created_at: datetime


class AlertCreate(BaseModel):
    title: str
    description: str = ""
    level: str = "medium"
    severity: str = "medium"
    contract_id: str = ""