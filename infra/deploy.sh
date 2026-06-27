#!/usr/bin/env bash
# Build + deploy the API to Cloud Run from app/. Account-portable via env vars.
# Cloud Build builds app/Dockerfile; no local Docker needed.
set -euo pipefail

# shellcheck source=infra/env.sh
source "$(dirname "$0")/env.sh"  # PROJECT_ID, REGION — the account/project source of truth
SERVICE="${SERVICE:-htl-api}"
VERTEX_LOCATION="${VERTEX_LOCATION:-global}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash}"

# --- Cloud SQL + Supabase auth (provisioned by bootstrap.sh) ----------------
DB_INSTANCE="${DB_INSTANCE:-htl-db}"
DB_NAME="${DB_NAME:-htl}"
DB_USER="${DB_USER:-htl_app}"
DB_PASSWORD_SECRET="${DB_PASSWORD_SECRET:-htl-db-password}"
CONN="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"

# Supabase is auth-only and tied to the user's Supabase login — it persists
# across the GCP account switch, so its (non-secret) ref is the default here,
# overridable for a different project. Issuer/JWKS derive from the ref.
SUPABASE_REF="${SUPABASE_REF:-seowjktpscgkklvmlvep}"
SUPABASE_ISSUER="${SUPABASE_ISSUER:-https://${SUPABASE_REF}.supabase.co/auth/v1}"
SUPABASE_JWKS_URL="${SUPABASE_JWKS_URL:-https://${SUPABASE_REF}.supabase.co/auth/v1/.well-known/jwks.json}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Deploying $SERVICE to Cloud Run ($PROJECT_ID / $REGION), Cloud SQL $CONN"
gcloud run deploy "$SERVICE" \
  --source "$ROOT/app" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --add-cloudsql-instances "$CONN" \
  --set-secrets "DB_PASSWORD=${DB_PASSWORD_SECRET}:latest" \
  --set-env-vars "GCP_PROJECT=${PROJECT_ID},VERTEX_LOCATION=${VERTEX_LOCATION},GEMINI_MODEL=${GEMINI_MODEL},INSTANCE_CONNECTION_NAME=${CONN},DB_USER=${DB_USER},DB_NAME=${DB_NAME},SUPABASE_ISSUER=${SUPABASE_ISSUER},SUPABASE_JWKS_URL=${SUPABASE_JWKS_URL}" \
  --port 8080

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
echo ""
echo "==> Deployed:  $URL"
echo "==> Health:    curl $URL/health"
echo "==> Set the frontend's NEXT_PUBLIC_API_URL to: $URL"
