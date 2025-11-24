import gradio as gr
import json
import uuid
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines

# --- NEW IMPORTS FOR VERTEX AI ---
import vertexai
from vertexai import agent_engines

# --- CONFIGURATION & SETUP ---
# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
AGENT_ENGINE_ID = os.getenv("AGENT_ENGINE_ID")

if not AGENT_ENGINE_ID:
    print("WARNING: AGENT_ENGINE_ID not found in .env. Make sure you ran the deployment script.")

# Initialize Vertex AI SDK
vertexai.init(project=PROJECT_ID, location=LOCATION)

# --- UPDATED: HTML_CONTENT with new highlight colors for feature cards ---
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RAG AI Agent Prototye</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
/* Hide scrollbar */
::-webkit-scrollbar {
    width: 0px;
    background: transparent;
}
#chat-container {
    transition: all 0.3s ease;
}
body {
    font-family: 'Poppins', sans-serif;
}

/* Chat bubble pulse animation (dark gray) */
#chat-bubble {
    transition: all 0.3s ease;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(17, 24, 39, 0.7); }
    70% { box-shadow: 0 0 0 12px rgba(17, 24, 39, 0); }
    100% { box-shadow: 0 0 0 0 rgba(17, 24, 39, 0); }
}

/* Animated Logo Keyframes */
@keyframes pulse-glow {
    0%, 100% {
        opacity: 0.7;
        transform: scale(1);
    }
    50% {
        opacity: 1;
        transform: scale(1.1);
    }
}
.aiva-logo-animate {
    animation: pulse-glow 2.5s infinite ease-in-out;
}

/* Contact Modal Styles */
#contact-modal {
    transition: opacity 0.3s ease, visibility 0.3s ease;
}
</style>
</head>
<body class="bg-gray-50 text-gray-900 h-screen overflow-hidden flex flex-col">

<div id="contact-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100] invisible opacity-0">
    <div class="bg-white p-8 rounded-lg shadow-xl max-w-sm w-full text-center">
        <h2 class="text-2xl font-bold mb-4">Contact Us</h2>
        <p class="text-gray-700">For feedback and inquiries, please email us at:</p>
        <a href="mailto:PlaceYourEmailHere@---.com" class="text-blue-600 font-medium text-lg">PlaceYourEmailHere@gmail.com</a>
        <button id="close-modal" class="mt-6 bg-gray-900 text-white px-6 py-2 rounded-full font-semibold w-full hover:bg-gray-700 transition">
            Close
        </button>
    </div>
</div>

<header class="w-full p-6 px-4 md:px-10 flex-shrink-0">
    <nav class="flex justify-between items-center max-w-7xl mx-auto">
        <div class="flex items-center gap-3">
            <span class="text-3xl font-bold text-gray-900">RAG AI Agent</span>
        </div>

        <button id="contact-us-btn" class="bg-gray-900 text-white px-6 py-3 rounded-full font-semibold hover:bg-gray-700 transition">
            Contact Us
        </button>
    </nav>
</header>

<main class="flex-grow w-full max-w-7xl mx-auto px-6 py-4 flex flex-col justify-center gap-6 md:gap-10">

    <div class="w-full grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
        <div>
            <h1 class="text-5xl font-extrabold text-gray-900 leading-tight">
                <span class="bg-cyan-100 px-2 rounded-md inline-block">Replace your Website/Portal</span>
                <br>
                <span class="bg-cyan-100 px-2 rounded-md inline-block mt-2">Here</span>
            </h1>
            <p class="mt-4 text-base text-gray-600 max-w-xl">
                 [Summary] - Retrieval Augmented Generation (RAG) AI Agent prototype features a decoupled architecture with a dedicated GCP Vertex Agent Engine, GCP Vertex RAG Corpus backend, a custom web frontend with ChatBot UI, and an automated event-driven pipeline for document ingestion from GCS to Vertex RAG Corpus.
            </p>
        </div>

        <div class="flex items-center justify-center">
            <svg class="w-64 h-64 text-blue-600 aiva-logo-animate" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2z" stroke="currentColor" stroke-width="1.5" stroke-opacity="0.3"/>
                <path d="M12 4.04c-4.4 0-8 3.56-8 7.96 0 4.4 3.6 7.96 8 7.96s8-3.56 8-7.96c0-4.4-3.6-7.96-8-7.96z" stroke="currentColor" stroke-width="1.5" stroke-opacity="0.6"/>
                <path d="M15.899 12c0-2.154-1.746-3.899-3.899-3.899S8.1 9.846 8.1 12s1.746 3.899 3.899 3.899 3.899-1.745 3.899-3.899z" stroke="currentColor" stroke-width="1.5"/>
            </svg>
        </div>
    </div>

    <div class="w-full grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-blue-100 p-6 rounded-2xl shadow-sm">
            <h2 class="text-xl font-bold text-gray-900">RAG AI Agent prototype is Portable & Pluggable</h2>
        </div>
        <div class="bg-cyan-100 p-6 rounded-2xl shadow-sm">
            <h2 class="text-xl font-bold text-gray-900">RAG AI Agent prototype Works for most platforms</h2>
        </div>
        <div class="bg-purple-100 p-6 rounded-2xl shadow-sm">
            <h2 class="text-xl font-bold text-gray-900">RAG AI Agent prototype pretty quick to deploy</h2>
        </div>
    </div>
</main>

<div id="chat-bubble" class="fixed bottom-8 right-8 w-16 h-16 bg-gray-900 rounded-full flex items-center justify-center cursor-pointer shadow-lg z-50">
    <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
</div>

<div id="chat-container" class="hidden fixed bottom-28 right-8 w-full max-w-md h-3/4 max-h-[600px] bg-white rounded-3xl shadow-xl z-50 flex flex-col">
    <div class="flex justify-between items-center p-4 bg-gray-900 text-white rounded-t-3xl">
        <h3 class="text-lg font-semibold">RAG AI Agent</h3>
        <button id="close-chat" class="text-white hover:text-gray-200">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
        </button>
    </div>
    <iframe 
        src="/chatbot" 
        width="100%" 
        height="100%" 
        frameborder="0" 
        class="flex-grow rounded-b-3xl"
        title="Embedded Gradio Chatbot"
    ></iframe>
</div>

<script>
    // Chat Toggle Script
    const chatBubble = document.getElementById('chat-bubble');
    const chatContainer = document.getElementById('chat-container');
    const closeChat = document.getElementById('close-chat');

    chatBubble.addEventListener('click', () => {
        chatContainer.classList.remove('hidden');
        chatBubble.classList.add('hidden');
    });

    closeChat.addEventListener('click', () => {
        chatContainer.classList.add('hidden');
        chatBubble.classList.remove('hidden');
    });

    // Contact Modal Script
    const contactBtn = document.getElementById('contact-us-btn');
    const modal = document.getElementById('contact-modal');
    const closeModalBtn = document.getElementById('close-modal');

    function toggleModal() {
        modal.classList.toggle('invisible');
        modal.classList.toggle('opacity-0');
    }

    contactBtn.addEventListener('click', toggleModal);
    closeModalBtn.addEventListener('click', toggleModal);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            toggleModal();
        }
    });
</script>

</body>
</html>
"""

# --- BACKEND AGENT LOGIC (Vertex AI SDK) ---
def stream_from_agent_engine(prompt: str):
    """
    Connects to the Deployed Vertex AI Agent Engine and yields chunks of text.
    """
    if not AGENT_ENGINE_ID:
        yield "Error: AGENT_ENGINE_ID is missing. Check your .env file or deployment."
        return

    try:
        # 1. Get the Remote Agent Object
        agent_engine = agent_engines.get(AGENT_ENGINE_ID)
        
        # 2. Generate a unique user session ID (or use a fixed one for demo)
        user_session_id = f"gradio-user-{uuid.uuid4()}"

        # 3. Stream the query to Vertex AI
        response_stream = agent_engine.stream_query(
            user_id=user_session_id,
            message=prompt
        )

        # 4. Parse the event stream from Vertex
        for event in response_stream:
            # The event object structure depends on the reasoning engine
            # We look for 'content' -> 'parts' -> 'text'
            if "content" in event and "parts" in event["content"]:
                for part in event["content"]["parts"]:
                    if "text" in part:
                        yield part["text"]
                        
    except Exception as e:
        print(f"Vertex AI Agent Error: {e}")
        yield f"Error communicating with Vertex AI: {str(e)}"

def predict(message, history):
    """
    Gradio event handler function.
    """
    history = history or []
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": ""})
    yield history

    response_content = ""
    
    # Stream from the Cloud Agent
    for chunk in stream_from_agent_engine(message):
        response_content += chunk
        history[-1] = {"role": "assistant", "content": response_content}
        yield history
        
    # Final check if empty response
    if not response_content:
        history[-1] = {"role": "assistant", "content": "No response received from the agent."}
        yield history


# --- Build the Gradio UI ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="purple"), css="#chatbot { min-height: 400px; }") as demo:
    chatbot = gr.Chatbot(elem_id="chatbot", type='messages')
    with gr.Row():
        txt = gr.Textbox(
            show_label=False,
            placeholder="Ask your question here...",
            container=False,
            scale=7
        )
        btn = gr.Button("Send", scale=1)

    txt.submit(predict, [txt, chatbot], [chatbot])
    btn.click(predict, [txt, chatbot], [chatbot])
    txt.submit(lambda: "", None, [txt])
    btn.click(lambda: "", None, [txt])


# --- Create FastAPI app, add HTML route, and mount Gradio app ---
main_app = FastAPI()

@main_app.get("/", response_class=HTMLResponse)
async def serve_custom_html():
    """Serves the custom HTML page."""
    return HTML_CONTENT

# Mount the Gradio app onto the FastAPI app at the /chatbot path
app = gr.mount_gradio_app(main_app, demo, path="/chatbot")


# --- Run the combined app with Uvicorn ---
if __name__ == "__main__":
    print(f"Launching app connected to Vertex AI Agent Engine: {AGENT_ENGINE_ID}")
    print("Access at http://127.0.0.1:7860/")
    uvicorn.run(app, host="127.0.0.1", port=7860)