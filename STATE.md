# STATE

Where the project is right now. Update this as reality moves.

## Now
- Initial scaffold: FastAPI backend (`/health`, `/chat`) + Next.js chatbox + account-portable GCP infra.
- Backend deploys to Cloud Run; Gemini-on-Vertex wired (async, ADC auth).
- Frontend: single chat page → `NEXT_PUBLIC_API_URL`.

## Live
- **GCP project:** `hack-the-law-cambridge-2026` (throwaway — switching to admin account soon).
- **Cloud Run service:** `htl-api` @ `europe-west1`. URL: `https://htl-api-ixnpjv7vsq-ew.a.run.app` (verified: `/health` ok, `/chat` returns live Gemini answers). Public (`--allow-unauthenticated`).
- **Vercel:** `https://hack-the-law-cambridge-2026.vercel.app` (live). Project `maxims-projects-e4175e3c/hack-the-law-cambridge-2026`, root dir `frontend`, GitHub-connected → **`main` auto-deploys**. `NEXT_PUBLIC_API_URL` set to the Cloud Run URL (production).

## Next / open
- Tomorrow: switch to admin GCP account → `PROJECT_ID=<new> CREATE_PROJECT=1 ... just gcp-bootstrap && just deploy`, then update `NEXT_PUBLIC_API_URL`.
- **Auth (Supabase JWT):** planned — brief at `.claude/handoffs/auth-supabase-jwt.md`. Gate `/chat` with a verifier dependency mirroring jobmatch-ch (no DB here → Principal is just sub+email). Blocked only on confirming the Supabase project's signing alg (ES256/JWKS vs HS256).
- Pick the real legal use-case from the released challenge and shape the system prompt / endpoints around it.
