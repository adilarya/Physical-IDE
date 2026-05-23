#!/usr/bin/env bash
# deploy.sh — deploy the Physical IDE backend to Google Cloud Run (Gen2).
# Run from the backend/ directory:  bash deploy.sh
set -euo pipefail

# ── Config — set these before running ───────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE="preflight-backend"
GEMINI_KEY="${GEMINI_API_KEY:-}"

if [ "$PROJECT_ID" = "your-gcp-project-id" ]; then
  echo "ERROR: set GCP_PROJECT_ID in your .env or export it before running."
  exit 1
fi

if [ -z "$GEMINI_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY is not set."
  exit 1
fi

echo "Deploying $SERVICE to $PROJECT_ID / $REGION..."

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --execution-environment gen2 \
  --cpu-boost \
  --session-affinity \
  --min-instances 1 \
  --timeout 300 \
  --port 8080 \
  --set-env-vars "MOCK_MODE=false,GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview,GEMINI_API_KEY=${GEMINI_KEY}"

echo ""
echo "Done. Get your service URL:"
gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format "value(status.url)"
