# Retrieval → Analysis: the ingestion contract

What the retrieval layer must deliver so the analysis pipeline (triage → classify
→ relate → aggregate) can consume it. This is the boundary the two tracks meet at.
Locked now that retrieval is confirmed consistent (full-text ∪ graph, deduped).

> **One line:** retrieval delivers **clean, deduped, well-attributed inbound edges
> with provenance**, one per citing cluster. It does *not* classify treatment or
> tag propositions — that's the analysis side. Deliver the edges; we tier and read
> them.

The wire boundary is `GET /cases/{id}/citations → CitationsResponse` (today a stub
in `app/src/htl/citator/golden.py`; retrieval makes it real). Triage already
consumes exactly this shape.

---

## 1. The wire contract (`CitationsResponse`)

```jsonc
{
  "case": {                       // the TARGET being looked up
    "case_id":   6480696,         // CL cluster id (== /resolve case_id == cited_id)
    "case_name": "New York State Rifle & Pistol Assn., Inc. v. Bruen",
    "citation":  "597 U.S. 1",    // lead parallel cite
    "court":     "scotus",
    "date_filed":"2022-06-23"
  },
  "total": 7,
  "edges": [                      // one per CITING cluster, deduped
    {
      "citing_case": {
        "case_name":  "United States v. Rahimi",
        "court":      "scotus",   // CL court slug — drives BINDING (most important field)
        "date_filed": "2024-06-21"// ISO date — drives RECENCY
      },
      "citation":         "602 U.S. 680",   // citing case's own lead cite, nullable
      "passage":          "Some courts have misunderstood the methodology …",
      "source":           "fulltext",       // "graph" | "fulltext"
      "matched_citation": "597 U.S. 1",     // which parallel cite of the TARGET matched
      "opinion_url":      "https://www.courtlistener.com/opinion/<id>/slug/"
    }
  ]
}
```

### Field-by-field — required, nullable, and what it drives downstream

| Field | Req? | Drives | Quality bar |
|---|---|---|---|
| `case.case_id` | ✅ | the lookup key (== `cited_id`) | the **target must be ingested too** — Bruen isn't a normal "case in the DB" |
| `case.{case_name,citation,court,date_filed}` | ✅ | the Resolve screen + reversed-direction detection (we derive the target's short name, e.g. "Bruen", from `case_name`) | real, canonical |
| `citing_case.court` | ✅ | **binding** tier signal (apex/circuit vs not) | **must be a CourtListener court slug** — `scotus`, `ca1`…`ca11`, `cadc`, `cafc`, district (`dcd`, `nysd`…), state (`txapp`…). Free-text court names break tiering. |
| `citing_case.date_filed` | ✅ | **recency** signal | ISO `YYYY-MM-DD` |
| `citing_case.case_name` | ✅ | display + attribution | real |
| `passage` | ✅ | **everything the LLM/keyword reads** — treatment keywords + proposition-phrase hits | the actual citing span *about the target* (see §4) |
| `source` | ✅ | provenance badge | `"graph"` (structured `cites:`) or `"fulltext"` (matched by reporter string) |
| `matched_citation` | ◻ null-ok | provenance; confirms it really cites the target | one of the target's parallel cites |
| `citation` (citing) | ◻ null-ok | display | unpublished dispositions may have none |
| `opinion_url` | ◻ null-ok | click-through to primary source | derivable from the citing CL opinion id; strongly wanted for lawyer trust |

---

## 2. DB ingestion schema — the one change that matters

The current schema (`migration 0002`) was built for whole-case risk. **The citing
passage lives on `cl_opinions.plain_text` — that's the whole citing opinion.** For
proposition-level work that's wrong: the passage we need is the *span about the
target*, which is **per-edge** (per citing × cited pair), not per opinion. A case
that cites Bruen and Heller has two different passages.

So:

**`cl_opinions`** (one row per opinion — citing *and* cited):
`id` (CL cluster id, PK) · `case_name` · `court` (CL slug) · `date_filed` (date) ·
`citation` (lead cite) · `source` · **`plain_text` = the FULL opinion text** (see
§2a — now required, not optional). → **Action: also ingest the target row** (Bruen
6480696) so `/citations` and `/resolve` can serve its metadata.

**`citation_edges`** (one row per inbound edge) — needs new columns:

| column | exists? | type | note |
|---|---|---|---|
| `citing_id`, `cited_id` | ✅ | int (composite PK) | `citing_id` = citing **cluster** id (dedup unit) |
| `depth` | ✅ | int | keep |
| **`passage`** | ➕ add | TEXT | the citing span about the target (the field triage/classify read) |
| **`source`** | ➕ add | TEXT | `'graph'` \| `'fulltext'` |
| **`matched_citation`** | ➕ add | TEXT null | which parallel cite matched |

`opinion_url` is derived (`/opinion/{citing_id}/`), so no column needed.

The `/citations` route then becomes: load `cl_opinions[cited_id]` for `case`, join
`citation_edges ⋈ cl_opinions` on `citing_id` for the edges. (Same join shape as
`routes/risk.py`, plus the three new edge columns.)

## 2a. Full opinion text — REQUIRED, and the hard part (locked decision)

The **deep-analysis stage (Feature 3) reads the full citing opinion**, not the
snippet — that's how the model actually *finds* the treatment (locate the discussion
across paragraphs, even cited-by-name) instead of guessing from a highlight window.

**Decision: retrieval persists the full opinion text in `cl_opinions.plain_text`,
keyed by opinion id; the analysis stage reads it from the DB by id.** Rationale:
retrieval already fetched the opinion to find the cite, so re-fetching downstream
duplicates work and needs a second CL-token/rate-limit owner; persisting makes
analysis fast, deterministic, and offline-testable, and avoids shipping 100 KB blobs
per edge over the API (the wire contract carries the **id + snippet**; full text
lives in Postgres).

⚠️ **Sourcing full text is genuinely hard — flagged, in your lane.** Verified on
2026-06-27 against CL: SCOTUS opinions have full text (Rahimi = 222K chars), but
**recent F.4th circuit opinions return empty** `plain_text`/html *and* no
`download_url` (Antonyuk, Range, Wolford all 0 chars across every field). These are
the gun-law battlegrounds, so this gap is the pipeline's #1 data risk. Options to
close it (your call): court-site / CAP / Google Scholar text, PDF extraction from
`download_url` where present (note scope §9: some slip PDFs 403 fetchers), or a
commercial export. **Until text exists for an edge, mark it so:** analysis degrades
to snippet mode (lower confidence) rather than fabricating depth. Where you *can*
supply full text, set `plain_text`; where you can't, leave it null and the analyzer
flags `analysis_depth="snippet"`.

---

## 3. Normalization (non-negotiable — tiering is deterministic on these)

- **Court** → CourtListener slug, lower-case. This is the single highest-leverage
  field: binding tiering keys off `scotus` / `ca\d+` / `cadc` / `cafc`. Anything
  else reads as non-binding.
- **Dates** → ISO 8601 `YYYY-MM-DD`.
- **Citations** → reporter form as CL emits it (`597 U.S. 1`, `602 U.S. 680`,
  `120 F.4th 941`).
- **Edges deduped by citing cluster** — one edge per citing case, even if found by
  both graph and full-text (record the path in `source`; union flag optional).

---

## 4. Passage quality — where the known defects live

The `passage` is the only place the analysis layer "reads law", so its quality is
the whole ballgame. From the retrieval brief (`citation-retrieval.md`) the failure
modes that produced the **Smith #112404 false-red** were *retrieval* defects, and
they all live in this field:

1. **Correct attribution.** The treatment language in the passage must be about
   **the target**, not a neighbouring case in the same sentence. ("…overruled
   Casey and Roe…" must attach to the right cited id.)
2. **No snippet noise.** Give the real sentence(s) around the cite, not a
   highlight fragment truncated mid-clause. Whole-sentence spans.
3. **Dedupe passages.** Don't emit the same span three times for one edge.
4. **Self-vs-reported is preserved in the text.** Keep enough context that the
   classifier can tell "*this* court limited Bruen" from "this court *quotes
   Rahimi* limiting Bruen" (the "trapped in amber" attribution trap, scope §4).
   Don't pre-trim that signal away.

A clean, correctly-attributed, whole-sentence passage is worth more than ten more
edges.

---

## 5. Out of scope for retrieval (the analysis side owns these)

Don't compute these — we do, deterministically/with the LLM, and we need the raw
inputs un-pre-judged:

- ❌ treatment classification (overruled/limited/followed) — Feature 2
- ❌ proposition tagging (P1…P8) — triage derives phrase hits from `passage`
- ❌ tiering / relevance scoring / dropping noise — triage owns this; **never
  pre-filter**, send reversed-direction and procedural cites through too (we
  surface them as `mention`)
- ❌ risk / good-law verdict — Features 4/5

Deliver clean edges + provenance. We tier, classify, relate, and judge.
```
