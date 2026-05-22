#!/usr/bin/env bash
# One-shot Cloud Run deploy for the Physical IDE agent backend.
# Run from physical-ide/backend:   bash deploy.sh
set -euo pipefail

GCLOUD="/opt/homebrew/share/google-cloud-sdk/bin/gcloud"
PROJECT="io-chmuseum25mtv-1832"
REGION="us-central1"
SERVICE="physical-ide-agent"
SECRET_NAME="gemini-api-key"
GEMINI_API_KEY="REDACTED_API_KEY"

echo "[deploy] project=$PROJECT  region=$REGION  service=$SERVICE"

# --- 1. Enable required APIs (idempotent) ---------------------------------
echo "[deploy] enabling APIs..."
$GCLOUD services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project="$PROJECT" --quiet

# --- 2. Store API key in Secret Manager (idempotent) ----------------------
if $GCLOUD secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
  echo "[deploy] updating existing secret..."
  echo -n "$GEMINI_API_KEY" | $GCLOUD secrets versions add "$SECRET_NAME" \
    --data-file=- --project="$PROJECT"
else
  echo "[deploy] creating secret..."
  echo -n "$GEMINI_API_KEY" | $GCLOUD secrets create "$SECRET_NAME" \
    --data-file=- --project="$PROJECT"
fi

# --- 3. Deploy to Cloud Run -----------------------------------------------
echo "[deploy] building and deploying (this takes ~2 min)..."
$GCLOUD run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT" \
  --allow-unauthenticated \
  --min-instances 1 \
  --timeout 300 \
  --port 8080 \
  --set-env-vars "MOCK_MODE=false,GEMINI_STRATEGY=parallel,GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview,GEMINI_VISION_MODEL=gemini-2.5-flash,GEMINI_TEXT_MODEL=gemini-2.5-flash,GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts,GEMINI_IMAGE_MODEL=imagen-3.0-generate-002" \
  --set-secrets "GEMINI_API_KEY=${SECRET_NAME}:latest"

# --- 4. Print the deployed URL -------------------------------------------
URL=$($GCLOUD run services describe "$SERVICE" \
  --region="$REGION" --project="$PROJECT" --format="value(status.url)")

echo ""
echo "============================================"
echo " DEPLOYED: $URL"
echo " WebSocket: ${URL/https/wss}/ws/agent"
echo "============================================"
echo ""
echo "Set in frontend/.env:"
echo "  VITE_WS_URL=${URL/https/wss}/ws/agent"
echo "  VITE_MOCK_SOCKET=false"
