"""The proposition spine (scope §4, lawyer-confirmed) — one source of truth.

A case is a bundle of propositions; treatment attaches to each separately. Both the
deterministic filter (``triage.py`` — phrase hits) and the LLM classifier
(``llm.classify`` — scope→proposition) read this. ``phrases`` are the verbatim
opinion-text signals; ``summary`` is the short gloss handed to the model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Proposition:
    id: str
    label: str
    summary: str
    phrases: tuple[str, ...]


PROPOSITIONS: list[Proposition] = [
    Proposition(
        "P1", "Public-carry right",
        "Right to carry a handgun in public for self-defense; 'proper cause' / "
        "may-issue regimes are unconstitutional.",
        ("proper cause", "special need", "may-issue", "shall-issue", "second-class right"),
    ),
    Proposition(
        "P2", "Text-history-tradition",
        "Gun regulations must be justified by the Nation's historical tradition; "
        "means-end / interest-balancing scrutiny is rejected.",
        ("text, history, and tradition", "means-end", "two-step", "interest balancing",
         "one step too many"),
    ),
    Proposition(
        "P2a", "Analogue not twin",
        "The historical analogue need not be a 'dead ringer' or 'historical twin' — "
        "only relevantly similar (how & why). Clarified/narrowed by Rahimi.",
        ("historical twin", "dead ringer", "relevantly similar", "how and why",
         "comparable burden", "regulatory straightjacket"),
    ),
    Proposition(
        "P3", "Sensitive places",
        "'Sensitive places' may bar carry, but the category was left largely "
        "undefined (dicta); contested and expanding.",
        ("sensitive place", "island of manhattan", "polling place", "private property"),
    ),
    Proposition(
        "P4", "Common use / AWB",
        "Arms in common use are protected; 'dangerous and unusual' may be regulated — "
        "circuit split over assault weapons / large-capacity magazines.",
        ("in common use", "dangerous and unusual", "assault weapon",
         "large-capacity magazine", "caetano"),
    ),
    Proposition(
        "P5", "The people / §922(g)",
        "Who counts among 'the people' and may be disarmed (felons, DV, §922(g)) — "
        "the hottest split; categorical vs as-applied.",
        ("the people", "law-abiding", "responsible", "922(g)", "categorical",
         "as-applied", "non-dangerous"),
    ),
    Proposition(
        "P6", "Historical era 1791/1868",
        "Which era fixes the tradition — 1791 (founding) vs 1868 (Reconstruction) — "
        "reserved / open.",
        ("1791", "1868", "reconstruction", "level of generality", "too late"),
    ),
    Proposition(
        "P7", "Shall-issue licensing",
        "Shall-issue licensing regimes are presumptively lawful (fn.9 + concurrence), "
        "absent exorbitant fees or abuse.",
        ("footnote 9", "good moral character", "43 states", "exorbitant fees"),
    ),
    Proposition(
        "P8", "Presumptively-lawful carve-outs",
        "Heller's 'presumptively lawful' measures (felon-in-possession, mentally ill, "
        "commercial sale) survive.",
        ("presumptively lawful", "longstanding prohibition", "felons and the mentally ill",
         "commercial sale"),
    ),
]

# Phrase hits for the deterministic filter, keyed by id.
PHRASES: dict[str, list[str]] = {p.id: list(p.phrases) for p in PROPOSITIONS}

# Ids in spine order (for the classifier enum + ordering).
PROP_IDS: list[str] = [p.id for p in PROPOSITIONS]

# A compact "P1 — label: summary" block for the classifier system prompt.
SPINE_TEXT: str = "\n".join(f"- {p.id} — {p.label}: {p.summary}" for p in PROPOSITIONS)
