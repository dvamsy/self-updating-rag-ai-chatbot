# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from google.auth import default
from google.api_core.exceptions import ResourceExhausted
import vertexai
from vertexai.preview import rag
from google.cloud import storage
import os
from dotenv import load_dotenv, set_key
import requests
import tempfile
import uuid

# Load environment variables from .env file
load_dotenv()

# --- Please fill in your configurations ---
# Retrieve the PROJECT_ID from the environmental variables.
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID:
    raise ValueError(
        "GOOGLE_CLOUD_PROJECT environment variable not set. Please set it in your .env file."
    )
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
if not LOCATION:
    raise ValueError(
        "GOOGLE_CLOUD_LOCATION environment variable not set. Please set it in your .env file."
    )
CORPUS_DISPLAY_NAME = "Alphabet_10K_2024_corpus"
CORPUS_DESCRIPTION = "Corpus containing Alphabet's 10-K 2024 document"
# Initial URL (Primary)
PDF_URL = "https://abc.xyz/assets/77/51/9841ad5c4fbe85b4440c47a4df8d/goog-10-k-2024.pdf"
PDF_FILENAME = "goog-10-k-2024.pdf"
# Goes up one folder to check the .env file and update
ENV_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))


# --- Start of the script ---
def initialize_vertex_ai():
  credentials, _ = default()
  vertexai.init(
      project=PROJECT_ID, location=LOCATION, credentials=credentials
  )

def update_env_file(key, value, env_file_path):
    """Updates the .env file with a specific key-value pair."""
    try:
        set_key(env_file_path, key, value)
        print(f"Updated {key} in {env_file_path} to {value}")
    except Exception as e:
        print(f"Error updating .env file: {e}")

def ensure_bucket_exists(bucket_name, location):
    """Helper to create a GCS bucket if it doesn't exist."""
    storage_client = storage.Client(project=PROJECT_ID)
    try:
        # Strip gs:// if present for the API call, as client.bucket() expects just the name
        clean_name = bucket_name.replace("gs://", "")
        bucket = storage_client.bucket(clean_name)
        if not bucket.exists():
            print(f"Bucket {clean_name} not found. Creating in {location}...")
            bucket.create(location=location)
            print(f"Bucket {clean_name} created successfully.")
        else:
            print(f"Bucket {clean_name} found.")
        return clean_name
    except Exception as e:
        print(f"Failed to access or create bucket {bucket_name}: {e}")
        raise e

def ensure_source_bucket(env_file_path):
    """
    Checks for SOURCE_GCS_BUCKET in .env. 
    If missing, generates one and adds it.
    Ensures the value in .env is JUST the name (no gs://).
    """
    bucket_name = os.getenv("SOURCE_GCS_BUCKET")
    
    # 1. If variable is missing or placeholder, generate a new name
    if not bucket_name or bucket_name == "YOUR_VALUE_HERE":
        # Generate unique name: rag-source-[project_id]-[short_uuid]
        random_suffix = uuid.uuid4().hex[:6]
        bucket_name = f"rag-source-{PROJECT_ID}-{random_suffix}"
        
        # Update .env immediately with RAW name (no gs://)
        update_env_file("SOURCE_GCS_BUCKET", bucket_name, env_file_path)
        print(f"Generated new source bucket name configuration: {bucket_name}")
    
    # 2. Safety check: If user manually added gs:// in .env, clean it for usage here
    clean_name = bucket_name.replace("gs://", "")

    # 3. Ensure it exists in Cloud
    ensure_bucket_exists(clean_name, LOCATION)

    return clean_name

def ensure_staging_bucket(env_file_path):
    """
    Checks for STAGING_BUCKET in .env. 
    If missing, generates one, creates it, and updates .env WITH 'gs://' prefix.
    """
    staging_bucket = os.getenv("STAGING_BUCKET")
    
    # 1. If variable is missing or placeholder, generate a new name
    if not staging_bucket or staging_bucket == "YOUR_VALUE_HERE":
        # Generate unique name
        random_suffix = uuid.uuid4().hex[:6]
        raw_bucket_name = f"rag-staging-{PROJECT_ID}-{random_suffix}"
        
        # Create the bucket in GCS
        ensure_bucket_exists(raw_bucket_name, LOCATION)

        # Format WITH gs:// for the .env file (Required for Vertex AI staging)
        staging_uri = f"gs://{raw_bucket_name}"
        
        # Update .env
        update_env_file("STAGING_BUCKET", staging_uri, env_file_path)
        print(f"Generated new staging bucket configuration: {staging_uri}")
        return raw_bucket_name
    
    # 2. If it exists, ensure the physical bucket is there
    # Remove gs:// for the API check
    raw_bucket_name = staging_bucket.replace("gs://", "")
    ensure_bucket_exists(raw_bucket_name, LOCATION)

    # 3. Ensure the .env value actually starts with gs:// (Fix if user forgot)
    if not staging_bucket.startswith("gs://"):
        staging_uri = f"gs://{staging_bucket}"
        update_env_file("STAGING_BUCKET", staging_uri, env_file_path)
    
    return raw_bucket_name

def create_or_get_corpus():
  """Creates a new corpus or retrieves an existing one."""
  embedding_model_config = rag.EmbeddingModelConfig(
      publisher_model="publishers/google/models/text-embedding-004"
  )
  existing_corpora = rag.list_corpora()
  corpus = None
  for existing_corpus in existing_corpora:
    if existing_corpus.display_name == CORPUS_DISPLAY_NAME:
      corpus = existing_corpus
      print(f"Found existing corpus with display name '{CORPUS_DISPLAY_NAME}'")
      break
  if corpus is None:
    corpus = rag.create_corpus(
        display_name=CORPUS_DISPLAY_NAME,
        description=CORPUS_DESCRIPTION,
        embedding_model_config=embedding_model_config,
    )
    print(f"Created new corpus with display name '{CORPUS_DISPLAY_NAME}'")
  return corpus

def download_pdf_from_url(url, output_path):
  """Downloads a PDF file from the specified URL with browser-like headers."""
  print(f"Downloading PDF from {url}...")
  
  # Add headers to mimic a real browser (Chrome)
  headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  }
  
  try:
      response = requests.get(url, headers=headers, stream=True)
      response.raise_for_status()  # Raise an exception for HTTP errors
      
      with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
          f.write(chunk)
      
      print(f"PDF downloaded successfully to {output_path}")
      return output_path
  except Exception as e:
      print(f"Failed to download from primary URL. Error: {e}")
      # Fallback URL (hosted on Q4CDN, often easier to download from)
      fallback_url = "https://s206.q4cdn.com/479360582/files/doc_financials/2024/q4/goog-10-k-2024.pdf"
      print(f"Attempting download from fallback URL: {fallback_url}...")
      
      response = requests.get(fallback_url, headers=headers, stream=True)
      response.raise_for_status()
      
      with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
          f.write(chunk)
          
      print(f"PDF downloaded successfully to {output_path}")
      return output_path

def upload_to_gcs(bucket_name, source_file_path, destination_blob_name):
    """Uploads a file to the Google Cloud Storage bucket."""
    try:
        storage_client = storage.Client(project=PROJECT_ID)
        # Ensure bucket name is clean for upload (no gs://)
        clean_bucket_name = bucket_name.replace("gs://", "")
        bucket = storage_client.bucket(clean_bucket_name)
        blob = bucket.blob(destination_blob_name)

        print(f"Uploading {destination_blob_name} to gs://{clean_bucket_name}...")
        blob.upload_from_filename(source_file_path)
        print(f"File uploaded to GCS successfully.")
    except Exception as e:
        print(f"Error uploading to GCS: {e}")

def upload_pdf_to_corpus(corpus_name, pdf_path, display_name, description):
  """Uploads a PDF file to the specified corpus."""
  print(f"Uploading {display_name} to RAG Corpus...")
  try:
    rag_file = rag.upload_file(
        corpus_name=corpus_name,
        path=pdf_path,
        display_name=display_name,
        description=description,
    )
    print(f"Successfully uploaded {display_name} to corpus")
    return rag_file
  except ResourceExhausted as e:
    print(f"Error uploading file {display_name}: {e}")
    return None
  except Exception as e:
    # If file already exists, we can ignore the error for idempotency
    if "409" in str(e) or "already exists" in str(e):
       print(f"File {display_name} already exists in corpus. Skipping upload.")
       return None
    print(f"Error uploading file {display_name}: {e}")
    return None

def list_corpus_files(corpus_name):
  """Lists files in the specified corpus."""
  files = list(rag.list_files(corpus_name=corpus_name))
  print(f"Total files in corpus: {len(files)}")
  for file in files:
    print(f"File: {file.display_name} - {file.name}")


def main():
  initialize_vertex_ai()
  
  # 1. Ensure Source GCS Bucket exists (Stores only name in .env)
  source_bucket_name = ensure_source_bucket(ENV_FILE_PATH)

  # 2. Ensure Staging Bucket exists (Stores gs://name in .env)
  ensure_staging_bucket(ENV_FILE_PATH)
  
  # 3. Ensure RAG Corpus exists
  corpus = create_or_get_corpus()

  # Update the .env file with the corpus name
  update_env_file("RAG_CORPUS", corpus.name, ENV_FILE_PATH)
  
  # Create a temporary directory to store the downloaded PDF
  with tempfile.TemporaryDirectory() as temp_dir:
    pdf_path = os.path.join(temp_dir, PDF_FILENAME)
    
    # 4. Download the PDF from the URL
    download_pdf_from_url(PDF_URL, pdf_path)
    
    # 5. Upload the PDF to the RAG Corpus (for Vector Search)
    upload_pdf_to_corpus(
        corpus_name=corpus.name,
        pdf_path=pdf_path,
        display_name=PDF_FILENAME,
        description="Alphabet's 10-K 2024 document"
    )

    # 6. Upload the PDF to the GCS Bucket (for file storage)
    upload_to_gcs(source_bucket_name, pdf_path, PDF_FILENAME)
  
  # List all files in the corpus
  list_corpus_files(corpus_name=corpus.name)

if __name__ == "__main__":
  main()