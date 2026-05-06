"""
backend/app/api/v1/router.py — TRD §4.3 canonical router.

Exposes exactly 3 endpoints:
  GET  /health                       — health.py
  POST /v1/ingest                    — ingestion.py
  GET  /v1/sessions/{id}/export      — sessions.py
"""

from fastapi import APIRouter

try:
    from backend.app.api.v1.endpoints.health import router as health_router
    from backend.app.api.v1.endpoints.ingestion import router as ingestion_router
    from backend.app.api.v1.endpoints.sessions import router as sessions_router
except ImportError:
    from app.api.v1.endpoints.health import router as health_router
    from app.api.v1.endpoints.ingestion import router as ingestion_router
    from app.api.v1.endpoints.sessions import router as sessions_router

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(ingestion_router, prefix="/v1/ingest", tags=["ingestion"])
router.include_router(sessions_router, tags=["sessions"])
