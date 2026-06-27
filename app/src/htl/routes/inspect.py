"""GET /cases/{id}/inspect — a raw DB dump for the dev data-inspector.

Not a product surface: this is the "show me everything we pulled, and why" view.
For a target it returns the target row, counts, and every inbound edge with its
citer metadata, provenance (source / depth / binding tier), the stored citing
passage (the "why"), and all treatments classified from it — including
*unclassified* edges, so recall gaps are visible. Public, read-only.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from htl.db.citator import CitationEdge, ClOpinion, Treatment
from htl.routes.dependencies import DbSession

router = APIRouter()

_FED_CIRCUIT = re.compile(r"^(ca\d+|cadc|cafc)$")
_PASSAGE_PREVIEW = 600


def _tier(court: str | None) -> str:
    if court == "scotus":
        return "binding · apex"
    if court and _FED_CIRCUIT.match(court):
        return "binding · circuit"
    return "persuasive / other"


def _opinion_url(citing_id: int, name: str | None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "case").lower()).strip("-") or "case"
    return f"https://www.courtlistener.com/opinion/{citing_id}/{slug}/"


@router.get("/cases/{case_id}/inspect")
async def inspect_case(case_id: int, session: DbSession) -> dict[str, Any]:
    target = (
        await session.execute(select(ClOpinion).where(ClOpinion.id == case_id))
    ).scalars().first()

    edge_rows = (
        await session.execute(
            select(
                ClOpinion.id,
                ClOpinion.case_name,
                ClOpinion.court,
                ClOpinion.date_filed,
                ClOpinion.citation,
                ClOpinion.source,
                ClOpinion.plain_text,
                CitationEdge.depth,
            )
            .join(CitationEdge, CitationEdge.citing_id == ClOpinion.id)
            .where(CitationEdge.cited_id == case_id)
        )
    ).all()

    treat_rows = (
        await session.execute(
            select(
                Treatment.citing_id,
                Treatment.type,
                Treatment.scope,
                Treatment.on_other_grounds,
                Treatment.confidence,
                Treatment.model,
                Treatment.quote,
            ).where(Treatment.cited_id == case_id)
        )
    ).all()
    by_citer: dict[int, list[dict[str, Any]]] = {}
    for t in treat_rows:
        by_citer.setdefault(t.citing_id, []).append({
            "type": t.type,
            "scope": t.scope,
            "on_other_grounds": bool(t.on_other_grounds),
            "confidence": t.confidence,
            "model": t.model,
            "quote": t.quote,
        })

    edges = []
    for r in edge_rows:
        passage = r.plain_text
        edges.append({
            "citing_id": r.id,
            "case_name": r.case_name,
            "court": r.court,
            "tier": _tier(r.court),
            "date_filed": r.date_filed.isoformat() if r.date_filed else None,
            "citation": r.citation,
            "source": r.source,  # provenance: cl_api | seed | …
            "depth": r.depth,
            "has_passage": bool(passage),
            "passage_chars": len(passage) if passage else 0,
            "passage_preview": (passage[:_PASSAGE_PREVIEW] if passage else None),
            "treatments": by_citer.get(r.id, []),
            "opinion_url": _opinion_url(r.id, r.case_name),
        })
    # Binding tier first, then most recent — the order a reviewer cares about.
    edges.sort(key=lambda e: (e["tier"].startswith("persuasive"), e["date_filed"] or ""),)

    total_edges = await session.scalar(
        select(func.count()).select_from(CitationEdge).where(CitationEdge.cited_id == case_id)
    )
    classified = sum(1 for e in edges if e["treatments"])
    return {
        "target": {
            "case_id": case_id,
            "case_name": target.case_name if target else None,
            "court": target.court if target else None,
            "date_filed": target.date_filed.isoformat() if target and target.date_filed else None,
            "citation": target.citation if target else None,
            "source": target.source if target else None,
            "in_db": target is not None,
        },
        "counts": {
            "edges": total_edges or 0,
            "classified": classified,
            "unclassified": (total_edges or 0) - classified,
            "with_passage": sum(1 for e in edges if e["has_passage"]),
            "binding": sum(1 for e in edges if e["tier"].startswith("binding")),
        },
        "edges": edges,
    }
