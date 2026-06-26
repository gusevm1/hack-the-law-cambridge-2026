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

# Build + deploy the API to Cloud Run. Override with PROJECT_ID=... REGION=...
deploy:
    ./infra/deploy.sh
