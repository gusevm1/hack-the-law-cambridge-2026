# CiteMeRight API

FastAPI backend for the legal good-law checker. **Gemini on Vertex AI**
(GCP-native auth via ADC — no API key), async, plus **Postgres** (Cloud SQL) for
the citation graph and **Supabase JWT** auth on the chat path.

The full endpoint surface, the five-stage citator pipeline, and how to run it live
in the [root README](../README.md). This file is just the backend layout + the
local-dev essentials.

## Local dev

```bash
cd app
uv sync
cp .env.local.example .env.local         # point DATABASE_URL at a local Postgres
gcloud auth application-default login     # one-time, for Vertex
uv run alembic upgrade head               # schema
uv run python scripts/ingest_citator.py --seed   # demo citation graph
uv run uvicorn htl.main:app --reload --port 8080
```

## Test / lint

```bash
uv run pytest          # offline — the LLM call is mocked
uv run ruff check src tests
```

## Deploy

From the repo root: `just deploy` (Cloud Run, builds from this Dockerfile). See
[`infra/README.md`](../infra/README.md) for account-portable infra.

## Layout

```
src/htl/
  main.py        FastAPI app, CORS, correlation-id + error middleware, routers
  settings.py    pydantic-settings (env-driven)
  routes/        health, chat, resolve, risk, citations, triage, classify,
                 analyze, propositions, graph, inspect, ask, verdict
  llm/           vertex (Gemini call), router, classify, analyze, usemap
  citator/       the pipeline: triage, retrieval, propositions, evolution,
                 verdict, risk, golden fixtures, courts, certwatch, cl_client
  db/            async SQLAlchemy engine, models, repositories (users, messages,
                 cl_opinions, citation_edges, treatments)
  auth/          Supabase JWT (ES256/JWKS) + dev stub verifier
  models/api.py  request/response schemas
scripts/         ingest_citator, classify_citator, scrape_scotus_grants
alembic/         migrations (0001 base, 0002 citator)
```
