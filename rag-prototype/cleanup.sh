#!/bin/bash
# cleanup.sh - Deletes Agent Engine, RAG Corpus, GCS Buckets, Cloud Run, and Triggers

set -e

# 1. Load Environment Variables
if [ -f ".env" ]; then
    source ".env"
    echo "Loaded configuration from .env"
else
    echo "Error: .env file not found. Please run this from the project root."
    exit 1
fi

# Set defaults
SERVICE_NAME=${CLOUD_RUN_SERVICE_NAME:-"rag-ingestion-worker"}
TRIGGER_NAME="rag-gcs-trigger"
WORKER_SA="rag-worker-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
ACCESS_TOKEN=$(gcloud auth print-access-token)

echo "--------------------------------------------------------"
echo "WARNING: You are about to delete ALL resources:"
echo "  Project: $GOOGLE_CLOUD_PROJECT"
echo "  1. Agent Engine: $AGENT_ENGINE_ID"
echo "  2. RAG Corpus:   $RAG_CORPUS"
echo "  3. Source Bucket: gs://$SOURCE_GCS_BUCKET"
echo "  4. Staging Bucket: $STAGING_BUCKET"
echo "  5. Cloud Run:    $SERVICE_NAME"
echo "--------------------------------------------------------"
read -p "Are you sure? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi

# --- PART 1: RAG AGENT RESOURCES (Using REST API for stability) ---

# 2. Delete Vertex AI Agent Engine
if [ -n "$AGENT_ENGINE_ID" ]; then
    echo "Deleting Agent Engine via API..."
    ENGINE_ID=$(echo $AGENT_ENGINE_ID | awk -F'/' '{print $NF}')
    
    curl -X DELETE \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${GOOGLE_CLOUD_PROJECT}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines/${ENGINE_ID}" \
        || echo "Warning: Failed to delete Agent Engine."
else
    echo "AGENT_ENGINE_ID missing, skipping..."
fi

# 3. Delete RAG Corpus
if [ -n "$RAG_CORPUS" ]; then
    echo "Deleting RAG Corpus via API..."
    CORPUS_ID=$(echo $RAG_CORPUS | awk -F'/' '{print $NF}')
    
    curl -X DELETE \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${GOOGLE_CLOUD_PROJECT}/locations/${GOOGLE_CLOUD_LOCATION}/ragCorpora/${CORPUS_ID}" \
        || echo "Warning: Failed to delete Corpus."
else
    echo "RAG_CORPUS missing, skipping..."
fi

# 4. Delete Source GCS Bucket
if [ -n "$SOURCE_GCS_BUCKET" ]; then
    echo "Deleting Source Bucket..."
    gcloud storage rm --recursive "gs://$SOURCE_GCS_BUCKET" || echo "Bucket not found."
fi

# 5. Delete Staging GCS Bucket
if [ -n "$STAGING_BUCKET" ]; then
    echo "Deleting Staging Bucket..."
    gcloud storage rm --recursive "$STAGING_BUCKET" || echo "Bucket not found."
fi

# --- PART 2: AUTOMATION RESOURCES ---

# 6. Delete Eventarc Trigger
echo "Deleting Eventarc Trigger..."
gcloud eventarc triggers delete "$TRIGGER_NAME" \
    --location="$GOOGLE_CLOUD_LOCATION" \
    --quiet || echo "Trigger not found."

# 7. Delete Cloud Run Service
echo "Deleting Cloud Run Service..."
gcloud run services delete "$SERVICE_NAME" \
    --region="$GOOGLE_CLOUD_LOCATION" \
    --quiet || echo "Service not found."

# 8. Delete Pub/Sub Topic
if [ -n "$NOTIFICATION_TOPIC_ID" ]; then
    echo "Deleting Pub/Sub Topic..."
    gcloud pubsub topics delete "$NOTIFICATION_TOPIC_ID" \
        --quiet || echo "Topic not found."
fi

# 9. Delete Worker Service Account
echo "Deleting Worker Service Account..."
gcloud iam service-accounts delete "$WORKER_SA" --quiet || echo "SA not found."

# 10. Delete Custom IAM Role
ROLE_ID="ragCorpusQueryRole"
echo "Deleting Custom IAM Role..."
gcloud iam roles delete $ROLE_ID --project=$GOOGLE_CLOUD_PROJECT --quiet || echo "Role not found."

# 11. Delete Container Images
echo "Deleting Container Images..."
gcloud container images delete "gcr.io/${GOOGLE_CLOUD_PROJECT}/${SERVICE_NAME}" \
    --quiet --force-delete-tags || echo "Images not found."

echo "--------------------------------------------------------"
echo "✅ Cleanup Complete."
echo "--------------------------------------------------------"