# Handoff — Correct citation retrieval (citator data layer)

**Mode line.** Next session is **EXECUTING**: own and improve **citation retrieval** — given a
case, fetch the *correct, complete, well-attributed* set of citing authorities + their treatment
passages. This is the data-input half of the citator. A separate track (the operator) is rebuilding
the **analysis engine** (passages → "good law?" verdict) on top of your output; the two halves meet
at the Postgres schema, so keep that contract stable. The product surfaces (`/resolve`, `/risk`,
`/ask`, `/assistant`) already consume your data — better retrieval flows straight through.

## The split (who owns what)
- **You — retrieval (inputs).** Which opinions cite the target, and the correct citing passage text
  + attribution. Code: `app/scripts/ingest_citator.py` (the ingester, your main file) and
  `app/src/htl/routes/resolve.py::cl_search` (case → cluster-id lookup). Writes `cl_opinions`
  (incl. `plain_text` = the citing passage) + `citation_edges` (citing→cited graph).
- **Operator — analysis (verdict).** Passages → treatment labels → risk. Code:
  `app/src/htl/llm/classify.py` + `app/src/htl/citator/risk.py`. Being reworked (agentic). Don't
  build here — just keep producing clean inputs.
- **Contract = the DB schema** (`app/src/htl/db/citator.py`, migration `0002_citator`):
  `cl_opinions`, `citation_edges`, `treatments`. Don't change column meanings without coordinating;
  additive migrations are fine.

## State (quantified) — all merged to `main`, CI-green
- Product: `POST /chat` (🔒) · `POST /resolve` (🌐) · `GET /cases/{id}/risk` (🌐) · `POST /ask`
  (🌐, agentic Gemini-2.5-pro, tools = resolve+risk, captures the verdict so the card can't be
  hallucinated) · `GET /health`. Frontend: `/` chat, `/citator` lookup, `/assistant` agentic ask.
  PRs #11–#13, #16–#18, #20 (typed query layer + `<VerdictCard>`), #21 (`/ask` + `/assistant`).
- Data is **LOCAL Docker Postgres only.** Prod Cloud SQL is NOT migrated/deployed, so the live
  Vercel `/assistant` errors on submit until the backend is promoted — the working demo is localhost.
- 6 seeded SCOTUS cases: Roe `108713`, Plessy `94508`, Bowers `111738`, Lochner `96276` (red),
  Auer `118089` (green), **Smith `112404` (false-red — your bug to fix).**
- `gemini-2.5-pro` works on Vertex here (ADC); `/ask` runs on it live (~9s/call).

## Carry-over — retrieval defects (the actual work, worst first)
Today's retrieval = CourtListener v4 **search** endpoint, NO token (`q=cites:(<op_id>) "<cite>"&highlight=on`
→ inbound graph + a **snippet** stored as `plain_text`). `opinions`/`opinions-cited` are 401 without a token.
1. **Snippet-sized passages.** `plain_text` is a search-highlight fragment, not the opinion text
   around the cite — too little context for reliable treatment. Fix: set `COURTLISTENER_TOKEN`
   (already wired: `ingest_citator.py::enrich_full_text` pulls `/opinions/<id>/` full text, paced
   ≤4/min) and/or widen the passage window. This single change removes most downstream noise.
2. **Mis-attribution.** Search relevance attaches a passage to the WRONG target (the Smith
   false-red: a passage about *Congress enacting RFRA* got tied to an unrelated ACCA case,
   *Wooden*). Fix: verify the citer actually cites THIS target (trust the `cites:(<op_id>)` filter +
   a passage-mentions-target check) before writing the edge.
3. **Duplicate passages.** The same fragment stacks multiple rows, inflating signal (3× on Smith).
   The edge PK dedups edges; dedup the stored passages too.
4. **Coverage.** Only 6 hand-seeded cases. The real tool resolves an arbitrary case → fetches its
   inbound graph on demand → caches to DB. `/resolve` already live-falls-back for non-seeded cases,
   but `/risk` only sees what's been ingested.

Defects 1–3 are *why* Smith false-reds — fixing retrieval likely flips it without touching the
analysis engine. (Forensic detail on the Smith trace lives in `archive/citator-endpoints.md`.)

## First moves
1. Skim `STATE.md`. Read fully: `app/scripts/ingest_citator.py` (your main file) and
   `app/src/htl/db/citator.py` (the contract). Glance at `classify.py` + `risk.py` only to see how
   your output is consumed (operator's territory — don't edit).
2. Local up: `docker run -d --name htl-citator-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=htl -p 5433:5432 postgres:16`
   → `cd app && uv run alembic upgrade head` → `uv run python scripts/ingest_citator.py --seed` (or
   live) → `just dev-api`. Reproduce the bug: `curl 127.0.0.1:8080/cases/112404/risk` → false-red.
   That's your target to flip.
3. Get a free `COURTLISTENER_TOKEN`, re-ingest Smith with full-text enrichment + an attribution
   check + passage dedup; confirm Smith stops false-redding while the 4 real reds stay red and Auer
   stays green.
4. Ship via the **ship-feature** skill (branch off `main` → atomic commits → PR → CI green →
   squash-merge). Build/test LOCALLY; the backend isn't deployed, don't rely on prod.

## Gotchas
- curl `127.0.0.1:8080`, NOT `localhost` (::1 is squatted). Verify via `just dev-api` (one uvicorn
  loop), not a multi-request FastAPI TestClient (crashes "attached to a different loop").
- Local DB only; `app/.env.local` (gitignored) points `DATABASE_URL` at the Docker PG. Prod
  promotion = `just migrate` → re-ingest/classify against Cloud SQL → `just deploy` (tied to an
  upcoming admin-GCP-account switch; infra is account-portable).
- `ingest_citator.py` is idempotent (coalesce upsert + skip-existing edges): re-runs enrich, don't
  duplicate opinions — but the passages themselves aren't deduped (defect #3).

## Teardown note
Delete this handoff (move to `.claude/handoffs/archive/`) when retrieval is reworked and this plan
is superseded by real PRs.
