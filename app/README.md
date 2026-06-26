# Legal chatbot API

FastAPI backend. One LLM endpoint backed by **Gemini on Vertex AI** (GCP-native auth via ADC — no API key). Async, so a single instance fans out many concurrent calls.

## Endpoints
- `GET /health` → `{"status": "ok"}`
- `POST /chat` → `{ "message": str, "history": [{role, content}] }` ⟶ `{ "reply": str }`

## Local dev
```bash
cd app
uv sync
cp .env.local.example .env.local        # edit if needed
gcloud auth application-default login    # one-time, for Vertex
uv run uvicorn htl.main:app --reload --port 8080
```

## Test
```bash
uv run pytest          # offline — the LLM call is mocked
```

## Deploy
From the repo root: `just deploy` (Cloud Run, builds from this Dockerfile). See root README for account-portable infra.

## Layout
```
src/htl/
  main.py        FastAPI app, CORS, routers
  settings.py    pydantic-settings (env-driven)
  routes/        health.py, chat.py
  llm/vertex.py  async Gemini-on-Vertex call
  models/api.py  request/response schemas
```
Mirrors jobmatch-ch's `routes/ · llm/ · models/ · settings · main` shape, trimmed to what a chatbot needs (no db/storage/auth layers yet).
