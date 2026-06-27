"""Load a pg_dump COPY-format dump into the citator DB via the Cloud SQL connector
(ADC + Secret Manager creds — same path as `just migrate`, no psql/proxy needed).

TRUNCATEs the three citator tables and bulk-loads the dump's COPY blocks with
asyncpg's native text-format COPY (Postgres does the parsing + type coercion).
Atomic: all-or-nothing in one transaction.

    DRY=1 uv run python scripts/load_dump.py /path/to/citator-dump.sql   # parse only
        uv run python scripts/load_dump.py /path/to/citator-dump.sql    # load
"""
import asyncio
import io
import os
import re
import sys

from htl.db.engine import dispose_engine, get_engine

TABLES = {
    "citation_edges": ["citing_id", "cited_id", "depth"],
    "cl_opinions": ["id", "cluster_id", "case_name", "court", "date_filed",
                    "citation", "plain_text", "source"],
    "treatments": ["id", "citing_id", "cited_id", "type", "scope", "on_other_grounds",
                   "quote", "confidence", "model", "created_at"],
}


def extract_blocks(text: str) -> dict[str, str]:
    """The raw COPY data (between 'COPY ... FROM stdin;' and the '\\.' terminator)."""
    out = {}
    for table in TABLES:
        m = re.search(rf"COPY public\.{table} \([^)]*\) FROM stdin;\n(.*?)\n\\\.\n",
                      text, re.DOTALL)
        out[table] = m.group(1) if m else ""
    return out


async def main(path: str, dry: bool) -> None:
    blocks = extract_blocks(open(path, encoding="utf-8").read())
    for t, data in blocks.items():
        print(f"  {t}: {len(data.splitlines()) if data else 0} rows parsed")
    if dry:
        print("DRY run — nothing written.")
        return

    engine = get_engine()
    async with engine.connect() as conn:
        apg = (await conn.get_raw_connection()).driver_connection
        async with apg.transaction():
            await apg.execute(
                "TRUNCATE public.citation_edges, public.cl_opinions, "
                "public.treatments RESTART IDENTITY;")
            for table, cols in TABLES.items():
                data = blocks[table]
                if not data:
                    continue
                await apg.copy_to_table(
                    table, schema_name="public", columns=cols,
                    source=io.BytesIO(data.encode("utf-8")), format="text")
                print(f"  loaded {table}")
    await dispose_engine()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], bool(os.environ.get("DRY"))))
