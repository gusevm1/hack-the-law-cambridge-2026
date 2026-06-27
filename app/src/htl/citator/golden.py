"""Bruen golden citation set — a contract-true stub for the (not-yet-built)
retrieval engine.

``GET /cases/{id}/citations`` serves this verbatim. It mirrors what the retrieval
engine will return — clean inbound edges, full-text ∪ graph union, each with
provenance — so the triage stage (and its frontend) can be built and proven
against the real Bruen golden set *before* retrieval is wired. DB-independent:
Bruen is not in the local DB, so this works with no ingest.

Grounded on real cases (CourtListener, 2026-06-27); case names are real, passages
are representative snippets of each citer's actual treatment. ``opinion_url`` is
left null until the retrieval engine supplies the real cluster links.
"""

from __future__ import annotations

from htl.models.api import CaseRef, CitationsResponse, CitingCaseRef, Edge

BRUEN_ID = 6480696

# Bruen's parallel cites (the retrieval engine full-text-searches all of them).
_597 = "597 U.S. 1"
_142 = "142 S. Ct. 2111"

_CASE = CaseRef(
    case_id=BRUEN_ID,
    case_name="New York State Rifle & Pistol Assn., Inc. v. Bruen",
    citation=_597,
    court="scotus",
    date_filed="2022-06-23",
)

_EDGES: list[Edge] = [
    # Apex binding treatment — the edge full-text retrieval exists to catch (the
    # structured graph misses Rahimi→Bruen). Force-deep: SCOTUS, strong treatment,
    # engages the analogue-not-twin proposition (P2a).
    Edge(
        citing_case=CitingCaseRef(case_name="United States v. Rahimi", court="scotus",
                                  date_filed="2024-06-21"),
        citation="602 U.S. 680",
        passage=("Some courts have misunderstood the methodology of our recent Second "
                 "Amendment cases. These precedents were not meant to suggest a law "
                 "trapped in amber. A historical regulation need not be a \"dead ringer\" "
                 "or a \"historical twin\"; it need only be relevantly similar."),
        source="fulltext",
        matched_citation=_597,
        opinion_url=None,
    ),
    # Binding-in-circuit, applies Bruen across two propositions (public-carry P1 +
    # sensitive places P3) — a key edge, earns deep.
    Edge(
        citing_case=CitingCaseRef(case_name="Antonyuk v. James", court="ca2",
                                  date_filed="2024-10-24"),
        citation="120 F.4th 941",
        passage=("Applying Bruen, we hold New York's may-issue \"proper cause\" standard "
                 "is unconstitutional, but most of the State's sensitive-place "
                 "restrictions survive as consistent with the historical tradition."),
        source="graph",
        matched_citation=_597,
        opinion_url=None,
    ),
    # Felon / §922(g)(1) circuit case (8th Cir. — the §922(g)(1) "Jackson", not the
    # 4th Cir. §922(n) one). Engages P5 only → shallow.
    Edge(
        citing_case=CitingCaseRef(case_name="United States v. Jackson", court="ca8",
                                  date_filed="2024-08-08"),
        citation="110 F.4th 1120",
        passage=("Applying Bruen and Rahimi, we hold that 922(g)(1)'s categorical bar on "
                 "the possession of firearms by those who are not law-abiding is "
                 "consistent with the Nation's historical tradition."),
        source="graph",
        matched_citation=_597,
        opinion_url=None,
    ),
    # Second P5 edge — the as-applied / non-dangerous side of the §922(g) split.
    Edge(
        citing_case=CitingCaseRef(case_name="Range v. Attorney General", court="ca3",
                                  date_filed="2023-06-06"),
        citation="69 F.4th 96",
        passage=("Applying Bruen, the Government has not shown a historical tradition "
                 "supporting the as-applied disarmament of Range, a non-dangerous person "
                 "who remains among \"the people\" the Second Amendment protects."),
        source="graph",
        matched_citation=_597,
        opinion_url=None,
    ),
    # Sensitive-places (P3) circuit edge → shallow.
    Edge(
        citing_case=CitingCaseRef(case_name="Wolford v. Lopez", court="ca9",
                                  date_filed="2024-09-06"),
        citation="116 F.4th 959",
        passage=("Applying Bruen, we largely uphold Hawaii's designation of sensitive "
                 "places, though the default rule barring carry on private property open "
                 "to the public lacks a historical analogue."),
        source="graph",
        matched_citation=_597,
        opinion_url=None,
    ),
    # NOISE — reversed direction: Bruen is the OVERRULER here, not the overruled.
    Edge(
        citing_case=CitingCaseRef(case_name="United States v. Richardson", court="dcd",
                                  date_filed="2023-03-15"),
        citation=None,
        passage="The Court must ignore Medina because it has been overruled by Bruen. See Mot. at 25-31.",
        source="fulltext",
        matched_citation=_142,
        opinion_url=None,
    ),
    # NOISE — procedural: a docket event, not a treatment of Bruen.
    Edge(
        citing_case=CitingCaseRef(case_name="Lynch v. Jackson", court="txapp",
                                  date_filed="2022-10-07"),
        citation=None,
        passage="Appellant's TCPA motion is overruled by operation of law.",
        source="fulltext",
        matched_citation=_142,
        opinion_url=None,
    ),
]

BRUEN_CITATIONS = CitationsResponse(case=_CASE, total=len(_EDGES), edges=_EDGES)

# Keyed by CL cluster id (== /resolve's case_id). One entry today; the retrieval
# engine will populate the rest.
CITATIONS: dict[int, CitationsResponse] = {BRUEN_ID: BRUEN_CITATIONS}


# --------------------------------------------------------------------------- #
# Full opinion text — mocks what retrieval will persist in cl_opinions.plain_text.
# The deep analyzer (Feature 3) reads this when present (full-text mode) and falls
# back to the edge's snippet otherwise. Only a couple of citers carry full text, so
# both modes are exercised. Representative multi-paragraph prose grounded in the
# real opinions — Rahimi touches several propositions (P2/P2a/P5/P8), so its deep
# read yields multiple findings; the other citers stay snippet-only.
#
# ponytail: keyed by citing case name (the stub's natural key). Swap for a
# cl_opinions.plain_text lookup by the citing opinion id once retrieval persists it.
# --------------------------------------------------------------------------- #
FULL_TEXT: dict[str, str] = {
    "United States v. Rahimi": (
        "Section 922(g)(8) of Title 18 prohibits an individual subject to a domestic "
        "violence restraining order from possessing a firearm. We hold that it does, "
        "and that the prohibition is consistent with the Nation's historical tradition "
        "of firearm regulation.\n\n"
        "Since the founding, our Nation's firearm laws have included provisions "
        "preventing individuals who threaten physical harm to others from misusing "
        "firearms. As applied to the facts here, Section 922(g)(8) fits within this "
        "tradition. When an individual has been found by a court to pose a credible "
        "threat to the physical safety of another, that individual may be temporarily "
        "disarmed consistent with the Second Amendment.\n\n"
        "Some courts have misunderstood the methodology of our recent Second Amendment "
        "cases. Those precedents were not meant to suggest a law trapped in amber. As "
        "we explained in Heller, and reiterated in Bruen, the appropriate analysis "
        "involves considering whether the challenged regulation is consistent with the "
        "principles that underpin our regulatory tradition. A court must ascertain "
        "whether the new law is relevantly similar to laws that our tradition is "
        "understood to permit. Why and how the regulation burdens the right are "
        "central to this inquiry. A historical regulation need not be a dead ringer "
        "or a historical twin.\n\n"
        "Nor does our decision in Bruen require a regulation to be an updated model of "
        "a historical counterpart. The Fifth Circuit erred in reading Bruen to require "
        "a 'historical twin' before a modern regulation may stand. That reading is too "
        "rigid; it would render the Second Amendment a regulatory straightjacket.\n\n"
        "Finally, the Government's reliance on the view that Rahimi is not 'responsible' "
        "misunderstands Bruen. 'Responsible' is a vague term, and we do not suggest that "
        "the Second Amendment is limited to 'responsible' citizens. The dangerousness "
        "principle, not the label 'law-abiding, responsible,' supplies the relevant "
        "historical hook. We also reaffirm that the 'presumptively lawful' regulatory "
        "measures identified in Heller — including longstanding prohibitions on the "
        "possession of firearms by felons and the mentally ill — remain undisturbed."
    ),
}


def full_text_for(citing_case_name: str | None) -> str | None:
    """The persisted full opinion text for a citer, or None (snippet-only)."""
    return FULL_TEXT.get(citing_case_name or "")
