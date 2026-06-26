# Hack the Law Cambridge 2026

Legal chatbot. **Next.js** chat UI (Vercel) → **FastAPI** API (Cloud Run) → **Gemini on Vertex AI** (GCP-native, no API key).

```
frontend/   Next.js chatbox  → deploys to Vercel on push to main
app/        FastAPI API       → deploys to Cloud Run via `just deploy`
infra/      account-portable GCP bootstrap + deploy scripts
.claude/    workflow setup (ship-feature) for clean PRs
```

## Quickstart (local)

```bash
# 1. Backend
cd app && uv sync
gcloud auth application-default login          # one-time, for Vertex
just dev-api                                   # http://localhost:8080

# 2. Frontend (new terminal)
cd frontend && pnpm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8080" > .env.local
just dev-web                                   # http://localhost:3000
```

## Deploy

- **Backend → Cloud Run:** `just deploy` (prints the service URL).
- **Frontend → Vercel:** push to `main`; Vercel auto-deploys. Set `NEXT_PUBLIC_API_URL` to the Cloud Run URL in the Vercel project's env vars.

## Switching GCP accounts (e.g. tomorrow's admin account)

Nothing is hardcoded to one login. On the new account:

```bash
gcloud auth login                              # the admin account
PROJECT_ID=<new-project> BILLING_ACCOUNT=<acct> CREATE_PROJECT=1 ORG_ID=<org> \
  just gcp-bootstrap
PROJECT_ID=<new-project> just deploy
```

See [`infra/README.md`](infra/README.md) for the full rebuild flow.

## Workflow

Every change rides the **`ship-feature`** skill: branch off `main` → atomic commits → PR → merge to `main`. `main` is production (auto-deploys the frontend to Vercel). See [`.claude/skills/ship-feature/SKILL.md`](.claude/skills/ship-feature/SKILL.md).
