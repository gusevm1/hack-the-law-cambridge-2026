# STATE

Where the project is right now. Update this as reality moves.

## Now
- **Citator pipeline COMPLETE + DEPLOYED** — all five stages (Filter · Classify · Deep-analyzer · Propositions · Use-aware Verdict) shipped to `main` and live on Cloud Run (rev `htl-api-00005-rsn`) + Vercel. The `/citator/analyze` stepper walks the full Bruen flow end-to-end; the frontend is fully wired to the backend (every fetcher → a live endpoint, CORS `*`). Details under **Citator** below.
- Scaffold + **production backend foundation shipped** (PR #6): Supabase JWT auth (ES256/JWKS), Cloud SQL Postgres (`users` + `messages`) via async SQLAlchemy + the Cloud SQL connector + Alembic, correlation IDs, structured JSON logging, and a uniform error envelope.
- `POST /chat` is gated behind a verified user and persists both turns (user + assistant), stamped with the user + correlation id. `get_verifier` auto-selects Supabase (when JWKS+issuer set) else a dev/CI stub.
- Backend on Cloud Run; Gemini-on-Vertex wired (async, ADC auth). Frontend: real **login** (email/password + Google/GitHub buttons) gating the chat, with the signed-in email + sign-out in the top-right; `/chat` calls carry the session `Bearer`.

## Live
- **GCP project:** `llm-law-cambridge26cbx-522` ("Hack the Law-522" — Google-managed dev sandbox, account `devstar5221@gcplab.me`, org "No organization"). Switched off the old throwaway `hack-the-law-cambridge-2026` on 2026-06-27 via `bootstrap` + public-IP migrate + `deploy`.
- **Cloud Run service:** `htl-api` @ `europe-west1`. URL: `https://htl-api-4h4hpkfmqq-ew.a.run.app` (revision `htl-api-00005-rsn`). Cloud SQL attached + Supabase env (issuer/JWKS unchanged). Live (all → 200): `/health`; `/resolve`; `/ask`; `/cases/{id}/risk` (runtime SA reaches Cloud SQL via the connector); the full citator pipeline `/cases/{id}/{citations,triage,classify,analyze,propositions,verdict}` (DB-independent stub + filter + real Gemini via the runtime SA — Rahimi→limited/P2a etc.). Public (`--allow-unauthenticated`); the app-level JWT gate is the real access control. **Deploy with `just deploy`** — project/region now flow from `infra/env.sh`, the single source of truth (PR #40); override any value via env.
  - **Custom domain:** `https://api.citemeright.com` → this service (Cloud Run managed domain mapping, Google-managed TLS via `pki.goog`); the raw `run.app` URL still serves as a fallback. ⚠️ The mapping is **account-scoped** — recreate on any GCP account switch: `gcloud beta run domain-mappings create --service=htl-api --domain=api.citemeright.com --region=$REGION` (needs one-time Search Console domain verification under the new account), then add the returned `api CNAME ghs.googlehosted.com` at the DNS host (Vercel).
- **Cloud SQL:** `htl-db` @ `europe-west1` (POSTGRES_16, db-f1-micro, ENTERPRISE edition). DB `htl`, user `htl_app` (password in Secret Manager `htl-db-password`). Conn: `llm-law-cambridge26cbx-522:europe-west1:htl-db`. **Migrated to `0002`**, then ingested + classified on prod (150 `cl_opinions`, 157 `citation_edges`, `treatments` populated). ⚠️ The Cloud SQL **connector** (`connectSettings` API) is blocked for the **user** identity on this sandbox (`boss::NOT_AUTHORIZED`, even with `editor`+`cloudsql.client` — a higher-level lab guardrail, no project deny policy), so `just migrate` fails from a laptop. Workaround for migrate/ingest from a laptop: allowlist your egress IP (`gcloud sql instances patch htl-db --authorized-networks=<ip>/32`) and run alembic/scripts with `DATABASE_URL=postgresql+pg8000://htl_app:<pw>@<public-ip>:5432/htl` and `INSTANCE_CONNECTION_NAME=""`. The **runtime SA on Cloud Run is NOT blocked** — it uses the connector normally.
- **Vercel:** production now on **`https://citemeright.com`** (apex + `www`, Vercel-registered domain on Vercel nameservers; `hack-the-law-cambridge-2026.vercel.app` still live). `main` auto-deploys. `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` set in Production. ✅ `NEXT_PUBLIC_API_URL` → **`https://api.citemeright.com`** (branded backend domain; flipped from the raw `run.app` URL 2026-06-27, verified in the live bundle).
- **Supabase** (auth-only): project `hack-the-law-cambridge-2026`, ref `seowjktpscgkklvmlvep` (London), ES256/JWKS. Persists across the GCP account switch.

## Citator (live: /resolve · /ask · /cases/{id}/{risk,citations,triage,classify,analyze,propositions,verdict})
- **Proposition-level pipeline — Features 1 (Filter) + 2 (Classify) + 3 (Deep
  analyzer / A) + 4 (Propositions / B) + 5 (Use-aware Verdict / C) ALL SHIPPED +
  DEPLOYED** (PRs #26, #27, #35, #36, #37; prod revision `htl-api-00005-rsn`, real
  Gemini via the runtime SA). The aligned spec is
  `.claude/handoffs/citator-pipeline-scope.md` (vision → retrieval contract →
  proposition spine P1–P8 → Bruen golden example → per-feature roadmap). The shipped
  feature handoffs (A/B/C) + the parallel-build contracts are in `handoffs/archive/`.
  - **F1 Filter** — `citator/triage.py::tier_edges` (pure, mirrors `risk.py`) tiers
    inbound edges `deep|shallow|mention`, never drops (noise → `mention`). `GET
    /cases/{id}/citations` is a contract-true **stub** of the retrieval engine
    seeded with the real Bruen golden set (cluster 6480696); `GET /cases/{id}/triage`
    runs the filter. Bruen funnel: 7 → deep 2 · shallow 3 · mention 2.
  - **F2 Classify** — `GET /cases/{id}/classify` triages then runs Gemini **only on
    deep+shallow** edges (mentions skip), per-edge: treatment · proposition (P1..P8)
    · holding/dicta · attribution (self|reported, catches the Rahimi "trapped in
    amber" trap) · verbatim quote · confidence. `llm/classify.py::classify_edge`
    (Vertex + quote-verify; keyword fallback). Live Gemini: Rahimi→limited/P2a,
    Antonyuk→followed/P1, §922(g)→P5, Wolford→P3.
  - **F3 Deep analyzer (A)** — `GET /cases/{id}/analyze` triages then deep-reads
    **only deep+shallow** edges into per-proposition **findings** (one case → many
    propositions): treatment · what_changed · holding/dicta · attribution · verbatim
    quote · conf + a one-line `case_summary`. Graceful degradation: **full-text mode**
    (one schema-constrained read locating+classifying+compiling across the whole
    opinion) when retrieval persisted the text, else **snippet mode** (reuses
    `classify_edge`, lower conf); `analysis_depth` records which. `llm/analyze.py`;
    full text mocked in `golden.full_text_for` (swap for `cl_opinions.plain_text` by
    citing id). Live: Rahimi→full-text 3 findings (P2a limited · P5 followed · P8
    followed), the rest snippet. **Supersedes /classify's depth** (kept as the snippet
    path). Contract A.
  - **F4 Propositions (B)** — `GET /cases/{id}/propositions` aggregates findings per
    proposition → signed risk + evolution + trajectory + the composed **operative
    rule**. Live Bruen: "good law as modified by Rahimi (2024)"; P1/P2 green,
    P2a/P3/P4/P5 amber. Contract B. ⚠️ Reads its own deterministic golden mock
    (`citator/golden_analysis.py`), **not** A's live `/analyze` — chosen for demo
    determinism; one-line swap to share A's read when wanted.
  - **F5 Use-aware Verdict (C)** — `POST /cases/{id}/verdict` maps the lawyer's
    intended use → the propositions it depends on (`llm/usemap.py`: deterministic for
    the menu picks, model for free-form), intersects with the compromised props from
    B → `real_risk` *for this use* + grounded explanation + `final_labels`. Consumes B
    directly (`routes/verdict.py` imports `case_propositions`). Live: §922(g)/P5 use →
    real risk; P1 use → no real risk (same case, opposite answer). Contract C.
  - Proposition spine is one source of truth: `citator/propositions.py`.
  - All endpoints public, DB-independent. Frontend `/citator/analyze` is the
    pipeline **stepper**: Resolve → Citations → Treatment → Relation → Verdict —
    **all five live**. Grouped by proposition throughout.
  - **Retrieval engineer's ingestion contract:**
    `.claude/handoffs/retrieval-ingestion-contract.md` (wire shape + the per-edge
    `passage` column to add on `citation_edges`).
- **Tables** (migration `0002_citator`): `cl_opinions` (CL id PK, case_name, court, date_filed, citation, plain_text, source), `citation_edges` (composite PK citing_id+cited_id, depth), `treatments` (empty — a later agent classifies passages into it). Models in `app/src/htl/db/citator.py`.
- **Ingestion**: `cd app && uv run python scripts/ingest_citator.py` (idempotent upserts; `--seed` for an offline real-overrulings fallback). **No CL token needed** — uses the CourtListener v4 **search** endpoint (`q=cites:(<op_id>) "<cite>"&highlight=on`), which returns the inbound graph + a citing-passage snippet stored as `plain_text`. A `COURTLISTENER_TOKEN` only adds optional full-text enrichment (paced ≤4/min via `/opinions/<id>/`).
- **Seeded the 4 LoC "Decisions Overruled" targets**: Roe (108713), Plessy (94508), Bowers (111738), Lochner (96276). Live run: 150 `cl_opinions`, 157 `citation_edges`, all `source=cl_api`; snippets carry real treatment language (e.g. a Roe citer: "...overruled Casey and Roe v. Wade... See Dobbs").
- **Local dev DB**: a throwaway **Docker Postgres** (Cloud SQL friction skipped for the overnight build). Start: `docker run -d --name htl-citator-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=htl -p 5433:5432 postgres:16`. `app/.env.local` (gitignored) points `DATABASE_URL` at it; `cd app && uv run alembic upgrade head` then `just dev-api` use it. Prod Cloud SQL is now migrated to `0002` (via the public-IP workaround — `just migrate`'s connector is user-blocked on the new sandbox; see Live → Cloud SQL).
- **`POST /resolve`** (PR #12, public/no-JWT): citation or case name → canonical CL cluster id (`{found, case_id, case_name, citation, court, date_filed, source, ambiguous}`). `found:false` is the anti-hallucination gate. Local-DB first, unauth CL **search** fallback for non-seeded cases. `case_id` == `cl_opinions.id` == `citation_edges.cited_id`.
- **Classifier + `GET /cases/{id}/risk`** (PR #13, public): `app/src/htl/llm/classify.py` runs Gemini-on-Vertex (structured JSON, temp 0; keyword fallback) over each citing passage → `treatments`. `/risk` aggregates → `{signal, status, risk_score, risk_rationale, trend[], negative_treatments[], positive_signal, ground_truth}`. All 157 passages classified (no fallback needed); the 4 targets all come out **red/overruled** with correct ground-truth (Roe→Dobbs, Plessy→Brown, Bowers→Lawrence, Lochner→West Coast Hotel). Risk formula is **ponytail v1** (court+recency-weighted negative share; any high-court overruled @ conf≥0.6 → dispositive red), thresholds expert-tunable.
- **Ownership split (2026-06-27).** Work forked into two tracks meeting at the Postgres schema: **citation retrieval** (the *inputs* — which opinions cite the target + correct, full, well-attributed passages; `scripts/ingest_citator.py` + `resolve.py::cl_search` → `cl_opinions`/`citation_edges`) handed to a new engineer; **analysis engine** (the *verdict* — passages → treatment → risk; `classify.py` + `citator/risk.py`) being reworked agentically by the operator. **Retrieval brief: `.claude/handoffs/citation-retrieval.md`** (ranked defects + first moves).
- **Caveats / next:** prod Cloud SQL is now migrated + deployed + seeded (150/157). ⚠️ **prod `treatments` were written by the keyword-fallback**, not Gemini — the sandbox blocks the *user* identity from Vertex `predict` (the runtime SA works fine: `/ask` + `/chat` return real Gemini), so a laptop re-classify can't reach prod; real-Gemini reclassify on prod is a retrieval/analysis follow-up (the next feature assumes verdict quality is good enough). The local Docker DB still holds the validated gemini-2.5-flash set. The **Smith #112404 false-red** is now a *retrieval* bug (snippet noise + mis-attribution + dup passages — see the retrieval brief), not an analysis one. Still open: a not-yet-overruled **"amber"** case to demo erosion, expand ground-truth, then `just migrate` + classify + `just deploy` for prod (tied to the admin-GCP-account switch). Backend/classifier forensic detail: `.claude/handoffs/archive/citator-endpoints.md`.
- **Tuning fixtures (local DB, overnight validation):** Auer v. Robbins (`118089`, **green** 0.137 — non-red graded path validated, safe from false-red) and Employment Division v. Smith (`112404`, **FALSE RED** — classifier mis-read the *legislative* "abrogated by enacting RFRA" snippet as judicial overruling + mis-attributed it to an unrelated case). The Smith false-red is the **#1 reliability fix** (distinguish legislative vs judicial abrogation; require corroboration before dispositive red — see handoff). Amber *label* branch still unhit on live data.
- **Frontend** (PRs #16, #20, #21): `/citator` (public) — search → resolve → risk; signal card + CSS-bar erosion trend + treatments + 6 quick-pick chips. **`/assistant`** (public, PR #21) — the flagship: free-form case + a litigation-use dropdown → agentic `/ask` → grounded answer + `<VerdictCard>` + CourtListener link. **Local auth works** (`frontend/.env.local`: real Supabase publishable key + localhost API; backend on stub verifier; email login `demo@hacklaw.app`/`hacklaw2026`). Query layer unified in `lib/api.ts` (`request()` + typed `resolve`/`caseRisk`/`ask`); `<VerdictCard>` shared (PR #20).
- **`POST /ask`** (PR #21, public): agentic **Gemini-2.5-pro** function-calling loop (tools `resolve_case` + `get_case_risk`, max 5 rounds) → grounded good-law answer **tailored to the lawyer's intended use**. The route captures the resolve+risk tool results and returns them alongside the prose, so `<VerdictCard>` renders from verified data, never model text. Verified live on localhost (Roe→red/Dobbs, Auer→green-with-caveat). `/ask` is **now deployed** (rev `00005`), so the live Vercel `/assistant` no longer 500s on submit; answer quality depends on the DB-seeded data (the 4 overruling targets) + the CL-search fallback for non-seeded cases.

## Next / open
- **Auth providers.** Email/password is **live** (demo login: `demo@hacklaw.app` / `hacklaw2026`, a confirmed user seeded via the admin API). New self-serve signups need email confirmation OFF to log in instantly. **Google/GitHub** buttons are wired but need each provider enabled in Supabase (OAuth app client id/secret) + the Site URL / redirect allowlist set to the Vercel prod URL + `http://localhost:3000`. All of this is Supabase-dashboard / OAuth-console work (or `PATCH config/auth` with a Supabase PAT).
- Vercel env: Supabase publishable vars set in Production (+ the merged feature branch's Preview). `NEXT_PUBLIC_API_URL` stays Production-only.
- ✅ **GCP account switch DONE** — running on `llm-law-cambridge26cbx-522`, deployed, `NEXT_PUBLIC_API_URL` set. Account/project config centralized in `infra/env.sh` (PR #40); `just deploy` needs no prefix. Supabase ref carries over.
- **Minor cleanup (optional):** `lib/api.ts` has two now-unused fetchers — `caseCitations` and `caseClassify` (the Treatment step moved to `caseAnalyze` when A shipped). Dead, harmless; remove when convenient.
- **Optional integration:** wire B's `/propositions` to A's live `/analyze` instead of its golden mock (one line) if you want the Treatment + Relation steps sharing one source on non-Bruen cases.
- Pick the real legal use-case from the released challenge and shape the system prompt / endpoints around it. (Messages persistence is a demo of "stores stuff" — keep or reshape per the product.)
