# Infra — account-portable GCP

Two scripts, both parameterized by env vars. **Nothing is hardcoded to one login**: the account/project lives in one place — [`env.sh`](env.sh) — and the whole backend rebuilds on a different account by editing it (or overriding `PROJECT_ID` and friends in the environment).

| Script | Does |
|---|---|
| `env.sh` | **Source of truth** for `PROJECT_ID` + `REGION`. Sourced by the two scripts and `just migrate`. Edit here to switch accounts. |
| `bootstrap.sh` | (optionally create project) → link billing → enable APIs (Run, Vertex, Cloud Build, Artifact Registry) → grant `roles/aiplatform.user` to the Cloud Run runtime SA. Idempotent. |
| `deploy.sh` | `gcloud run deploy --source app/` (Cloud Build builds the Dockerfile), sets env vars, prints the service URL. |

## Env vars (with defaults)

| Var | Default | Used by |
|---|---|---|
| `PROJECT_ID` | `llm-law-cambridge26cbx-522` (in `env.sh`) | both |
| `REGION` | `europe-west1` (in `env.sh`) | both (Cloud Run region) |
| `BILLING_ACCOUNT` | _(unset)_ | bootstrap (link billing) |
| `CREATE_PROJECT` | `0` | bootstrap (set `1` to create the project) |
| `ORG_ID` | _(unset)_ | bootstrap (org for a created project) |
| `SERVICE` | `htl-api` | deploy (Cloud Run service name) |
| `VERTEX_LOCATION` | `global` | deploy (Gemini region) |
| `GEMINI_MODEL` | `gemini-3.5-flash` | deploy (unmapped-task default; per-task routing lives in settings) |

## Rebuild on a new account (the tomorrow case)

```bash
gcloud auth login                       # switch to the admin account
gcloud auth application-default login    # ADC for local Vertex calls

PROJECT_ID=htl-prod BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX CREATE_PROJECT=1 ORG_ID=123456789 \
  ./infra/bootstrap.sh

PROJECT_ID=htl-prod ./infra/deploy.sh    # prints the new Cloud Run URL
```

Then point the frontend at the new URL (`NEXT_PUBLIC_API_URL` in Vercel + local `.env.local`).

> The API is deployed `--allow-unauthenticated` (public) for hackathon speed. Before anything sensitive, lock it down (IAM-authenticated invoker, or Supabase JWT verification in the app — the `routes/` seam is where auth would slot in).
