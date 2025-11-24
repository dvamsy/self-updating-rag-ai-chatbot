#!/bin/bash

# deploy_ingestion_worker.sh
# Automates the deployment of the RAG ingestion worker to Cloud Run.
# Works on both macOS and Linux.

set -e

# --- Helper Function to Update .env (Cross-Platform) ---
update_env() {
    local key=$1
    local val=$2
    local file=$3
    
    # Check if key exists
    if grep -q "^${key}=" "$file"; then
        # Check OS for sed compatibility
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS requires an empty string '' for in-place edits
            sed -i '' "s|^${key}=.*|${key}=${val}|" "$file"
        else
            # Linux (Cloud Shell) standard
            sed -i "s|^${key}=.*|${key}=${val}|" "$file"
        fi
    else
        # Append if missing
        echo "${key}=${val}" >> "$file"
    fi
    echo "📝 Updated .env: ${key}=${val}"
}

# 1. Load .env (Assumes script is run from project root)
if [ -f ".env" ]; then
  source ".env"
else
  echo "Error: .env file not found. Please run this from the project root."
  exit 1
fi

# Validations for core Google Cloud Config
if [ -z "$GOOGLE_CLOUD_PROJECT" ] || [ -z "$GOOGLE_CLOUD_LOCATION" ] || [ -z "$SOURCE_GCS_BUCKET" ]; then
  echo "Error: Missing required .env variables (PROJECT, LOCATION, or BUCKET)."
  exit 1
fi

# --- AUTO-CONFIGURATION SECTION ---

# 1. Check/Set CLOUD_RUN_SERVICE_NAME
if [ -z "$CLOUD_RUN_SERVICE_NAME" ] || [ "$CLOUD_RUN_SERVICE_NAME" == "YOUR_VALUE_HERE" ]; then
    NEW_SERVICE_NAME="rag-ingestion-worker"
    CLOUD_RUN_SERVICE_NAME=$NEW_SERVICE_NAME
    update_env "CLOUD_RUN_SERVICE_NAME" "$NEW_SERVICE_NAME" ".env"
fi

# 2. Check/Set NOTIFICATION_TOPIC_ID
if [ -z "$NOTIFICATION_TOPIC_ID" ] || [ "$NOTIFICATION_TOPIC_ID" == "YOUR_VALUE_HERE" ]; then
    # Generate a unique topic name
    NEW_TOPIC_ID="rag-updates-${GOOGLE_CLOUD_PROJECT}"
    NOTIFICATION_TOPIC_ID=$NEW_TOPIC_ID
    update_env "NOTIFICATION_TOPIC_ID" "$NEW_TOPIC_ID" ".env"
fi

# ----------------------------------

SERVICE_ACCOUNT="rag-worker-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
IMAGE_URI="gcr.io/${GOOGLE_CLOUD_PROJECT}/${CLOUD_RUN_SERVICE_NAME}"
SCRIPT_DIR="$(dirname "$0")"

echo "====================================================="
echo "🚀 Deploying: ${CLOUD_RUN_SERVICE_NAME}"
echo "📍 Region:    ${GOOGLE_CLOUD_LOCATION}"
echo "🔔 Topic:     ${NOTIFICATION_TOPIC_ID}"
echo "====================================================="

# 2. Enable APIs
echo "Enable required APIs..."
gcloud services enable \
  run.googleapis.com \
  eventarc.googleapis.com \
  pubsub.googleapis.com \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com

# 3. Create Service Account for the Worker
echo "Checking Service Account..."
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" --project="${GOOGLE_CLOUD_PROJECT}" &>/dev/null; then
  gcloud iam service-accounts create rag-worker-sa --display-name="RAG Ingestion Worker SA"
  echo "Created SA: ${SERVICE_ACCOUNT}"
  echo "⏳ Waiting 20 seconds for Service Account propagation..."
  sleep 20
else
  echo "SA ${SERVICE_ACCOUNT} already exists."
fi

# 4. Grant Permissions to the Service Account
echo "Granting permissions..."

# Allow SA to Use Vertex AI
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/aiplatform.user"

# Allow SA to Read from GCS
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectViewer"

# Allow SA to Publish to Pub/Sub
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/pubsub.publisher"

# Allow SA to act as a Service Account (for Eventarc)
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountTokenCreator"

# Allow SA to RECEIVE events (Critical for Eventarc Triggers)
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/eventarc.eventReceiver"

# Allow SA to INVOKE Cloud Run
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker"

# 5. Create Pub/Sub Topic
echo "Checking Pub/Sub Topic: ${NOTIFICATION_TOPIC_ID}..."
if ! gcloud pubsub topics describe "${NOTIFICATION_TOPIC_ID}" --project="${GOOGLE_CLOUD_PROJECT}" &>/dev/null; then
  gcloud pubsub topics create "${NOTIFICATION_TOPIC_ID}"
  echo "Topic created."
fi

# 6. Build Docker Image
echo "Building Docker Image..."
gcloud builds submit --tag "${IMAGE_URI}" "$SCRIPT_DIR"

# 7. Deploy Cloud Run Service
echo "Deploying Cloud Run Service..."
gcloud run deploy "${CLOUD_RUN_SERVICE_NAME}" \
  --image "${IMAGE_URI}" \
  --region "${GOOGLE_CLOUD_LOCATION}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}" \
  --set-env-vars="RAG_CORPUS=${RAG_CORPUS}" \
  --set-env-vars="NOTIFICATION_TOPIC_ID=${NOTIFICATION_TOPIC_ID}" \
  --no-allow-unauthenticated

# 8. Create Eventarc Trigger (Link GCS -> Cloud Run)
echo "Granting GCS permission to publish events..."

# Retrieve GCS Service Agent
SERVICE_AGENT=$(gcloud storage service-agent --project="${GOOGLE_CLOUD_PROJECT}")

# Grant Pub/Sub Publisher role to the GCS Service Agent
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
  --member="serviceAccount:${SERVICE_AGENT}" \
  --role="roles/pubsub.publisher"

echo "Creating Eventarc Trigger..."
gcloud eventarc triggers create rag-gcs-trigger \
  --location="${GOOGLE_CLOUD_LOCATION}" \
  --destination-run-service="${CLOUD_RUN_SERVICE_NAME}" \
  --destination-run-region="${GOOGLE_CLOUD_LOCATION}" \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=${SOURCE_GCS_BUCKET}" \
  --service-account="${SERVICE_ACCOUNT}" \
  || echo "Trigger creation warning (might already exist). Proceeding."

echo "====================================================="
echo "✅ Deployment Complete!"
echo "Service: ${CLOUD_RUN_SERVICE_NAME}"
echo "Trigger: Watching gs://${SOURCE_GCS_BUCKET}"
echo "====================================================="