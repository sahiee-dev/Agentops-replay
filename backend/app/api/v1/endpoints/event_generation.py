from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.session import Session as SessionModel
from app.services.event_generator import EventGeneratorService

router = APIRouter()

class EventGenerationRequest(BaseModel):
    session_id: int
    scenario_type: str

class EventGenerationResponse(BaseModel):
    message: str
    events_created: int
    session_id: int
    scenario_type: str

@router.post("/generate", response_model=EventGenerationResponse)
def generate_events(
    request: EventGenerationRequest,
    db: Session = Depends(get_db)
):
    """Generate realistic events for a session based on scenario type"""

    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Initialize event generator
    generator = EventGeneratorService(db)

    try:
        # Generate events based on scenario type
        events = generator.generate_scenario(request.session_id, request.scenario_type)

        return EventGenerationResponse(
            message=f"Successfully generated {len(events)} events for {request.scenario_type} scenario",
            events_created=len(events),
            session_id=request.session_id,
            scenario_type=request.scenario_type
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating events: {e!s}")

@router.get("/scenarios")
def get_available_scenarios():
    """Get list of available event generation scenarios"""
    return {
        "scenarios": [
            {
                "type": "customer_support",
                "name": "Customer Support Agent",
                "description": "Chat-based customer service workflow with knowledge base lookup",
                "events_count": 7
            },
            {
                "type": "data_analysis",
                "name": "Data Analysis Agent",
                "description": "End-to-end data processing and analysis workflow",
                "events_count": 9
            },
            {
                "type": "voice_agent",
                "name": "Voice Call Agent",
                "description": "Phone-based interaction with speech processing",
                "events_count": 9
            },
            {
                "type": "complex_workflow",
                "name": "Complex Workflow (with violations)",
                "description": "Multi-step process with policy violations for compliance testing",
                "events_count": 9
            }
        ]
    }
