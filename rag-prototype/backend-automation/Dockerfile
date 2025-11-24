# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 8080
ENV PORT=8080
# This forces Python to print logs immediately instead of waiting
ENV PYTHONUNBUFFERED=True

# --- UPDATED ENTRYPOINT ---
ENTRYPOINT ["functions-framework", "--source", "app.py", "--target", "rag_ingestion_handler", "--signature-type", "cloudevent", "--port", "8080", "--host", "0.0.0.0"]