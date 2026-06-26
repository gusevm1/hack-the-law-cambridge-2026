"""open-citator tables: cl_opinions + citation_edges + treatments

Hand-written (autogenerate needs a live DB), matching 0001's style.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cl_opinions",
        # CourtListener opinion/cluster id — supplied, not generated.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("cluster_id", sa.BigInteger(), nullable=True),
        sa.Column("case_name", sa.Text(), nullable=True),
        sa.Column("court", sa.Text(), nullable=True),
        sa.Column("date_filed", sa.Date(), nullable=True),
        sa.Column("citation", sa.Text(), nullable=True),
        sa.Column("plain_text", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
    )

    op.create_table(
        "citation_edges",
        # Composite PK doubles as unique(citing_id, cited_id).
        sa.Column("citing_id", sa.BigInteger(), primary_key=True),
        sa.Column("cited_id", sa.BigInteger(), primary_key=True),
        sa.Column("depth", sa.Integer(), nullable=True),
    )
    # Lookups walk both directions of the graph.
    op.create_index("citation_edges_cited_id_idx", "citation_edges", ["cited_id"])

    op.create_table(
        "treatments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("citing_id", sa.BigInteger(), nullable=False),
        sa.Column("cited_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("on_other_grounds", sa.Boolean(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("treatments_cited_id_idx", "treatments", ["cited_id"])


def downgrade() -> None:
    op.drop_table("treatments")
    op.drop_table("citation_edges")
    op.drop_table("cl_opinions")
