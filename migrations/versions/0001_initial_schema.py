"""Initial schema: identity (users, roles, user_roles) + graph storage (graphs, graph_versions).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-17

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GRAPH_STATUSES = ("draft", "active", "archived")
DEFAULT_ROLES = ("admin", "approver", "editor")
SYSTEM_USER_NAME = "system"
SYSTEM_USER_EMAIL = "system@local"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            sa.BigInteger,
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "graphs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "latest_version",
            sa.BigInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN {GRAPH_STATUSES!r}", name="ck_graphs_status"
        ),
    )

    op.create_table(
        "graph_versions",
        sa.Column(
            "graph_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graphs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version", sa.BigInteger, primary_key=True),
        sa.Column("definition", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── Seed default roles and the system user ────────────────────────────
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.BigInteger),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        roles_table, [{"name": role_name} for role_name in DEFAULT_ROLES]
    )

    users_table = sa.table(
        "users",
        sa.column("id", sa.BigInteger),
        sa.column("name", sa.String),
        sa.column("email", sa.String),
    )
    op.bulk_insert(
        users_table,
        [{"name": SYSTEM_USER_NAME, "email": SYSTEM_USER_EMAIL}],
    )

    # Give `system` the admin role.
    op.execute(
        """
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u, roles r
        WHERE u.name = 'system' AND r.name = 'admin'
        """
    )


def downgrade() -> None:
    op.drop_table("graph_versions")
    op.drop_table("graphs")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
