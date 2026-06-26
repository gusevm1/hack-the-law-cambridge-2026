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

echo "==> Enabling APIs (Cloud Run, Vertex AI, Cloud Build, Artifact Registry)"
gcloud services enable \
  run.googleapis.com aiplatform.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com \
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

echo "==> Bootstrap complete. Next: ./infra/deploy.sh"
