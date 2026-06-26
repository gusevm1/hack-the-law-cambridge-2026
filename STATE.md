# STATE

Where the project is right now. Update this as reality moves.

## Now
- Scaffold + **production backend foundation shipped** (PR #6): Supabase JWT auth (ES256/JWKS), Cloud SQL Postgres (`users` + `messages`) via async SQLAlchemy + the Cloud SQL connector + Alembic, correlation IDs, structured JSON logging, and a uniform error envelope.
- `POST /chat` is gated behind a verified user and persists both turns (user + assistant), stamped with the user + correlation id. `get_verifier` auto-selects Supabase (when JWKS+issuer set) else a dev/CI stub.
- Backend on Cloud Run; Gemini-on-Vertex wired (async, ADC auth). Frontend: real **login** (email/password + Google/GitHub buttons) gating the chat, with the signed-in email + sign-out in the top-right; `/chat` calls carry the session `Bearer`.

## Live
- **GCP project:** `hack-the-law-cambridge-2026` (throwaway — switching to admin account soon).
- **Cloud Run service:** `htl-api` @ `europe-west1`. URL: `https://htl-api-ixnpjv7vsq-ew.a.run.app` (revision `htl-api-00003-j94`). Deployed with Cloud SQL attached + Supabase env. DoD verified live: real ES256 token → `/chat` 200 + 1 `users` row + 2 `messages` rows (correlation_id == `X-Correlation-ID`); no/bad token → 401 envelope. Public (`--allow-unauthenticated`); the app-level JWT gate is the real access control now.
- **Cloud SQL:** `htl-db` @ `europe-west1` (POSTGRES_16, db-f1-micro, ENTERPRISE edition). DB `htl`, user `htl_app` (password in Secret Manager `htl-db-password`). Conn: `hack-the-law-cambridge-2026:europe-west1:htl-db`. Migrated to `0001`.
- **Vercel:** `https://hack-the-law-cambridge-2026.vercel.app` (live, `main` auto-deploys). `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` set in Production.
- **Supabase** (auth-only): project `hack-the-law-cambridge-2026`, ref `seowjktpscgkklvmlvep` (London), ES256/JWKS. Persists across the GCP account switch.

## Next / open
- **Auth providers.** Email/password is **live** (demo login: `demo@hacklaw.app` / `hacklaw2026`, a confirmed user seeded via the admin API). New self-serve signups need email confirmation OFF to log in instantly. **Google/GitHub** buttons are wired but need each provider enabled in Supabase (OAuth app client id/secret) + the Site URL / redirect allowlist set to the Vercel prod URL + `http://localhost:3000`. All of this is Supabase-dashboard / OAuth-console work (or `PATCH config/auth` with a Supabase PAT).
- Vercel env: Supabase publishable vars set in Production (+ the merged feature branch's Preview). `NEXT_PUBLIC_API_URL` stays Production-only.
- Tomorrow: switch to admin GCP account → `PROJECT_ID=<new> CREATE_PROJECT=1 ... just gcp-bootstrap && just migrate && just deploy`, then update `NEXT_PUBLIC_API_URL`. Infra is account-portable; Supabase ref carries over.
- Pick the real legal use-case from the released challenge and shape the system prompt / endpoints around it. (Messages persistence is a demo of "stores stuff" — keep or reshape per the product.)
