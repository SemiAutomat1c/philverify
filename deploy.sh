#!/usr/bin/env bash
# ── PhilVerify — Firebase + Cloud Run Deployment Script ───────────────────────
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh YOUR_GCP_PROJECT_ID
#
# Prerequisites:
#   brew install google-cloud-sdk firebase-cli
#   gcloud auth login
#   gcloud auth configure-docker
#   firebase login

set -euo pipefail

PROJECT_ID="${1:-}"
REGION="asia-southeast1"
SERVICE_NAME="philverify-api"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: ./deploy.sh YOUR_GCP_PROJECT_ID"
  exit 1
fi

echo "▶ Project: $PROJECT_ID | Region: $REGION | Service: $SERVICE_NAME"

# ── 1. Set GCP project ────────────────────────────────────────────────────────
gcloud config set project "$PROJECT_ID"

# ── 2. Build + push Docker image to GCR ──────────────────────────────────────
echo ""
echo "▶ Building & pushing Docker image (this takes ~10 min first time)…"
gcloud builds submit \
  --tag "$IMAGE" \
  --timeout=30m \
  .

# ── 3. Deploy to Cloud Run ────────────────────────────────────────────────────
echo ""
echo "▶ Deploying to Cloud Run…"
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --concurrency 10 \
  --timeout 300 \
  --min-instances 1 \
  --max-instances 3 \
  --set-env-vars "APP_ENV=production,DEBUG=false,LOG_LEVEL=INFO" \
  --set-env-vars "ALLOWED_ORIGINS=https://${PROJECT_ID}.web.app,https://${PROJECT_ID}.firebaseapp.com"
  # Add secrets like NEWS_API_KEY via:
  # --update-secrets NEWS_API_KEY=philverify-news-api-key:latest

# ── 4. Link Firebase project ──────────────────────────────────────────────────
echo ""
echo "▶ Setting Firebase project…"
firebase use "$PROJECT_ID"

# ── 5. Build React frontend ───────────────────────────────────────────────────
echo ""
echo "▶ Building React frontend…"
cd frontend
npm ci
npm run build
cd ..

# ── 6. Deploy to Firebase Hosting ────────────────────────────────────────────
echo ""
echo "▶ Deploying to Firebase Hosting…"
firebase deploy --only hosting,firestore

echo ""
echo "✅  Deploy complete!"
echo "   Frontend: https://${PROJECT_ID}.web.app"
echo "   API:      https://${PROJECT_ID}.web.app/api/health"
