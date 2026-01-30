"""
verify.py - Session verification API endpoint.

CONSTITUTIONAL REQUIREMENT: Verification operates on RFC 8785 canonical exports only.
"""

import logging
import os
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import EventChain, Session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/verify")
async def verify_session_api(session_id: str, db: DBSession = Depends(get_db)):
    """
    Verify session integrity using canonical export.

    CONSTITUTIONAL: Operates on RFC 8785 canonical form, NOT ORM objects.
    Stores verification result for later inspection.

    Returns:
        Evidence class, violations, replay fingerprint
    """
    try:
        # 1. Get session
        session = (
            db.query(Session)
            .filter(Session.session_id_str == uuid.UUID(session_id))
            .first()
        )

        if not session:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        # 2. Export to canonical form
        events = (
            db.query(EventChain)
            .filter(EventChain.session_id == session.id)
            .order_by(EventChain.sequence_number)
            .all()
        )

        if not events:
            raise HTTPException(status_code=400, detail="Cannot verify empty session")

        # 3. Convert    # Build canonical events list (MUST use payload_canonical, not payload_jsonb)
        canonical_events = []
        for event in events:
            canonical_event = {
                "event_id": str(event.event_id),  # Use event_id not id
                "session_id": str(session.session_id_str),  # Use session's UUID
                "sequence_number": event.sequence_number,
                "timestamp_wall": event.timestamp_wall.isoformat(),  # Serialize to string
                "timestamp_monotonic": event.timestamp_monotonic,
                "event_type": event.event_type,
                "source_sdk_ver": event.source_sdk_ver,
                "schema_ver": event.schema_ver,
                "payload": event.payload_canonical,  # AUTHORITATIVE: canonical text
                "payload_hash": event.payload_hash,
                "prev_event_hash": event.prev_event_hash,
                "event_hash": event.event_hash,
                "chain_authority": event.chain_authority,
            }
            canonical_events.append(canonical_event)

        # 4. Run verifier on canonical form
        policy = {"reject_local_authority": False}

        # Import verify_session from agentops_verify
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "../../../../verifier")
        )
        from agentops_verify import verify_session

        result = verify_session(canonical_events, policy)

        #  5. Update session evidence class
        session.evidence_class = result.get("evidence_class")
        db.commit()

        # 6. Return verification result
        return {
            "session_id": session_id,
            "status": result.get("status"),
            "evidence_class": result.get("evidence_class"),
            "sealed": result.get("sealed"),
            "complete": result.get("complete"),
            "authority": result.get("authority"),
            "total_drops": result.get("total_drops", 0),
            "violations": result.get("violations", []),
            "replay_fingerprint": result.get("replay_fingerprint"),
            "event_count": result.get("event_count"),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # Log full exception server-side for debugging
        logger.exception("Verification error for session %s", session_id)
        raise HTTPException(
            status_code=500, detail="Internal server error during verification"
        )
