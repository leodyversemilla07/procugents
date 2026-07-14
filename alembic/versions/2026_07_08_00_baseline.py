"""baseline schema

Creates the initial ProCuGents production schema mirroring the SQLAlchemy
declarative metadata in ``src.services.db_models``. After this revision,
all three tables (procurement_analysis, alerts, agencies) exist with the
shape expected by the rest of the application.

Revision ID: 2026_07_08_00-baseline
Revises:
Create Date: 2026-07-08 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2026_07_08_00"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "procurement_analysis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.String(length=100), nullable=False),
        sa.Column("contract_description", sa.Text(), nullable=False),
        sa.Column("contract_amount", sa.Float(), nullable=False),
        sa.Column("agency", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("svp_category", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "legal_check",
                "price_check",
                "scraping",
                "alerting",
                "completed",
                "error",
                name="analysisstatus",
            ),
            nullable=True,
        ),
        sa.Column("legal_findings", json_type, nullable=True),
        sa.Column("price_findings", json_type, nullable=True),
        sa.Column("scraping_results", json_type, nullable=True),
        sa.Column("llm_analysis", json_type, nullable=True),
        sa.Column("anomalies", json_type, nullable=True),
        sa.Column("alerts_created", json_type, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("bid_findings", json_type, nullable=True),
        sa.Column("bid_flags", json_type, nullable=True),
        sa.Column("bid_risk_score", sa.Integer(), nullable=True),
        sa.Column("doc_findings", json_type, nullable=True),
        sa.Column("doc_flags", json_type, nullable=True),
        sa.Column("doc_risk_score", sa.Integer(), nullable=True),
        sa.Column("final_risk_score", sa.Integer(), nullable=True),
        sa.Column("all_flags", json_type, nullable=True),
        sa.Column("all_citations", json_type, nullable=True),
        sa.Column("alert_triggered", sa.Integer(), nullable=True),
        sa.Column("alert_report", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_procurement_analysis_contract_id",
        "procurement_analysis",
        ["contract_id"],
        unique=False,
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.String(length=20), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("contract_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_alerts_contract_id",
        "alerts",
        ["contract_id"],
        unique=False,
    )

    op.create_table(
        "agencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("acronym", sa.String(length=20), nullable=True),
        sa.Column("uacs_code", sa.String(length=50), nullable=True),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_agencies_name",
        "agencies",
        ["name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agencies_name", table_name="agencies")
    op.drop_table("agencies")
    op.drop_index("ix_alerts_contract_id", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_procurement_analysis_contract_id", table_name="procurement_analysis")
    op.drop_table("procurement_analysis")
