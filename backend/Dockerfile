# ============================================================
# AgentOps Replay - Backend Dockerfile
# ============================================================
# Multi-stage build for production-grade FastAPI service.
# Python 3.11 is the canonical version (see CONTRIBUTING.md).
#
# Build context is repository root (for verifier access).
# ============================================================

FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt


# ============================================================
# Production Stage
# ============================================================
FROM python:3.11-slim-bookworm AS production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Ensure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code from backend/
COPY backend/ .

# Copy verifier module (required by ingestion service)
COPY verifier/ /app/verifier/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
# Workers set to 1 for append-only consistency; scale horizontally via replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
