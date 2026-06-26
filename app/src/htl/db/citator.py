"""Open-citator ORM models.

The data foundation for the "does case X still stand?" feature:

- ``cl_opinions``  — one row per opinion/cluster we know about (a target case or
  one of its citers), keyed by its CourtListener id.
- ``citation_edges`` — the who-cites-whom graph (an edge ``citing → cited``).
- ``treatments`` — how a citer treats the cited case (overruled, distinguished,
  …). Created empty here; a later agent classifies passages into rows.

Populated by ``app/scripts/ingest_citator.py``. ``citing_id``/``cited_id`` are
CourtListener ids, not FKs: the graph tolerates an edge whose endpoint row hasn't
been ingested yet (ponytail — add FKs only if a real query needs the guarantee).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, Float, Integer, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from htl.db.base import Base


class ClOpinion(Base):
    __tablename__ = "cl_opinions"

    # The CourtListener opinion/cluster id — supplied by the source, not generated.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    cluster_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    case_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    court: Mapped[str | None] = mapped_column(Text, nullable=True)  # court id, e.g. 'scotus'
    date_filed: Mapped[date | None] = mapped_column(Date, nullable=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. '410 U.S. 113'
    plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provenance: 'cl_api' | 'cl_bulk' | 'cap' | 'seed'.
    source: Mapped[str | None] = mapped_column(Text, nullable=True)


class CitationEdge(Base):
    __tablename__ = "citation_edges"

    # Composite PK doubles as the unique(citing_id, cited_id) constraint.
    citing_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cited_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Treatment(Base):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    citing_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cited_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)  # overruled|distinguished|…
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_other_grounds: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
