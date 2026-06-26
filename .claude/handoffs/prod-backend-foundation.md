# Handoff — Production backend foundation (auth + Cloud SQL + observability)

**Mode line.** Next session is **executing** a foundational backend build — no product direction yet; this is the platform everything later sits on. Ride `ship-feature`, incremental PRs. Provisioning is account-portable — do it first. No blocking decisions: a Supabase project already exists and its signing alg is confirmed (ES256/JWKS).

## Goal
Mirror jobmatch-ch's production backend on GCP, minus its CV/credits domain:
- **Supabase = auth only** — verify ES256 JWTs against the project JWKS.
- **Cloud SQL Postgres = app data** — `users` + `messages`, async SQLAlchemy + Alembic.
- **Cross-cutting** — correlation IDs, structured JSON logging, error envelope.
- Gate `POST /chat` behind auth; persist each turn (user + assistant) tied to the user + correlation_id. (Messages are a demo of "stores stuff"; keep or drop per the product later.)

## Already provisioned — use these
- **Supabase project** `hack-the-law-cambridge-2026`, ref `seowjktpscgkklvmlvep` (London). Tied to the user's Supabase login → persists across the GCP admin-account switch.
  - JWKS `https://seowjktpscgkklvmlvep.supabase.co/auth/v1/.well-known/jwks.json` · issuer `https://seowjktpscgkklvmlvep.supabase.co/auth/v1` · audience `authenticated` · **alg ES256** (confirmed live).
  - Frontend env (publishable — safe to commit): `NEXT_PUBLIC_SUPABASE_URL=https://seowjktpscgkklvmlvep.supabase.co`, `NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_ttEputZDbHJJXqbflGfsZQ_bx2mCJ3p`. (service_role / `sb_secret_…` exist — fetch via `supabase projects api-keys`; never commit.)
- **Cloud SQL** — NOT running. A throwaway `htl-db` was provisioned then torn down to avoid orphaned cost; re-provision via the steps below (works on whatever GCP account you're on).

## Provision — extend `infra/` (account-portable, one command on any account)
Add to `infra/bootstrap.sh`:
1. Enable `sqladmin.googleapis.com`, `secretmanager.googleapis.com`.
2. Instance (validated): `gcloud sql instances create htl-db --database-version POSTGRES_16 --tier db-f1-micro --region "$REGION" --storage-size 10 --storage-type HDD --availability-type zonal --root-password <gen>`.
3. `gcloud sql databases create htl --instance htl-db`; `gcloud sql users create htl_app --instance htl-db --password <gen>`.
4. Store the app password in Secret Manager (`htl-db-password`); grant the Cloud Run runtime SA `roles/secretmanager.secretAccessor`.
5. Grant the runtime SA `roles/cloudsql.client` (the connector authenticates via IAM).

Add to `infra/deploy.sh`: `--add-cloudsql-instances <CONN>` + `--set-secrets DB_PASSWORD=htl-db-password:latest` + `--set-env-vars INSTANCE_CONNECTION_NAME=<CONN>,DB_USER=htl_app,DB_NAME=htl,SUPABASE_JWKS_URL=…,SUPABASE_ISSUER=…`.
`CONN` = `PROJECT:REGION:htl-db` (e.g. `hack-the-law-cambridge-2026:europe-west1:htl-db`).

## Code plan — package `htl` (read jobmatch `app/src/jobmatch_ch/` for SHAPE; re-derive, never copy)
- `correlation.py` — ULID correlation id: contextvar + pure-ASGI middleware, reuse inbound `X-Correlation-ID` else mint, echo it on the response. `get_correlation_id()`.
- `logging_config.py` — structlog JSON to stdout (Cloud Run → Cloud Logging), a processor injecting `correlation_id`.
- `errors.py` — `AppError`/`Unauthorized` + handler → `{"error":{"code","message","correlation_id"}}`.
- `db/base.py` (DeclarativeBase) · `db/models.py` (`users`: id, supabase_sub UNIQUE, email, created_at; `messages`: id, user_id→users FK, role, content, correlation_id, created_at) · `db/engine.py` (async engine via the **Cloud SQL connector**, snippet below) · `db/repositories.py` (`get_or_create_user` with IntegrityError race-collapse; `add_message`).
- `auth/interface.py` — `Principal{user_id, supabase_sub, email, is_stub}` + `AuthVerifier` Protocol (`async verify(authorization) -> Principal`).
- `auth/supabase.py` — `jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)`; `jwt.decode(token, key.key, algorithms=["ES256"], audience, issuer, options={"require":["exp","iat","sub"]})`; JWKS fetch in `asyncio.to_thread`; then lazy `get_or_create_user(sub,email)` → `Principal`. Inject a `SigningKeyResolver` Protocol so tests pass a local key (no network).
- `auth/stub.py` — fixed dev principal (`user_id = 00000000-0000-0000-0000-000000000001`) for local/CI.
- `routes/dependencies.py` — `get_verifier()` (lru_cache; Supabase if `supabase_jwks_url` + `supabase_issuer` set, else stub) · `CurrentUser` · `get_session`/`DbSession`.
- `routes/chat.py` — add `user: CurrentUser, session: DbSession`; persist user msg + assistant reply stamped with `get_correlation_id()`.
- `main.py` — `configure_logging()`; add `CorrelationIdMiddleware` outermost; CORS with `expose_headers=["X-Correlation-ID"]`; register the error handler; lifespan disposes the engine.
- `settings.py` — add `instance_connection_name`, `db_user`, `db_password`, `db_name`, `database_url` (local fallback), `supabase_jwks_url`, `supabase_issuer`, `supabase_audience="authenticated"`.
- `alembic/` — env builds a **sync** engine via the connector (pg8000); `0001_init` creates both tables + seeds the stub user.
- `pyproject.toml` deps: `sqlalchemy[asyncio]`, `cloud-sql-python-connector[asyncpg,pg8000]`, `alembic`, `pyjwt[crypto]`, `structlog`, `python-ulid`.

### Cloud SQL connector engine (the non-obvious bit — verified pattern)
```python
from google.cloud.sql.connector import Connector
connector = Connector()
async def getconn():
    return await connector.connect_async(CONN, "asyncpg", user=…, password=…, db=…)
engine = create_async_engine("postgresql+asyncpg://", async_creator=getconn, pool_pre_ping=True)
```
Alembic (sync): `connector.connect(CONN, "pg8000", …)` + `create_engine("postgresql+pg8000://", creator=getconn)`. Works on Cloud Run and locally via ADC — no proxy, no IP allowlist.

## General workflows (capture each as a short `.claude/` note as you build)
- **Migration**: edit `db/models.py` → `alembic revision --autogenerate -m "…"` → review → `alembic upgrade head` (locally via connector; later a Cloud Run Job).
- **New service/endpoint**: `routes/<x>.py` (+ `service/<x>.py` if logic-heavy), gate with `CurrentUser`, use `DbSession`, stamp `get_correlation_id()` on writes, `include_router`.
- **Trace a request**: response `X-Correlation-ID` → filter Cloud Logging by it (every log line + persisted rows carry it). Port jobmatch's `trace-correlation-id` skill (GCP-flavoured) once this exists.
- **Ship**: `ship-feature` — branch → atomic commits → PR → CI green → squash-merge. `main` = prod.

## Definition of done
- `just lint && just test` green — tests override `get_verifier`→stub and `get_session`→fake session (offline; no DB/Supabase).
- Migration applied; deployed with Supabase env; a real ES256 token → `/chat` 200, one `users` row + two `messages` rows, `correlation_id` populated, `X-Correlation-ID` header present; bad/expired/wrong-aud → 401 envelope.
- Unit test: verifier accepts a locally-minted ES256 token (injected resolver) and rejects tampered/expired/wrong-aud.

## Open decisions (non-blocking)
1. Frontend sign-in: email magic-link / OAuth / **anonymous**. Anonymous (`supabase.auth.signInAnonymously()`, enable in the project) is the fastest real-JWT path to demo E2E; swap for real login later.
2. Persist messages (recommended — proves storage) vs users-only.
3. Migrations: locally via connector now vs a Cloud Run Job for CI later.

## First moves
1. `git switch -c feat/prod-backend-auth-db origin/main`.
2. Extend `infra/bootstrap.sh` + `deploy.sh` (Cloud SQL + Secret Manager + IAM); `just gcp-bootstrap` to provision.
3. Build `correlation`/`logging`/`errors` → `db/` → `auth/` → wire `routes/` + `main.py`; tests.
4. `alembic upgrade head`; deploy; run the DoD checks.
5. Frontend: `@supabase/supabase-js` + a sign-in; attach `Authorization: Bearer <access_token>` in `lib/api.ts`.

## Teardown
Move to `.claude/handoffs/archive/` when the foundation ships.
