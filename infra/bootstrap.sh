#!/usr/bin/env bash
# Account-portable GCP setup. Rebuild the backend infra on ANY account/project by
# changing env vars — nothing here is hardcoded to one login.
#
#   PROJECT_ID=my-new-proj BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX \
#   CREATE_PROJECT=1 ORG_ID=123456789 ./infra/bootstrap.sh
#
# Idempotent — safe to re-run. After this, run ./infra/deploy.sh.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-hack-the-law-cambridge-2026}"
REGION="${REGION:-europe-west1}"
BILLING_ACCOUNT="${BILLING_ACCOUNT:-}"
ORG_ID="${ORG_ID:-}"
CREATE_PROJECT="${CREATE_PROJECT:-0}"

echo "==> Project: $PROJECT_ID   Region: $REGION"

if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  if [ "$CREATE_PROJECT" = "1" ]; then
    echo "==> Creating project $PROJECT_ID"
    if [ -n "$ORG_ID" ]; then
      gcloud projects create "$PROJECT_ID" --organization="$ORG_ID"
    else
      gcloud projects create "$PROJECT_ID"
    fi
  else
    echo "Project $PROJECT_ID not found. Set CREATE_PROJECT=1 (and optionally ORG_ID) to create it." >&2
    exit 1
  fi
fi

gcloud config set project "$PROJECT_ID" >/dev/null

if [ -n "$BILLING_ACCOUNT" ]; then
  echo "==> Linking billing account $BILLING_ACCOUNT"
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT" >/dev/null
fi

echo "==> Enabling APIs (Cloud Run, Vertex AI, Cloud Build, Artifact Registry, Cloud SQL, Secret Manager)"
gcloud services enable \
  run.googleapis.com aiplatform.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com \
  --project="$PROJECT_ID"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "==> Granting Vertex AI access to Cloud Run runtime SA: $RUNTIME_SA"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/aiplatform.user" --condition=None >/dev/null

# `gcloud run deploy --source` builds as the compute SA; it needs builder rights
# (read source bucket, write Artifact Registry, logs). Required on fresh projects.
echo "==> Granting Cloud Build builder role to runtime SA"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/cloudbuild.builds.builder" --condition=None >/dev/null

# --- Cloud SQL (Postgres) — app data store --------------------------------
# The app connects via the Cloud SQL Python connector (IAM-authenticated, no
# proxy / no IP allowlist), so the instance needs no public-IP allowlisting.
DB_INSTANCE="${DB_INSTANCE:-htl-db}"
DB_NAME="${DB_NAME:-htl}"
DB_USER="${DB_USER:-htl_app}"
DB_PASSWORD_SECRET="${DB_PASSWORD_SECRET:-htl-db-password}"

if ! gcloud sql instances describe "$DB_INSTANCE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> Creating Cloud SQL instance $DB_INSTANCE (POSTGRES_16, db-f1-micro) — a few minutes"
  gcloud sql instances create "$DB_INSTANCE" \
    --project="$PROJECT_ID" \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region="$REGION" \
    --storage-size=10 --storage-type=HDD \
    --availability-type=zonal \
    --root-password="$(openssl rand -hex 24)"
else
  echo "==> Cloud SQL instance $DB_INSTANCE already exists"
fi

# App-user password lives in Secret Manager. Generate ONCE; re-runs reuse it so
# the deployed app's credential never silently rotates out from under it.
if ! gcloud secrets describe "$DB_PASSWORD_SECRET" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> Creating Secret Manager secret $DB_PASSWORD_SECRET"
  APP_DB_PASSWORD="$(openssl rand -hex 24)"
  printf '%s' "$APP_DB_PASSWORD" | gcloud secrets create "$DB_PASSWORD_SECRET" \
    --project="$PROJECT_ID" --data-file=- >/dev/null
else
  echo "==> Secret $DB_PASSWORD_SECRET already exists — reusing its value"
  APP_DB_PASSWORD="$(gcloud secrets versions access latest --secret="$DB_PASSWORD_SECRET" --project="$PROJECT_ID")"
fi

echo "==> Ensuring database $DB_NAME and user $DB_USER exist"
gcloud sql databases describe "$DB_NAME" --instance="$DB_INSTANCE" --project="$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud sql databases create "$DB_NAME" --instance="$DB_INSTANCE" --project="$PROJECT_ID"
# `users create` is idempotent-by-intent: set the password to the secret value
# whether the user is new or pre-existing, so secret and DB never drift.
if gcloud sql users list --instance="$DB_INSTANCE" --project="$PROJECT_ID" --format='value(name)' | grep -qx "$DB_USER"; then
  gcloud sql users set-password "$DB_USER" --instance="$DB_INSTANCE" --project="$PROJECT_ID" --password="$APP_DB_PASSWORD"
else
  gcloud sql users create "$DB_USER" --instance="$DB_INSTANCE" --project="$PROJECT_ID" --password="$APP_DB_PASSWORD"
fi

echo "==> Granting runtime SA Secret Manager + Cloud SQL client access"
gcloud secrets add-iam-policy-binding "$DB_PASSWORD_SECRET" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/cloudsql.client" --condition=None >/dev/null

echo ""
echo "==> Bootstrap complete."
echo "    Cloud SQL connection name: ${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
echo "    Next: apply migrations (just migrate) then deploy (./infra/deploy.sh)."
