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

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -m appuser

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder to user's local bin
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Ensure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code from backend/
COPY --chown=appuser:appuser backend/ .

# Copy verifier module (required by ingestion service)
COPY --chown=appuser:appuser verifier/ /app/verifier/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
# Workers set to 1 for append-only consistency; scale horizontally via replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
