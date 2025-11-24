import json
import os
import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1
import vertexai
from vertexai.preview import rag

# --- Environment Variable Validation ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION")
NOTIFICATION_TOPIC_ID = os.environ.get("NOTIFICATION_TOPIC_ID")
RAG_CORPUS_NAME = os.environ.get("RAG_CORPUS")

REQUIRED_ENV_VARS = {
    "GOOGLE_CLOUD_PROJECT": PROJECT_ID,
    "GOOGLE_CLOUD_LOCATION": LOCATION,
    "NOTIFICATION_TOPIC_ID": NOTIFICATION_TOPIC_ID,
    "RAG_CORPUS": RAG_CORPUS_NAME,
}

missing_vars = [var for var, val in REQUIRED_ENV_VARS.items() if not val]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

# --- GLOBAL INITIALIZATION (Run once on Cold Start) ---
print(f"🌍 Global Init: Initializing Vertex AI for {LOCATION}...")
# We use vertexai.init() directly as it handles the API endpoint logic for us
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Initialize Pub/Sub Client globally
pubsub_publisher = pubsub_v1.PublisherClient()
notification_topic_path = pubsub_publisher.topic_path(PROJECT_ID, NOTIFICATION_TOPIC_ID)


@functions_framework.cloud_event
def rag_ingestion_handler(cloud_event: CloudEvent):
    """
    Handles GCS file upload events.
    """
    # No need for global keywords as we are using the global clients directly
    file_name = "unknown"
    gcs_uri = "unknown"

    try:
        # --- 1. Extract Event Data ---
        data = cloud_event.data
        bucket_name = data.get("bucket")
        file_name = data.get("name")

        if not bucket_name or not file_name:
            print("❌ Incomplete GCS data.")
            return ("Incomplete data", 400)

        # IGNORE FOLDERS
        if file_name.endswith("/"):
            print(f"📂 Ignoring folder creation event: {file_name}")
            return ("Folder ignored", 200)

        gcs_uri = f"gs://{bucket_name}/{file_name}"
        print(f"📂 Received new GCS file: {gcs_uri}")

        # --- 2. Start RAG Import Job ---
        print(f"🚀 Starting RAG import for corpus: {RAG_CORPUS_NAME}...")
        # The client is already initialized globally with the correct region
        operation = rag.import_files(
            corpus_name=RAG_CORPUS_NAME,
            paths=[gcs_uri],
        )
        print(f"✅ Import operation started: {operation.operation.name}")

        # --- 3. Publish Notification ---
        message = {
            "status": "RAG_UPDATE_INITIATED",
            "file_name": file_name,
            "gcs_uri": gcs_uri,
            "corpus_name": RAG_CORPUS_NAME,
            "operation_id": operation.operation.name
        }
        future = pubsub_publisher.publish(
            notification_topic_path, json.dumps(message).encode("utf-8")
        )
        future.result()

        print(f"🔔 Notification sent for {file_name}")
        return ("RAG import initiated.", 200)

    except Exception as e:
        print(f"❌ Error: {e}")
        # Attempt failure notification
        try:
            fail_msg = {"status": "RAG_UPDATE_FAILED", "file_name": file_name, "error": str(e)}
            pubsub_publisher.publish(notification_topic_path, json.dumps(fail_msg).encode("utf-8"))
        except:
            pass
        # Return 500 so Eventarc knows to retry if needed (or check logs)
        return (f"Error: {e}", 500)