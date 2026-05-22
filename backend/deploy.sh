#!/usr/bin/env bash
# One-shot Cloud Run deploy for the Physical IDE agent backend.
# Run from physical-ide/backend :   bash deploy.sh
set -euo pipefail

gcloud run deploy physical-ide-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 1 \
  --timeout 300 \
  --port 8080 \
  --set-env-vars "MOCK_MODE=true,GEMINI_STRATEGY=parallel"

# --- GO LIVE (real Gemini) -------------------------------------------------
# Do NOT bake the API key into --set-env-vars. Store it in Secret Manager:
#
#   echo -n "$GEMINI_API_KEY" | gcloud secrets create gemini-key --data-file=-
#
# then redeploy with:
#
#   gcloud run deploy physical-ide-agent --source . --region us-central1 \
#     --allow-unauthenticated --min-instances 1 --timeout 300 --port 8080 \
#     --set-env-vars "MOCK_MODE=false,GEMINI_STRATEGY=parallel" \
#     --set-secrets "GEMINI_API_KEY=gemini-key:latest"
