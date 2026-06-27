"""Cert-watch table — SCOTUS review status per proposition (Feature 4 / B owns it).

The same curated-table discipline as ``risk.GROUND_TRUTH``: code-grounded, dated,
and **never** LLM-asserted. A confident wrong cert claim is the malpractice
boundary, so every entry carries a ``source`` and an ``as_of``, and ``granted`` is
the conservative fact (we only flag a grant we can stand behind).

As of ``AS_OF`` the AWB/LCM cert cluster (scope §9 — Duncan, NAGR v. Lamont, et al.)
is **pending, not granted** — the most volatile fact in the space.

ponytail: re-pull the supremecourt.gov order list before any lawyer-facing output;
these dates go stale fast. Upgrade path: replace this dict with a dated feed off the
SCOTUS docket. Keyed by proposition id (P1..P8).
"""

from __future__ import annotations

from htl.models.api import CertStatus

AS_OF = "2026-06-27"

CERT_WATCH: dict[str, CertStatus] = {
    "P4": CertStatus(
        granted=False,
        case_name="AWB/LCM cluster (Duncan v. Bonta · NAGR v. Lamont · Ocean State Tactical)",
        term="OT2025",
        question="Whether 'assault weapon' and large-capacity-magazine bans are "
        "consistent with the Second Amendment under Bruen.",
        source="supremecourt.gov order lists · SCOTUSblog · CourtListener dockets",
        as_of=AS_OF,
    ),
}
