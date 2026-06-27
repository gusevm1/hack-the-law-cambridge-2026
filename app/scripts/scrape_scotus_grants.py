#!/usr/bin/env python3
"""Scrape the SCOTUS cert-granted docket — cases the Court will review.

Each term the Supreme Court grants certiorari to a few dozen cases (it "will
review them for an appeal"). This pulls that granted set per term from the
Oyez API — clean JSON, no auth — and writes one file per term to
``data/scotus/ot<term>-granted.json`` at the repo root.

Source: ``https://api.oyez.org/cases?filter=term:<YEAR>`` returns every case
for an October Term with a ``timeline`` (Granted / Argued / Decided) and the
question presented. We keep the cases that have a **Granted** event — i.e. the
ones the Court agreed to hear. Pending ones (no Decided event yet) are the
upcoming docket; ``status`` flags which is which.

    cd app && uv run python scripts/scrape_scotus_grants.py            # current + next term
    cd app && uv run python scripts/scrape_scotus_grants.py --terms 2024 2025 2026

ponytail: Oyez summary payload is rich enough (docket #, question, timeline,
citation) — we don't fetch each case's full detail. Add per-case enrichment
only if a downstream feature needs the merits briefs / oral-argument audio.
The official authoritative cross-check is supremecourt.gov's
``<TT>grantednotedlist.pdf`` (PDF — needs a parser, so not used here).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

OYEZ = "https://api.oyez.org/cases?per_page=0&filter=term:{term}"
USER_AGENT = "htl-citator/0.1 (hack-the-law-cambridge-2026)"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "scotus"

_TAG = re.compile(r"<[^>]+>")

# macOS Pythons often lack a system CA bundle; certifi (a repo dep) is the fix.
try:
    import certifi

    _SSL_CTX: ssl.SSLContext = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - fall back to the system trust store
    _SSL_CTX = ssl.create_default_context()


def strip_html(s: str | None) -> str:
    return html.unescape(_TAG.sub("", s or "")).strip()


def http_get_json(url: str, timeout: int = 30) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def event_date(timeline: list[dict[str, Any]] | None, event: str) -> str | None:
    """First ISO date for a named timeline event (Oyez stores unix seconds)."""
    for e in timeline or []:
        if e and e.get("event") == event:
            dates = e.get("dates") or []
            if dates:
                return datetime.fromtimestamp(dates[0], tz=UTC).date().isoformat()
    return None


def web_url(api_href: str | None) -> str | None:
    """api.oyez.org/cases/2025/24-5438 -> www.oyez.org/cases/2025/24-5438."""
    return api_href.replace("api.oyez.org", "www.oyez.org") if api_href else None


def reporter_cite(cit: Any) -> str | None:
    """Format Oyez's citation object as '<vol> U.S. <page>', or None if unassigned."""
    if not isinstance(cit, dict) or not cit.get("volume") or not cit.get("page"):
        return None
    return f"{cit['volume']} U.S. {cit['page']}"


def to_record(case: dict[str, Any], term: int) -> dict[str, Any] | None:
    """Map an Oyez case summary to a granted-docket record, or None if not granted."""
    timeline = case.get("timeline")
    granted = event_date(timeline, "Granted")
    if not granted:
        return None  # docketed but not (yet) granted — not a case it will review
    decided = event_date(timeline, "Decided")
    return {
        "docket_number": case.get("docket_number"),
        "name": case.get("name"),
        "term": term,
        "status": "decided" if decided else "pending",
        "granted": granted,
        "argued": event_date(timeline, "Argued"),
        "decided": decided,
        "citation": reporter_cite(case.get("citation")),
        "question": strip_html(case.get("question")),
        "description": strip_html(case.get("description")),
        "oyez_url": web_url(case.get("href")),
        "justia_url": case.get("justia_url"),
    }


def scrape_term(term: int) -> list[dict[str, Any]]:
    cases = http_get_json(OYEZ.format(term=term))
    records = [r for c in (cases or []) if (r := to_record(c, term))]
    records.sort(key=lambda r: (r["status"] != "pending", r["docket_number"] or ""))
    return records


def current_term(today: date) -> int:
    """October Term <year>: starts the first Monday of October <year>."""
    return today.year if today.month >= 10 else today.year - 1


def _selfcheck() -> None:
    """Offline asserts on the pure logic — the bits that aren't a live fetch."""
    # term boundary: October flips the term to the new year.
    assert current_term(date(2026, 6, 27)) == 2025
    assert current_term(date(2026, 10, 6)) == 2026
    # 1737093600 = 2025-01-17 (Bowe grant date) in UTC.
    tl = [{"event": "Granted", "dates": [1737093600]}, {"event": "Argued", "dates": []}]
    assert event_date(tl, "Granted") == "2025-01-17"
    assert event_date(tl, "Argued") is None
    assert event_date(tl, "Decided") is None
    # citation: only a real volume+page becomes a string.
    assert reporter_cite({"volume": 606, "page": 1}) == "606 U.S. 1"
    assert reporter_cite({"volume": None, "page": None, "href": "x"}) is None
    # a granted case maps; an ungranted (empty timeline) one is dropped.
    assert to_record({"docket_number": "x", "timeline": tl}, 2025)["status"] == "pending"
    assert to_record({"docket_number": "y", "timeline": []}, 2025) is None
    assert strip_html("<p>a &amp; b</p>") == "a & b"
    print("selfcheck ok")


def main() -> None:
    default_terms = [current_term(date.today()), current_term(date.today()) + 1]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--terms", type=int, nargs="+", default=default_terms,
                   help=f"October Term start years to scrape (default: {default_terms})")
    p.add_argument("--out", type=Path, default=OUT_DIR, help=f"output dir (default: {OUT_DIR})")
    p.add_argument("--selfcheck", action="store_true", help="run offline logic asserts and exit")
    args = p.parse_args()

    if args.selfcheck:
        _selfcheck()
        return

    args.out.mkdir(parents=True, exist_ok=True)
    for term in args.terms:
        records = scrape_term(term)
        path = args.out / f"ot{term}-granted.json"
        path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
        pending = sum(1 for r in records if r["status"] == "pending")
        print(f"OT{term}: {len(records)} granted ({pending} pending) -> {path}")


if __name__ == "__main__":
    main()
