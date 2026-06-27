# Hack the Law Cambridge 2026 — CiteMeRight

A **legal good-law checker** (citator). A lawyer gives a case and what they intend
to rely on it for; the system answers whether that case is still *good law for that
specific use* — grounded in the real citations that cite it, never in model
free-text.

**Next.js** UI (Vercel) → **FastAPI** API (Cloud Run) → **Gemini on Vertex AI**
(GCP-native, no API key) + **Postgres** (Cloud SQL) for the citation graph, with
**CourtListener** as the citation data source and **Supabase** for auth.

```
frontend/   Next.js UI         → auto-deploys to Vercel on push to main
app/        FastAPI API        → deploys to Cloud Run via `just deploy`
infra/      account-portable GCP bootstrap + deploy (env-var driven)
data/       SCOTUS cert-granted dockets (cert-watch input)
.claude/    ship-feature workflow + handoffs
```

Production: frontend **citemeright.com**, backend **api.citemeright.com**.
For *where the project is right now* (live URLs, revisions, open work) read
[`STATE.md`](STATE.md) — this README is the stable map.

## What it does

The core is a five-stage **citator pipeline** that turns "who cites this case?"
into "is it still good law for *your* use?". Each stage is a live endpoint and a
step in the `/citator/analyze` UI.

| # | Stage | Endpoint | What it does |
|---|-------|----------|--------------|
| 1 | **Filter** | `GET /cases/{id}/triage` | Tier inbound citing edges `deep · shallow · mention` (noise never dropped, just demoted). |
| 2 | **Classify** | `GET /cases/{id}/classify` | Gemini per edge (deep+shallow only): treatment · proposition · holding/dicta · attribution · verbatim quote · confidence. |
| 3 | **Deep analyzer** | `GET /cases/{id}/analyze` | Deep-read each edge into per-**proposition** findings (full-text when available, snippet fallback). |
| 4 | **Propositions** | `GET /cases/{id}/propositions` | Aggregate findings per proposition → signed risk + evolution + the composed **operative rule**. |
| 5 | **Use-aware verdict** | `POST /cases/{id}/verdict` | Map the lawyer's intended use → the propositions it depends on → real risk *for that use*. |

Same case, different use → different answer: e.g. *Bruen* reads "good law as
modified by *Rahimi* (2024)" — fine for one proposition, compromised for another.

### Full endpoint surface

All endpoints are public (the app-level Supabase JWT gate is the real access
control on the chat path; the citator path is open by design).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness → `{"status":"ok"}` |
| `POST` | `/resolve` | Citation or case name → canonical CourtListener cluster id (`found:false` = anti-hallucination gate). |
| `GET` | `/cases/{id}/citations` | Inbound citing set for a case (retrieval layer). |
| `GET` | `/cases/{id}/triage` | Stage 1 — filter/tier the edges. |
| `GET` | `/cases/{id}/classify` | Stage 2 — per-edge classification. |
| `GET` | `/cases/{id}/analyze` | Stage 3 — per-proposition deep findings. |
| `GET` | `/cases/{id}/propositions` | Stage 4 — aggregate to the operative rule. |
| `POST` | `/cases/{id}/verdict` | Stage 5 — use-aware verdict. |
| `GET` | `/cases/{id}/risk` | Single-shot aggregate risk signal (red/amber/green + rationale + trend). |
| `GET` | `/cases/{id}/graph` | Citation graph for visualisation. |
| `GET` | `/cases/{id}/inspect` | Dev data inspector — every edge, its provenance, stored passage, treatments. |
| `POST` | `/ask` | Agentic Gemini function-calling loop (`resolve` + `risk` tools) → grounded good-law answer tailored to the intended use. |
| `POST` | `/chat` | Plain Gemini chat (JWT-gated, persists both turns) — the original demo path. |

### Frontend pages

| Route | What |
|---|---|
| `/assistant` | **Flagship** — free-form case + a litigation-use dropdown → grounded answer + verdict card + CourtListener link. |
| `/citator` | Search → resolve → risk: signal card, erosion-trend bars, treatments, quick-pick chips. |
| `/citator/analyze` | The five-stage pipeline as a **stepper**: Resolve → Citations → Treatment → Relation → Verdict. |
| `/dev` | Data inspector over `/inspect` — see exactly what's in the DB for a case and why. |
| `/` | Auth-gated Gemini chat (email/password + Google/GitHub buttons) — the original demo. |

## Quickstart (local)

You need: [`uv`](https://docs.astral.sh/uv/), `pnpm`, `just`, the `gcloud` CLI,
and Docker (for a local Postgres). Python 3.12.

```bash
# 0. One-time: ADC so local Vertex (Gemini) calls authenticate
gcloud auth application-default login

# 1. Local Postgres for the citation graph (citator endpoints)
docker run -d --name htl-citator-pg \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=htl -p 5433:5432 postgres:16

# 2. Backend
cd app
uv sync
cp .env.local.example .env.local      # point DATABASE_URL at the docker pg on :5433
uv run alembic upgrade head           # create the schema
uv run python scripts/ingest_citator.py --seed   # seed the demo citation graph
cd .. && just dev-api                  # http://localhost:8080

# 3. Frontend (new terminal)
cd frontend
pnpm install
cp .env.example .env.local            # NEXT_PUBLIC_API_URL=http://localhost:8080
just dev-web                           # http://localhost:3000
```

Auth is optional locally: with Supabase env unset the backend uses a dev stub
verifier. The seeded login (when Supabase is wired) is `demo@hacklaw.app` /
`hacklaw2026`. The citator pages (`/citator`, `/citator/analyze`, `/assistant`)
are public and need no login.

> **Why a local DB?** Cloud SQL's connector is blocked for the *user* identity on
> the current sandbox, so migrate/ingest run against a throwaway Docker Postgres
> locally. The Cloud Run runtime SA reaches prod Cloud SQL normally. See
> [`STATE.md`](STATE.md) → Live → Cloud SQL.

## Commands (`just`)

```sh
just            # list all recipes
just dev-api    # backend on :8080 (reload)
just dev-web    # frontend on :3000
just test       # backend tests (offline; LLM mocked)
just lint       # ruff over app/
just build-web  # frontend production build
just migrate    # alembic upgrade head against Cloud SQL (via connector + ADC)
just deploy     # build + deploy API to Cloud Run (prints the URL)
just gcp-bootstrap   # configure a GCP project (APIs + IAM)
```

### Data / ingestion

```sh
cd app
uv run python scripts/ingest_citator.py          # pull the inbound citation graph from CourtListener (v4 search; no token)
uv run python scripts/ingest_citator.py --seed   # offline fallback seed (the demo cases)
uv run python scripts/classify_citator.py         # classify stored passages into treatments
uv run python scripts/scrape_scotus_grants.py     # refresh the SCOTUS cert-granted dockets (cert-watch input)
```

A `COURTLISTENER_TOKEN` is optional (adds full-text enrichment, paced ≤4/min).
Without it, ingestion uses the public CourtListener search endpoint.

## Deploy

- **Backend → Cloud Run:** `just deploy` (Cloud Build builds `app/Dockerfile`,
  prints the service URL). Project/region flow from `infra/env.sh`.
- **Frontend → Vercel:** push to `main`; Vercel auto-deploys `frontend/`. Set
  `NEXT_PUBLIC_API_URL` (→ the backend URL) plus the Supabase publishable vars in
  the Vercel project env.

## Switching GCP accounts

Nothing is hardcoded to one login — the account/project lives in
[`infra/env.sh`](infra/env.sh). On a new account:

```bash
gcloud auth login                              # the new account
gcloud auth application-default login          # ADC for local Vertex
PROJECT_ID=<new-project> BILLING_ACCOUNT=<acct> CREATE_PROJECT=1 ORG_ID=<org> \
  just gcp-bootstrap
PROJECT_ID=<new-project> just deploy
```

Then point the frontend at the new backend URL (`NEXT_PUBLIC_API_URL` in Vercel +
local `.env.local`). Full rebuild flow + the env-var table:
[`infra/README.md`](infra/README.md). The `api.citemeright.com` domain mapping is
account-scoped — recreate it on a switch (see [`STATE.md`](STATE.md)).

## Workflow

Every change rides the **`ship-feature`** skill: branch off `main` → atomic
commits → PR → CI green → squash-merge. `main` is production (Vercel auto-deploys
the frontend; backend via `just deploy`). Never commit straight to `main`. See
[`.claude/skills/ship-feature/SKILL.md`](.claude/skills/ship-feature/SKILL.md).
