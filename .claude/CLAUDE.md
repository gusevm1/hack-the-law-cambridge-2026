# Hack the Law Cambridge 2026 — session primer

Legal chatbot built for a hackathon. **Next.js (Vercel) → FastAPI (Cloud Run) → Gemini on Vertex AI.**

Read [`STATE.md`](../STATE.md) first — it's where we are right now. This file is the stable map.

## Stack & deploy

- **Backend** `app/` — FastAPI, `uv`, package `htl`. Layout mirrors jobmatch-ch (`routes/ · llm/ · models/ · settings · main`), trimmed. LLM is **Gemini on Vertex AI** via `google-genai`, async, ADC auth (no API key). Deploys to **Cloud Run** with `just deploy`.
- **Frontend** `frontend/` — Next.js + Tailwind, App Router, pnpm. Single chat page POSTing to `NEXT_PUBLIC_API_URL`. **`main` auto-deploys to Vercel.**
- **Infra** `infra/` — account-portable bootstrap + deploy scripts (env-var driven). See `infra/README.md`.

## Working agreement (terse)

- **ponytail by default** — laziest solution that holds. Run the ladder (YAGNI → stdlib → native → installed dep → one line → only then new code). Shortest working diff wins; mark deliberate shortcuts with a `ponytail:` comment naming the ceiling.
- **Account-portable infra** — never hardcode a project ID, region, or account into code. Everything GCP-specific flows through `infra/` env vars + `app/settings.py`. We switch to an admin GCP account soon; the rebuild must be `bootstrap` + `deploy` with new env values.
- **Surface decisions explicitly.** Propose; don't silently choose.
- Senior engineer — match register.

## Shipping changes

Every shippable change rides the **`ship-feature`** skill (`.claude/skills/ship-feature/`): branch off `main` → atomic commits → PR → CI green → squash-merge to `main`. **`main` is production** (Vercel auto-deploys the frontend; backend via `just deploy`). Never commit straight to `main`. No separate dev/prod split — `main` + localhost only.

## Quick reference

```sh
just dev-api          # backend on :8080
just dev-web          # frontend on :3000
just test             # backend tests (offline; LLM mocked)
just deploy           # backend -> Cloud Run (prints URL)
PROJECT_ID=<x> just gcp-bootstrap   # configure a (new) GCP project
```

- **GCP project (current/throwaway):** `hack-the-law-cambridge-2026`, region `europe-west1`, Vertex `global`, model `gemini-2.5-flash`.
- **GitHub:** `gusevm1/hack-the-law-cambridge-2026`.
- The Cloud Run service is `--allow-unauthenticated` (public) for speed — lock down before anything sensitive.
