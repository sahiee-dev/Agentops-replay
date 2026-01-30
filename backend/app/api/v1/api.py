from fastapi import APIRouter  # type: ignore

from app.api.v1.endpoints import (
    compliance,
    events,
    ingestion_sessions,
    live_agent,
    replay,
    sessions,
    verify,
)
from app.api.v1.endpoints import export as export_endpoints
from app.api.v1.endpoints import ingestion as batch_ingestion

# Import event_generation only if the file exists
try:
    from app.api.v1.endpoints import event_generation
    HAS_EVENT_GENERATION = True
except ImportError:
    HAS_EVENT_GENERATION = False

# Create the main API router
router = APIRouter()

# Constitutional ingestion endpoints (Day 4)
router.include_router(ingestion_sessions.router, prefix="/ingest", tags=["ingestion"])
router.include_router(batch_ingestion.router, prefix="/ingest/batch", tags=["ingestion"])
router.include_router(verify.router, prefix="/verify", tags=["verification"])
router.include_router(export_endpoints.router, prefix="/export", tags=["export"])

# Legacy endpoints
router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
router.include_router(events.router, prefix="/events", tags=["events"])
router.include_router(replay.router, prefix="/replay", tags=["replay"])
router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
router.include_router(live_agent.router, prefix="/live-agent", tags=["live-agent"])

# Include event generation if available
if HAS_EVENT_GENERATION:
    router.include_router(event_generation.router, prefix="/event-generation", tags=["event-generation"])

