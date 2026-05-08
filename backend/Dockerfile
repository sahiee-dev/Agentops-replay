FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy verifier first — required by agentops_sdk and ingestion chain
COPY verifier/ /app/verifier/

# Copy SDK — required by backend services
COPY agentops_sdk/ /app/agentops_sdk/

# Copy backend application
COPY backend/ /app/backend/

# Install backend Python dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

ENV PYTHONPATH=/app:/app/backend

EXPOSE 8000
