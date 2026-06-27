# Handoff — seed deployed Bruen DB from the SQL dump

**Mode: executing.** Load a ready SQL dump into the deployed Cloud SQL, verify Bruen's
endpoints, merge the loader. No CL calls, no code-behavior changes. Nothing blocks you.

## State (verified)
- **Backend wire shipped + live.** PR #43 (`/citations`+pipeline → real DB; unified
  retrieve→analyze frontend) and PR #47 (graph "hide neutral" filter) are **merged to
  main**. Cloud Run rev **`htl-api-00006-xjq`** at `https://htl-api-4h4hpkfmqq-ew.a.run.app`
  (`/health` ok). Vercel frontend deployed.
- **In flight (this branch `feat/db-dump-loader`):** `app/scripts/load_dump.py` +
  `just load-dump <path>`. Parse-validated against the dump (413/416/396) — **not yet
  run against the DB.** Needs merge.
- **Deployed DB right now:** Bruen `6480696` = 185 edges (183 CL snippets + hand-seeded
  Rahimi/Hemani), **no `treatments`** → graph is grey, `signal: unknown`. The dump
  replaces this with real treatments.

## Carry-over notes
- **The dump is the source of truth — stop hitting CourtListener.** Limits are brutal
  and already hit: **5 req/min, 50/hr, 125/day**. Token is in Secret Manager
  (`courtlistener-token` v2) but don't ingest live anymore.
- **Dump:** `/Users/maximgusev/Downloads/citator-dump.sql` — Bruen-centric,
  **413 edges / 416 opinions / 396 treatments**. Treatments are real + varied (14
  overruled, 13 criticised, 3 limited, 2 abrogated, 1 questioned, 40 followed, 317
  neutral) → loading gives a **coloured graph + a real red/amber/green signal**. Includes
  Rahimi (`10600058`) + Hemani (`10876933`). Schema == our models, **no migration**.
- **Loader is destructive by design:** `TRUNCATE`s the 3 citator tables then bulk-loads
  via asyncpg COPY through the Cloud SQL connector (same auth as `just migrate`; `psql`
  and `cloud-sql-proxy` are NOT installed, so use this). Atomic (one txn).
- **ADC must be `devstar5221@gcplab.me`** or the connector 403s (it silently defaults to
  a stale personal account). Re-login: `gcloud auth application-default login` +
  `... set-quota-project llm-law-cambridge26cbx-522`. Instance:
  `llm-law-cambridge26cbx-522:europe-west1:htl-db`.
- **STATE.md's "connector is user-blocked" warning is STALE** — the connector works with
  ADC=devstar5221 (verified this session: `just migrate` exit 0, and the hand-seed wrote
  rows through it). If it *does* 403, the fallback is STATE.md's public-IP route:
  allowlist your egress IP (`gcloud sql instances patch htl-db --authorized-networks=<ip>/32`)
  and run with `DATABASE_URL=postgresql+pg8000://htl_app:<pw>@<public-ip>:5432/htl` +
  `INSTANCE_CONNECTION_NAME=""`.
- **No `just deploy` needed** — the load is pure data; backend rev 00006 already has the
  wire. "Deploy" = data lands in the deployed DB; verify endpoints.
- `propositions`/`verdict` still read the curated `golden_analysis`, not the DB
  (analysis lane, out of scope). The `/citations`+triage+classify+analyze path reads the
  DB with a Bruen-golden fallback when empty.

## Open questions
- **Heller (`145777`) + Lopez (`117927`) not seeded** — they predate Bruen so can't
  *treat* it (only Rahimi/Hemani do). Check if the dump includes them; drop unless you
  explicitly want neutral context nodes.

## First moves
1. **Confirm ADC** = devstar: `curl -s "https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=$(gcloud auth application-default print-access-token)" | grep email`. Re-login if not.
2. **Load:** `just load-dump /Users/maximgusev/Downloads/citator-dump.sql` → expect `413 / 416 / 396`.
3. **Verify Bruen** (should now be coloured + signalled):
   `curl -s .../cases/6480696/graph | python3 -m json.tool | head` (signal ≠ unknown,
   edges carry `treatment`), then `/risk`, `/inspect`. Open prod `/citator` (defaults to Bruen).
4. **Merge this branch** (loader + recipe) via PR to main.

## Teardown
Move this file to `.claude/handoffs/archive/` in the wrap-up commit once the dump is
loaded + Bruen verified.
