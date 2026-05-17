"""runs table (M5 — run lifecycle).

Revision ID: 0002_runs
Revises: 0001_initial_schema
Create Date: 2026-05-17

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_runs"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RUN_STATUSES = (
    "running",
    "awaiting_human",
    "succeeded",
    "failed",
    "cancelled",
)


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "graph_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("graph_version", sa.BigInteger, nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column(
            "inputs",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "started_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.CheckConstraint(
            f"status IN {RUN_STATUSES!r}", name="ck_runs_status"
        ),
        sa.ForeignKeyConstraint(
            ["graph_id", "graph_version"],
            ["graph_versions.graph_id", "graph_versions.version"],
            ondelete="RESTRICT",
            name="fk_runs_graph_version",
        ),
    )

    op.create_index(
        "ix_runs_graph_id", "runs", ["graph_id"], unique=False
    )
    op.create_index(
        "ix_runs_status", "runs", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_graph_id", table_name="runs")
    op.drop_table("runs")
