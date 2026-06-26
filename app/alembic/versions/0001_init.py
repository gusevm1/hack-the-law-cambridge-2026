"""initial schema: users + messages, seed the stub user

Hand-written (autogenerate needs a live DB). From 0002 onwards,
``alembic revision --autogenerate`` is the standard path.

Revision ID: 0001
Revises:
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Matches htl.auth.stub.STUB_USER_ID — seeded so message FKs resolve when the
# stub verifier runs against a real database (local / pre-Supabase deploys).
STUB_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("supabase_sub", sa.Text(), nullable=True, unique=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # CAST so pg8000's varchar bind lands in the uuid column.
    op.execute(
        sa.text("INSERT INTO users (id, email) VALUES (CAST(:id AS uuid), :email)").bindparams(
            id=STUB_USER_ID, email="dev@htl.local"
        )
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("users")
