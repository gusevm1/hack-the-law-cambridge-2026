# Hack the Law Cambridge 2026 — command surface. Run `just` to list.
set shell := ["bash", "-cu"]

# --- backend (app/) ---------------------------------------------------------

# Run the API locally with reload on :8080
dev-api:
    cd app && uv run uvicorn htl.main:app --reload --port 8080

test:
    cd app && uv run pytest -q

lint:
    cd app && uv run ruff check src tests

# --- frontend (frontend/) ---------------------------------------------------

# Run the chat UI locally on :3000
dev-web:
    cd frontend && pnpm dev

build-web:
    cd frontend && pnpm build

# --- infra (account-portable — see infra/README.md) -------------------------

# Configure a GCP project (APIs + IAM). Override with PROJECT_ID=... etc.
gcp-bootstrap:
    ./infra/bootstrap.sh

# Apply DB migrations to Cloud SQL via the connector + your gcloud ADC.
# Account-portable: pulls the app password from Secret Manager, composes the
# connection name from PROJECT_ID/REGION/DB_INSTANCE (same defaults as infra/).
migrate:
    #!/usr/bin/env bash
    set -euo pipefail
    source infra/env.sh  # PROJECT_ID, REGION — the account/project source of truth
    DB_INSTANCE="${DB_INSTANCE:-htl-db}"
    export INSTANCE_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
    export DB_USER="${DB_USER:-htl_app}"
    export DB_NAME="${DB_NAME:-htl}"
    export DB_PASSWORD="$(gcloud secrets versions access latest --secret=htl-db-password --project="$PROJECT_ID")"
    cd app
    # The connector calls the SQL Admin API over TLS; point Python at certifi's
    # CA bundle so verification works on machines without a system bundle (macOS).
    export SSL_CERT_FILE="$(uv run python -m certifi)"
    uv run alembic upgrade head

# Load a citator pg_dump (COPY format) into Cloud SQL via the connector — no CL, no
# psql/proxy. TRUNCATEs + reloads the 3 citator tables. Usage: just load-dump <path>
load-dump dump:
    #!/usr/bin/env bash
    set -euo pipefail
    source infra/env.sh
    export INSTANCE_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${DB_INSTANCE:-htl-db}"
    export DB_USER="${DB_USER:-htl_app}"
    export DB_NAME="${DB_NAME:-htl}"
    export DB_PASSWORD="$(gcloud secrets versions access latest --secret=htl-db-password --project="$PROJECT_ID")"
    cd app
    export SSL_CERT_FILE="$(uv run python -m certifi)"
    uv run python scripts/load_dump.py "{{dump}}"

# Build + deploy the API to Cloud Run. Override with PROJECT_ID=... REGION=...
deploy:
    ./infra/deploy.sh
