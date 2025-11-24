# validate_corpus.py

import os
from google.cloud import aiplatform_v1beta1
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")
RAG_CORPUS_ID = os.environ.get("RAG_CORPUS")

def list_corpus_files():
    """
    Lists all the files within a specified Vertex AI RAG Corpus.
    """
    print(f"🔍 Inspecting RAG Corpus: {RAG_CORPUS_ID}")
    print(f"📍 Region: {LOCATION}")

    try:
        # Construct the API endpoint for the specified location
        API_ENDPOINT = f"{LOCATION}-aiplatform.googleapis.com"
        client_options = {"api_endpoint": API_ENDPOINT}

        # Initialize the Vertex RAG Data Service Client
        rag_client = aiplatform_v1beta1.VertexRagDataServiceClient(client_options=client_options)

        # Create the request to list files in the corpus
        request = aiplatform_v1beta1.ListRagFilesRequest(parent=RAG_CORPUS_ID)
        page_result = rag_client.list_rag_files(request=request)

        print("\n--- 📄 Files in Corpus ---")
        files = list(page_result)

        if not files:
            print("⚠️ The corpus is currently empty.")
        else:
            for rag_file in files:
                # Extract just the numeric ID for cleaner reading
                short_id = rag_file.name.split('/')[-1]

                print(f"File: {rag_file.display_name}")
                print(f"  ID: {short_id}")
                
                # --- FIX: Print the status object directly ---
                # This avoids version conflicts with Enum lookups
                print(f"  Status: {rag_file.file_status}")
                print("-" * 30)

        print("\n✅ Verification complete.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("  - Please check if the RAG_CORPUS_ID in your .env file is correct.")
        print("  - Ensure the service account has 'Vertex AI User' permissions.")


if __name__ == "__main__":
    if not all([PROJECT_ID, LOCATION, RAG_CORPUS_ID]):
        print("❌ Error: Missing required environment variables.")
        print("  Please ensure GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, and RAG_CORPUS are set in your .env file.")
    else:
        list_corpus_files()