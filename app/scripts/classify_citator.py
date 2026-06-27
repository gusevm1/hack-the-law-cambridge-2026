#!/usr/bin/env python
"""Populate ``treatments`` — classify the seeded citing passages.

For each inbound citation edge of a target case, take the citing opinion's
``plain_text`` snippet and classify how it treats the target (see
``htl.llm.classify``). Writes one ``treatments`` row per (citing, cited) pair.

Idempotent: pairs already present in ``treatments`` are skipped, so re-running
only fills gaps. Classification calls Vertex concurrently under a small semaphore
(polite; the user has unlimited GCP). On a Vertex failure each call falls back to
the keyword classifier, so the run always completes.

    cd app && uv run python scripts/classify_citator.py            # the 4 targets
    cd app && uv run python scripts/classify_citator.py --targets 108713
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import aliased

from htl.citator.risk import GROUND_TRUTH
from htl.db.citator import CitationEdge, ClOpinion, Treatment
from htl.db.engine import dispose_engine, get_session_factory
from htl.llm.classify import classify_treatment

DEFAULT_TARGETS = list(GROUND_TRUTH)  # Roe, Plessy, Bowers, Lochner


async def _unclassified(session, targets: list[int]) -> list[tuple]:
    """(citing_id, cited_id, passage, target_name, target_citation) needing a label."""
    citing = aliased(ClOpinion)
    target = aliased(ClOpinion)
    already = (
        select(Treatment.citing_id)
        .where(Treatment.citing_id == CitationEdge.citing_id)
        .where(Treatment.cited_id == CitationEdge.cited_id)
        .exists()
    )
    stmt = (
        select(
            CitationEdge.citing_id,
            CitationEdge.cited_id,
            citing.plain_text,
            target.case_name,
            target.citation,
        )
        .join(citing, citing.id == CitationEdge.citing_id)
        .join(target, target.id == CitationEdge.cited_id)
        .where(CitationEdge.cited_id.in_(targets))
        .where(citing.plain_text.isnot(None))
        .where(~already)
    )
    return list((await session.execute(stmt)).all())


async def run(targets: list[int], concurrency: int) -> None:
    factory = get_session_factory()
    async with factory() as session:
        pending = await _unclassified(session, targets)
        print(f"Classifying {len(pending)} unlabelled passage(s) across {len(targets)} target(s)…")
        if not pending:
            print("Nothing to do — all classified.")
            await dispose_engine()
            return

        sem = asyncio.Semaphore(concurrency)

        async def work(row):
            async with sem:
                return row, await classify_treatment(row.plain_text, row.case_name, row.citation)

        results = await asyncio.gather(*(work(r) for r in pending))

        by_target: dict[int, Counter] = {}
        models: Counter = Counter()
        for row, c in results:
            session.add(
                Treatment(
                    citing_id=row.citing_id,
                    cited_id=row.cited_id,
                    type=c.type,
                    scope=c.scope,
                    on_other_grounds=c.on_other_grounds,
                    quote=c.quote,
                    confidence=c.confidence,
                    model=c.model,
                )
            )
            by_target.setdefault(row.cited_id, Counter())[c.type] += 1
            models[c.model] += 1
        await session.commit()

    for cited_id, counts in by_target.items():
        print(f"- {cited_id}: {dict(counts)}")
    print(f"models used: {dict(models)}")
    await dispose_engine()


def main() -> None:
    p = argparse.ArgumentParser(description="Classify seeded passages into treatments.")
    p.add_argument(
        "--targets",
        default=",".join(map(str, DEFAULT_TARGETS)),
        help="comma-separated cited_id (cluster) ids (default: the 4 LoC targets)",
    )
    p.add_argument("--concurrency", type=int, default=5, help="max concurrent Vertex calls")
    args = p.parse_args()
    targets = [int(x) for x in args.targets.split(",") if x.strip()]
    asyncio.run(run(targets, args.concurrency))


if __name__ == "__main__":
    main()
