# Copyright 2025 Google LLC
import sys
import os
import logging
from dotenv import set_key

# --- PATH SETUP ---
# 1. Get the folder where THIS script lives (.../ai_agent/vertex_engine_deploy)
script_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Get the 'ai_agent' folder (Parent of this script)
ai_agent_dir = os.path.dirname(script_dir)

# 3. Get the Project Root (Grandparent: .../rag-prototype)
project_root = os.path.dirname(ai_agent_dir)

# 4. Add Project Root to Python path
# This allows us to do "from ai_agent.agent import ..."
sys.path.insert(0, project_root)
# ------------------

import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# --- IMPORT FIX: Import directly from ai_agent package ---
try:
    from ai_agent.agent import root_agent
    print(f"✅ Successfully imported root_agent from ai_agent")
except ImportError as e:
    print(f"❌ Error importing agent: {e}")
    print(f"   Ensure 'agent.py' exists in: {ai_agent_dir}")
    sys.exit(1)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
STAGING_BUCKET = os.getenv("STAGING_BUCKET")

# .env path (Inside rag-prototype)
ENV_FILE_PATH = os.path.join(project_root, ".env")

vertexai.init(
    project=GOOGLE_CLOUD_PROJECT,
    location=GOOGLE_CLOUD_LOCATION,
    staging_bucket=STAGING_BUCKET,
)

def update_env_file(agent_engine_id, env_file_path):
    """Updates the .env file with the agent engine ID."""
    try:
        set_key(env_file_path, "AGENT_ENGINE_ID", agent_engine_id)
        print(f"Updated AGENT_ENGINE_ID in {env_file_path} to {agent_engine_id}")
    except Exception as e:
        print(f"Error updating .env file: {e}")

logger.info("deploying app...")
app = AdkApp(
    agent=root_agent,
    enable_tracing=True,
)

logging.debug("deploying agent to agent engine:")

remote_app = agent_engines.create(
    app,
    requirements=[
        "google-cloud-aiplatform[adk,agent-engines]==1.108.0",
        "google-adk==1.10.0",
        "python-dotenv",
        "google-auth",
        "tqdm",
        "requests",
        "llama-index",
    ],
    # We upload the entire 'ai_agent' folder so the cloud can resolve imports
    extra_packages=[
        ai_agent_dir, 
    ],
)

logging.info(f"Deployed agent to Vertex AI Agent Engine successfully, resource name: {remote_app.resource_name}")

update_env_file(remote_app.resource_name, ENV_FILE_PATH)