#!/usr/bin/env bash
# Build + deploy the API to Cloud Run from app/. Account-portable via env vars.
# Cloud Build builds app/Dockerfile; no local Docker needed.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-hack-the-law-cambridge-2026}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-htl-api}"
VERTEX_LOCATION="${VERTEX_LOCATION:-global}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Deploying $SERVICE to Cloud Run ($PROJECT_ID / $REGION)"
gcloud run deploy "$SERVICE" \
  --source "$ROOT/app" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT=${PROJECT_ID},VERTEX_LOCATION=${VERTEX_LOCATION},GEMINI_MODEL=${GEMINI_MODEL}" \
  --port 8080

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
echo ""
echo "==> Deployed:  $URL"
echo "==> Health:    curl $URL/health"
echo "==> Set the frontend's NEXT_PUBLIC_API_URL to: $URL"
