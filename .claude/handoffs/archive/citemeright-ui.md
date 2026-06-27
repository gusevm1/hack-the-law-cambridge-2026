# Handoff — CiteMeRight UI / case dossier

**Mode: EXECUTING.** Goal: the sickest single-view UI showing the *whole* citator
(ours + Maxim's), live. Stef's static HTML port was abandoned (janky flow); the
real deliverable is a fresh React page.

**FOR MAXIM — `devil` = everything not yet on main, in one branch, tests green
(98 passed). Merge `devil` → `main` and you have it all:** the UI (5 commits) +
full-text discovery + the network-timeout retry (cherry-picked clean on top of
current main). Nothing else to merge. `feat/citemeright-ui` is the same HEAD.

## The deliverable (DONE, on branch `feat/citemeright-ui`)
- **`frontend/app/citator/dossier/page.tsx`** → route **`/citator/dossier`**. One dark
  scroll showing EVERYTHING live: verdict hero + operative rule · treatment-mix /
  erosion-sparkline / analysis-depth bento · **interactive filterable citation graph**
  (reuses `components/citation-graph.tsx`, treated-only⇄all, click→passage) ·
  per-proposition "how each holding held up" · grounded negative treatments ·
  **use-aware verdict** (type your use → `/verdict` real-risk + per-prop + close-to-overruled).
- Reuses `lib/api` fetchers (all wired) + `CitationGraph`. Serves 200, eslint clean.
- `frontend/public/cmr.html` = the earlier Stef-port (static, live-data). Superseded by
  the dossier; keep as design reference only.

## Run it (local, all live)
```sh
docker start htl-citator-pg                                   # Postgres :5433 (local classified DB)
cd app && PYTHONPATH=src uv run uvicorn htl.main:app --port 8080   # MAIN backend on local DB (all endpoints; schema==local, migration 0002)
cd frontend && corepack pnpm@10 dev                          # web :3000 → .env.local NEXT_PUBLIC_API_URL=localhost:8080
# open http://localhost:3000/citator/dossier
```
`uv` at `~/.local/bin` (not on default PATH — prefix `PATH="$HOME/.local/bin:$PATH"`). pnpm needs `corepack pnpm@10` (repo workspace yaml is pnpm-10).

## Data state (local DB)
- 7 cases classified by **gemini-2.5-flash** (396 treatments). Bruen=6480696 has **229 edges incl Rahimi (9679332) + Hemani** — landed via **full-text discovery** (`source=cl_fulltext`); structured `cites:` graph misses them. 414/416 opinions live (cl_api/cl_fulltext), 2 seed.
- **`scratchpad/citator-data/citator-dump.sql`** = pg_dump (cl_opinions+citation_edges+treatments) for **Maxim → Cloud SQL** (`psql < dump.sql`).

## Open items (priority)
1. **Make the dossier the real `/citator`** — coordinate first: colleague owns `frontend/app/citator/*` + is steering to CiteMeRight (`citemeright.com`, #45/#47/#48). Don't silently overwrite.
2. **Rahimi/Hemani classify as "followed", not their narrowing** — passage-window grabs the opinion *intro* (first-occurrence). Fix = best-occurrence extraction (passage near a treatment verb). `app/scripts/ingest_citator.py::passage_window`. The `/propositions` layer DOES capture it ("Bruen — good law as modified by Rahimi").
3. **Heller** = outbound/foundations (Bruen→Heller); we only ingest inbound. Build outbound query if wanted.
4. ~~`feat/fulltext-discovery`~~ — DONE: the two new commits (full-text union + timeout-retry) are now cherry-picked onto `devil`. The rest of that old branch was already on main via #43.
5. **Prod**: load `citator-dump.sql` into Cloud SQL (needs `gcloud auth login` as devstar5221) ; prod treatments were keyword-fallback (sandbox blocks user Vertex).

## Constraints / gotchas
- **CourtListener 4 req/min.** ALL CL calls go through `htl.citator.cl_client.cl_get_json` (single-flight lock + ≥20s pace + 429/timeout backoff). **Never run concurrent CL calls / probes** — that's what kept throttling us. Token in `app/.env.local` (`COURTLISTENER_TOKEN`).
- Branch stack (all PR'd, unmerged): #24 graph → #25 dedup → #29 recall → #32 dev-inspector → #39 paced-client; `feat/fulltext-discovery`; `feat/citemeright-ui` (this). `main` already merged `devil` (#43) + Maxim's analysis (#35-37) + landing/domain.
- `git`: `gh` for PRs; commits end with the Opus co-author trailer; ship via the `ship-feature` flow; never commit to `main`.
