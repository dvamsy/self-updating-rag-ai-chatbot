#!/bin/bash
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Script to grant RAG Corpus access permissions to AI Platform Reasoning Engine Service Agent

set -e

# 1. Resolve the path to the .env file (Go up 3 levels from this script)
# Script is in: ai_agent/vertex_engine_deploy/
SCRIPT_DIR="$(dirname "$0")"
ENV_FILE="${SCRIPT_DIR}/../../.env"

if [ -f "$ENV_FILE" ]; then
  echo "Loading configuration from $ENV_FILE"
  # Export variables from .env so execution can see them
  export $(grep -v '^#' "$ENV_FILE" | xargs)
else
  echo "Error: .env file not found at $ENV_FILE"
  exit 1
fi

# 2. Get Project ID and Number
PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
if [ -z "$PROJECT_ID" ]; then
  echo "Error: GOOGLE_CLOUD_PROJECT not found in .env"
  exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
if [ -z "$PROJECT_NUMBER" ]; then
  echo "Failed to retrieve project number for project $PROJECT_ID"
  exit 1
fi

# 3. Construct the Service Account Email
# This is the specialized identity that runs your Agent Engine in the cloud
SERVICE_ACCOUNT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

# 4. Get RAG Corpus ID
if [ -z "$RAG_CORPUS" ]; then
  echo "RAG_CORPUS environment variable is not set in the .env file"
  exit 1
fi

# Extract just the numeric ID if the full path is provided
RAG_CORPUS_ID=$(echo $RAG_CORPUS | awk -F'/' '{print $NF}')
# Reconstruct full resource name to be safe
RAG_CORPUS_RESOURCE="projects/${PROJECT_NUMBER}/locations/${GOOGLE_CLOUD_LOCATION}/ragCorpora/${RAG_CORPUS_ID}"

echo "--------------------------------------------------------"
echo "Granting permissions for:"
echo "  Project: $PROJECT_ID"
echo "  Service Account: $SERVICE_ACCOUNT"
echo "  RAG Corpus: $RAG_CORPUS_RESOURCE"
echo "--------------------------------------------------------"

# 5. Ensure the AI Platform service identity exists
gcloud alpha services identity create --service=aiplatform.googleapis.com --project="$PROJECT_ID" 2>/dev/null || true

# 6. Create Custom Role (if it doesn't exist)
ROLE_ID="ragCorpusQueryRole"
ROLE_TITLE="RAG Corpus Query Role"
ROLE_DESCRIPTION="Custom role with permission to query RAG Corpus"

echo "Checking if custom role $ROLE_ID exists..."
if gcloud iam roles describe "$ROLE_ID" --project="$PROJECT_ID" &>/dev/null; then
  echo "Custom role $ROLE_ID already exists."
else
  echo "Creating custom role $ROLE_ID..."
  gcloud iam roles create "$ROLE_ID" \
    --project="$PROJECT_ID" \
    --title="$ROLE_TITLE" \
    --description="$ROLE_DESCRIPTION" \
    --permissions="aiplatform.ragCorpora.query"
  echo "Custom role created."
fi

# 7. Bind the Role to the Service Account
echo "Binding role to Service Account..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="projects/$PROJECT_ID/roles/$ROLE_ID" \
  --condition=None \
  --quiet

echo ""
echo "✅ Success! The Agent Engine can now read your RAG Corpus."