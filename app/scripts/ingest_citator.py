#!/usr/bin/env python
"""Ingest the open-citator data foundation.

For a handful of landmark SCOTUS cases (all on the Library of Congress
"Decisions Overruled" list), this stores the case, the inbound citation graph
(who cites it → ``citation_edges``), and a bounded set of citing-passage texts
(→ ``cl_opinions.plain_text``) for a later agent to classify into ``treatments``.

Data source
-----------
The primary source is the CourtListener v4 **search** endpoint, which needs *no
token*: ``q=cites:(<opinion_id>)`` returns the inbound graph and ``highlight=on``
returns the citing passage as a snippet. A token is optional — when
``COURTLISTENER_TOKEN`` is set we additionally upgrade the bounded text subset
to full opinion text via ``/opinions/<id>/``, paced ≤ 4 req/min. If the live
source yields nothing (offline / blocked), we fall back to a small ``source='seed'``
set of real, well-known overrulings so downstream work isn't blocked.

Idempotent: opinions upsert (existing text is never overwritten with NULL) and
edges skip-existing, so re-running enriches rather than duplicates.

    cd app && uv run python scripts/ingest_citator.py
    cd app && uv run python scripts/ingest_citator.py --seed   # offline seed only
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from htl.db.citator import CitationEdge, ClOpinion
from htl.db.engine import dispose_engine, get_session_factory

CL_BASE = "https://www.courtlistener.com/api/rest/v4"
USER_AGENT = "htl-citator/0.1 (hack-the-law-cambridge-2026)"

# "Name|Citation" — the four landmark overrulings we seed the citator with.
DEFAULT_CASES = [
    "Roe v. Wade|410 U.S. 113",
    "Plessy v. Ferguson|163 U.S. 537",
    "Bowers v. Hardwick|478 U.S. 186",
    "Lochner v. New York|198 U.S. 45",
]

_TAG = re.compile(r"<[^>]+>")
_FED_APPELLATE = re.compile(r"^(ca\d+|cadc|cafc)$")

# macOS Pythons often lack a system CA bundle; certifi (a transitive dep) is the
# repo's standard fix (see the justfile's SSL_CERT_FILE dance for alembic).
try:
    import certifi

    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - certifi always present here
    _SSL_CTX = None

Search = Callable[[dict[str, Any]], dict[str, Any]]


# --------------------------------------------------------------------------- #
# Pure parsing helpers (unit-tested; no network, no DB).                       #
# --------------------------------------------------------------------------- #
def strip_highlight(s: str | None) -> str:
    """Drop the search highlighter's HTML tags and unescape entities."""
    return html.unescape(_TAG.sub("", s or "")).strip()


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def pick_citation(cit: Any, prefer: str | None = None) -> str | None:
    """Pick one citation string, preferring the official U.S. Reports cite."""
    if isinstance(cit, str):
        return cit or None
    if not cit:
        return None
    if prefer and prefer in cit:
        return prefer
    for c in cit:
        if " U.S. " in c:
            return c
    return cit[0]


def court_rank(court_id: str | None) -> int:
    """Lower is higher: SCOTUS < federal appellate < everything else."""
    if court_id == "scotus":
        return 0
    if court_id and _FED_APPELLATE.match(court_id):
        return 1
    return 2


def lead_opinion_id(result: dict[str, Any]) -> int | None:
    ops = result.get("opinions") or []
    return ops[0].get("id") if ops else result.get("cluster_id")


def result_snippet(result: dict[str, Any]) -> str | None:
    for o in result.get("opinions") or []:
        s = strip_highlight(o.get("snippet"))
        if s:
            return s
    return None


def opinion_row(result: dict[str, Any], *, source: str, citation: str | None = None,
                plain_text: str | None = None) -> dict[str, Any]:
    """Map a CL search result (a cluster) to a ``cl_opinions`` row."""
    return {
        "id": result["cluster_id"],
        "cluster_id": result.get("cluster_id"),
        "case_name": result.get("caseName"),
        "court": result.get("court_id"),
        "date_filed": parse_date(result.get("dateFiled")),
        "citation": citation or pick_citation(result.get("citation")),
        "plain_text": plain_text,
        "source": source,
    }


def opinion_full_text(op: dict[str, Any]) -> str | None:
    """Best available full text from an ``/opinions/<id>/`` payload."""
    if op.get("plain_text"):
        return op["plain_text"]
    for k in ("html_with_citations", "html", "html_lawbox", "xml_harvard"):
        if op.get(k):
            return strip_highlight(op[k])
    return None


_GENERIC_PARTY = frozenset(
    {"inc", "co", "corp", "llc", "ltd", "assn", "of", "the", "et", "al", "ex",
     "rel", "dept", "department", "commr", "commissioner", "united", "states",
     "city", "county", "board", "v"}
)


def short_name(case_name: str | None) -> str | None:
    """The party surname a citing court uses ("…v. Bruen" → "Bruen"). Best-effort:
    the last alphabetic token after the final 'v.' (or the last token)."""
    if not case_name:
        return None
    tail = re.split(r"\bv\.?\s+", case_name)[-1]
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", tail)
    return tokens[-1] if tokens else None


def party_surnames(case_name: str | None) -> list[str]:
    """Distinctive surname(s) a court might shorthand a case by — *both* sides, since
    usage varies ("Roe v. Wade" → "Roe"; "NYSRPA v. Bruen" → "Bruen"). Drops generic
    org/government tokens so the needle stays distinctive. Used for attribution."""
    if not case_name:
        return []
    out: list[str] = []
    for part in re.split(r"\bv\.?\s+", case_name):
        part = re.split(r"\brevision", part.lower())[0]
        toks = [t for t in re.findall(r"[a-z][a-z'-]+", part) if t not in _GENERIC_PARTY]
        if toks:
            out.append(toks[-1])
    return out


def case_key(name: str | None, year: int | None) -> tuple[str, int | None]:
    """Identity for collapsing CourtListener *revision* clusters of one opinion
    (defect #3): same case name (sans a 'Revisions: …' suffix) + same year. Three
    'Wooden v. United States' clusters dated 2022-03-0{7,7,8} collapse to one."""
    n = (name or "").lower()
    n = re.split(r"\brevision", n)[0]
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return (n, year)


def passage_window(text: str | None, needles: list[str], *, window: int = 1100) -> str | None:
    """Extract the passage *around* the first mention of the cited authority, so the
    stored text is the paragraph that treats it — not the whole opinion. Defect #1
    fix: grounds treatment classification and the displayed receipt. Falls back to
    the opinion head when no needle is found (still bounded, never the full text)."""
    if not text:
        return None
    lowered = text.lower()
    pos = -1
    for n in needles:
        if not n:
            continue
        i = lowered.find(n.lower())
        if i != -1 and (pos == -1 or i < pos):
            pos = i
    if pos == -1:
        return text[: 2 * window].strip() or None
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    return text[start:end].strip() or None


# --------------------------------------------------------------------------- #
# Collection (live, search-only — pure given a `search` callable).             #
# --------------------------------------------------------------------------- #
@dataclass
class CaseData:
    target: dict[str, Any]
    citers: list[dict[str, Any]] = field(default_factory=list)
    edges: list[tuple[int, int, int]] = field(default_factory=list)
    # cluster_id -> lead opinion id, for optional token full-text enrichment.
    opinion_ids: dict[int, int] = field(default_factory=dict)
    source: str = "cl_api"


def resolve_target(search: Search, citation: str) -> dict[str, Any] | None:
    data = search({"type": "o", "court": "scotus", "q": f'"{citation}"'})
    for r in data.get("results", []):
        if r.get("court_id") == "scotus" and citation in (r.get("citation") or []):
            return r
    return None


def _search_citers(search: Search, op_id: int, citation: str, *,
                   court: str | None = None, pages: int = 1,
                   order: str = "score desc") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        params: dict[str, Any] = {
            "type": "o",
            "q": f'cites:({op_id}) "{citation}"',
            "highlight": "on",
            "order_by": order,
            "page": page,
        }
        if court:
            params["court"] = court
        data = search(params)
        out.extend(data.get("results") or [])
        if not data.get("next"):
            break
    return out


def collect_case(search: Search, *, name: str, citation: str,
                 max_edges: int = 60, max_texts: int = 40,
                 pages: int = 2) -> CaseData | None:
    """Resolve a target and gather its inbound graph from the search endpoint."""
    target_res = resolve_target(search, citation)
    if target_res is None:
        return None
    cited_id = target_res["cluster_id"]
    op_id = lead_opinion_id(target_res)
    case = CaseData(target=opinion_row(target_res, source="cl_api", citation=citation))

    # SCOTUS-first (the canonical treatments) then a broader relevance pass.
    raw = _search_citers(search, op_id, citation, court="scotus", pages=1, order="dateFiled desc")
    raw += _search_citers(search, op_id, citation, pages=pages, order="score desc")

    seen: dict[int, dict[str, Any]] = {}
    for r in raw:
        cid = r.get("cluster_id")
        if cid and cid != cited_id and cid not in seen:
            seen[cid] = r

    # Prefer higher courts, then most recent, then collapse revision clusters of
    # the same opinion (defect #3) before capping the graph.
    ranked_all = sorted(
        seen.values(),
        key=lambda r: (court_rank(r.get("court_id")), -_date_ord(r)),
    )
    ranked: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int | None]] = set()
    for r in ranked_all:
        d = parse_date(r.get("dateFiled"))
        key = case_key(r.get("caseName"), d.year if d else None)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ranked.append(r)
    ranked = ranked[:max_edges]

    dropped = len(ranked_all) - len(ranked)
    if dropped:
        # Recall-first (docs/citator-fixes-plan.md): we only collapse revision
        # duplicates of the *same* opinion, never distinct citations — and we say so.
        print(f"    · collapsed {dropped} revision-duplicate cluster(s) for {name}")

    for i, r in enumerate(ranked):
        cid = r["cluster_id"]
        plain = result_snippet(r) if i < max_texts else None
        case.citers.append(opinion_row(r, source="cl_api", plain_text=plain))
        case.edges.append((cid, cited_id, 1))
        opid = lead_opinion_id(r)
        if opid:
            case.opinion_ids[cid] = opid
    return case


def _date_ord(r: dict[str, Any]) -> int:
    d = parse_date(r.get("dateFiled"))
    return d.toordinal() if d else 0


# --------------------------------------------------------------------------- #
# Seed fallback — real, well-known overrulings (source='seed').                #
# --------------------------------------------------------------------------- #
SEED_CASES: dict[str, dict[str, Any]] = {
    "410 U.S. 113": {
        "target": (108713, "Roe v. Wade", "1973-01-22"),
        "citers": [(
            6481357, "Dobbs v. Jackson Women's Health Organization", "scotus",
            "2022-06-24", "597 U.S. 215",
            "We hold that Roe and Casey must be overruled. The Constitution makes no "
            "reference to abortion, and no such right is implicitly protected by any "
            "constitutional provision.",
        )],
    },
    "163 U.S. 537": {
        "target": (94508, "Plessy v. Ferguson", "1896-05-18"),
        "citers": [(
            105221, "Brown v. Board of Education", "scotus", "1954-05-17", "347 U.S. 483",
            "We conclude that, in the field of public education, the doctrine of "
            "'separate but equal' has no place. Separate educational facilities are "
            "inherently unequal.",
        )],
    },
    "478 U.S. 186": {
        "target": (111738, "Bowers v. Hardwick", "1986-06-30"),
        "citers": [(
            130160, "Lawrence v. Texas", "scotus", "2003-06-26", "539 U.S. 558",
            "Bowers was not correct when it was decided, and it is not correct today. "
            "Bowers v. Hardwick should be and now is overruled.",
        )],
    },
    "198 U.S. 45": {
        "target": (96276, "Lochner v. New York", "1905-04-17"),
        "citers": [(
            102784, "West Coast Hotel Co. v. Parrish", "scotus", "1937-03-29", "300 U.S. 379",
            "The Constitution does not speak of freedom of contract. The liberty "
            "safeguarded is liberty in a social organization which requires the "
            "protection of law against the evils which menace the health, safety, "
            "morals, and welfare of the people.",
        )],
    },
}


def seed_case(citation: str) -> CaseData | None:
    spec = SEED_CASES.get(citation)
    if spec is None:
        return None
    tid, tname, tdate = spec["target"]
    case = CaseData(
        target={"id": tid, "cluster_id": tid, "case_name": tname, "court": "scotus",
                "date_filed": parse_date(tdate), "citation": citation,
                "plain_text": None, "source": "seed"},
        source="seed",
    )
    for cid, cname, ccourt, cdate, ccite, quote in spec["citers"]:
        case.citers.append({
            "id": cid, "cluster_id": cid, "case_name": cname, "court": ccourt,
            "date_filed": parse_date(cdate), "citation": ccite,
            "plain_text": quote, "source": "seed",
        })
        case.edges.append((cid, tid, 1))
    return case


# --------------------------------------------------------------------------- #
# HTTP + DB plumbing.                                                          #
# --------------------------------------------------------------------------- #
def http_get_json(url: str, *, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if token:
        req.add_header("Authorization", f"Token {token}")
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def make_search(token: str | None, sleep: float) -> Search:
    """A paced search callable. With a token we pace ≤ 4 req/min (CL free tier)."""
    import time

    pace = max(sleep, 16.0) if token else sleep

    def search(params: dict[str, Any]) -> dict[str, Any]:
        url = f"{CL_BASE}/search/?" + urllib.parse.urlencode(params)
        data = http_get_json(url, token=token)
        time.sleep(pace)
        return data

    return search


async def upsert_opinion(session: Any, row: dict[str, Any]) -> None:
    stmt = pg_insert(ClOpinion).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={  # coalesce: a re-run never wipes a fetched value with NULL
            "cluster_id": func.coalesce(stmt.excluded.cluster_id, ClOpinion.cluster_id),
            "case_name": func.coalesce(stmt.excluded.case_name, ClOpinion.case_name),
            "court": func.coalesce(stmt.excluded.court, ClOpinion.court),
            "date_filed": func.coalesce(stmt.excluded.date_filed, ClOpinion.date_filed),
            "citation": func.coalesce(stmt.excluded.citation, ClOpinion.citation),
            "plain_text": func.coalesce(stmt.excluded.plain_text, ClOpinion.plain_text),
            "source": func.coalesce(stmt.excluded.source, ClOpinion.source),
        },
    )
    await session.execute(stmt)


async def upsert_edge(session: Any, citing: int, cited: int, depth: int | None) -> None:
    stmt = pg_insert(CitationEdge).values(citing_id=citing, cited_id=cited, depth=depth)
    stmt = stmt.on_conflict_do_nothing(index_elements=["citing_id", "cited_id"])
    await session.execute(stmt)


async def write_case(session: Any, case: CaseData) -> None:
    await upsert_opinion(session, case.target)
    for row in case.citers:
        await upsert_opinion(session, row)
    for citing, cited, depth in case.edges:
        await upsert_edge(session, citing, cited, depth)


async def enrich_full_text(case: CaseData, token: str, max_texts: int, pace: float) -> None:
    """Token path: upgrade the bounded text subset to the passage *around the cite*
    pulled from the full opinion (not the whole opinion — see ``passage_window``)."""
    needles = [n for n in [case.target.get("citation"), *party_surnames(case.target.get("case_name"))]
               if n]
    for row in case.citers[:max_texts]:
        opid = case.opinion_ids.get(row["id"])
        if not opid:
            continue
        try:
            data = http_get_json(f"{CL_BASE}/opinions/{opid}/", token=token)
        except urllib.error.HTTPError as e:  # pragma: no cover - network
            print(f"    ! opinion {opid}: HTTP {e.code}")
            continue
        passage = passage_window(opinion_full_text(data), needles)
        if passage:
            row["plain_text"] = passage
        await asyncio.sleep(pace)


# --------------------------------------------------------------------------- #
# CLI.                                                                         #
# --------------------------------------------------------------------------- #
def parse_cases(spec: str) -> list[tuple[str, str]]:
    cases = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        name, _, cite = item.partition("|")
        cases.append((name.strip(), cite.strip()) if cite else (item, item))
    return cases


async def run(cases: list[tuple[str, str]], args: argparse.Namespace, token: str | None) -> None:
    search = make_search(token=token, sleep=args.sleep)
    pace = max(args.sleep, 16.0)
    rows = []
    factory = get_session_factory()
    async with factory() as session:
        for name, citation in cases:
            case = None if args.seed else _try_collect(search, name, citation, args)
            src_note = ""
            if case is None:
                case = seed_case(citation)
                src_note = "" if args.seed else " (live empty → fallback)"
            if case is None:
                print(f"- {name} [{citation}]: NO DATA (no live match, no seed)")
                rows.append((name, citation, 0, 0, "none"))
                continue
            if token and case.source == "cl_api":
                await enrich_full_text(case, token, args.max_texts, pace)
            await write_case(session, case)
            await session.commit()
            texts = sum(1 for c in case.citers if c["plain_text"])
            print(f"- {name} [{citation}]: {len(case.edges)} edges, {texts} texts, "
                  f"source={case.source}{src_note}")
            rows.append((name, citation, len(case.edges), texts, case.source))

        n_op = await session.scalar(select(func.count()).select_from(ClOpinion))
        n_edge = await session.scalar(select(func.count()).select_from(CitationEdge))
    print(f"\nTotals: cl_opinions={n_op}, citation_edges={n_edge}, cases={len(rows)}")
    await dispose_engine()


def _try_collect(search: Search, name: str, citation: str,
                 args: argparse.Namespace) -> CaseData | None:
    try:
        return collect_case(search, name=name, citation=citation,
                            max_edges=args.max_edges, max_texts=args.max_texts,
                            pages=args.pages)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"  ! live fetch failed for {name}: {e}")
        return None


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest the open-citator data foundation.")
    p.add_argument("--cases", default=",".join(DEFAULT_CASES),
                   help="comma-separated 'Name|Citation' (default: 4 landmark overrulings)")
    p.add_argument("--max-edges", type=int, default=60, help="cap inbound edges per case")
    p.add_argument("--max-texts", type=int, default=40, help="cap stored texts per case")
    p.add_argument("--pages", type=int, default=2, help="search pages per relevance pass")
    p.add_argument("--sleep", type=float, default=1.5, help="seconds between live requests")
    p.add_argument("--seed", action="store_true", help="offline: use the seeded set only")
    args = p.parse_args()

    token = os.environ.get("COURTLISTENER_TOKEN") or None
    cases = parse_cases(args.cases)
    print(f"Ingesting {len(cases)} case(s) | token={'yes' if token else 'no'} | "
          f"mode={'seed' if args.seed else 'live (CL search)'}")
    asyncio.run(run(cases, args, token))


if __name__ == "__main__":
    main()
