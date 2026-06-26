# STATE

Where the project is right now. Update this as reality moves.

## Now
- Scaffold + **production backend foundation shipped** (PR #6): Supabase JWT auth (ES256/JWKS), Cloud SQL Postgres (`users` + `messages`) via async SQLAlchemy + the Cloud SQL connector + Alembic, correlation IDs, structured JSON logging, and a uniform error envelope.
- `POST /chat` is gated behind a verified user and persists both turns (user + assistant), stamped with the user + correlation id. `get_verifier` auto-selects Supabase (when JWKS+issuer set) else a dev/CI stub.
- Backend on Cloud Run; Gemini-on-Vertex wired (async, ADC auth). Frontend: single chat page → `NEXT_PUBLIC_API_URL`, now signs in anonymously via Supabase and sends `Authorization: Bearer`.

## Live
- **GCP project:** `hack-the-law-cambridge-2026` (throwaway — switching to admin account soon).
- **Cloud Run service:** `htl-api` @ `europe-west1`. URL: `https://htl-api-ixnpjv7vsq-ew.a.run.app` (revision `htl-api-00003-j94`). Deployed with Cloud SQL attached + Supabase env. DoD verified live: real ES256 token → `/chat` 200 + 1 `users` row + 2 `messages` rows (correlation_id == `X-Correlation-ID`); no/bad token → 401 envelope. Public (`--allow-unauthenticated`); the app-level JWT gate is the real access control now.
- **Cloud SQL:** `htl-db` @ `europe-west1` (POSTGRES_16, db-f1-micro, ENTERPRISE edition). DB `htl`, user `htl_app` (password in Secret Manager `htl-db-password`). Conn: `hack-the-law-cambridge-2026:europe-west1:htl-db`. Migrated to `0001`.
- **Vercel:** `https://hack-the-law-cambridge-2026.vercel.app` (live, `main` auto-deploys). `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` set in Production.
- **Supabase** (auth-only): project `hack-the-law-cambridge-2026`, ref `seowjktpscgkklvmlvep` (London), ES256/JWKS. Persists across the GCP account switch.

## Next / open
- **⚠️ Enable anonymous sign-ins in Supabase** (Auth → Sign In/Providers → Anonymous) — currently OFF, so the deployed frontend's anonymous sign-in fails until flipped. The backend + frontend code is ready; this is a one-toggle dashboard change (or PATCH `config/auth {external_anonymous_users_enabled:true}` with a Supabase PAT). The live DoD used a service_role-minted password user instead.
- Vercel **Preview** env: the Supabase vars are Production-only (CLI quirk on the preview add; matches the existing Production-only `NEXT_PUBLIC_API_URL`). Add to Preview if PR previews need working auth.
- Tomorrow: switch to admin GCP account → `PROJECT_ID=<new> CREATE_PROJECT=1 ... just gcp-bootstrap && just migrate && just deploy`, then update `NEXT_PUBLIC_API_URL`. Infra is account-portable; Supabase ref carries over.
- Pick the real legal use-case from the released challenge and shape the system prompt / endpoints around it. (Messages persistence is a demo of "stores stuff" — keep or reshape per the product.)
