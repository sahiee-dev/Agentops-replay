from fastapi import APIRouter # type: ignore
from app.api.v1.endpoints import sessions, events, replay, compliance, live_agent
from app.api.v1.endpoints import sessions, events, replay, compliance

# Import event_generation only if the file exists
try:
    from app.api.v1.endpoints import event_generation
    HAS_EVENT_GENERATION = True
except ImportError:
    HAS_EVENT_GENERATION = False

# Create the main API router
router = APIRouter()

# Include all endpoint routers
router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
router.include_router(events.router, prefix="/events", tags=["events"])
router.include_router(replay.router, prefix="/replay", tags=["replay"])
router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
router.include_router(live_agent.router, prefix="/live-agent", tags=["live-agent"])

# Include event generation if available
if HAS_EVENT_GENERATION:
    router.include_router(event_generation.router, prefix="/event-generation", tags=["event-generation"])
