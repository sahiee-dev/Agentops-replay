"""
ingestion.py - Ingestion API endpoints.

ENDPOINT: POST /v1/ingest
PURPOSE: Receive event batches from SDK, establish server authority.

RESPONSE CODES:
- 201 Created: Batch accepted
- 409 Conflict: State conflict (sealed, sequence issues)
- 400 Bad Request: Invalid input (malformed, invalid seal request)
- 500 Internal Server Error: DB failure
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

try:
    from backend.app.db.session import get_db
    from backend.app.schemas.ingestion import (
        IngestBatchRequest,
        IngestionResult,
        RejectionResponse,
    )
    from backend.app.services.ingestion.service import (
        BadRequestError,
        IngestionService,
        StateConflictError,
    )
except ImportError:
    try:
        from app.db.session import get_db
        from app.schemas.ingestion import (
            IngestBatchRequest,
            IngestionResult,
            RejectionResponse,
        )
        from app.services.ingestion.service import (
            BadRequestError,
            IngestionService,
            StateConflictError,
        )
    except ImportError:
        # Service not yet implemented — endpoint will return 503 until it is
        get_db = None
        IngestBatchRequest = None
        IngestionResult = None
        RejectionResponse = None
        BadRequestError = Exception
        StateConflictError = Exception

        class IngestionService:  # type: ignore[no-redef]
            pass

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest event batch",
    description="""
Ingest a batch of events into a session.

**Authority:** All ingested events are stamped with SERVER authority.

**Invariants:**
- Session must exist and not be sealed
- Sequence must be strictly monotonic and continuous
- `seal=true` requires SESSION_END as last event
- All writes are atomic (full batch or nothing)
""",
)
async def ingest_batch(request: dict) -> dict:
    """
    Ingest a batch of events.

    This endpoint establishes SERVER authority for all events.
    SDK-provided hashes are logged but never trusted.
    """
    if IngestionService is None or get_db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "code": "SERVICE_UNAVAILABLE",
                    "message": "Ingestion service not yet implemented"},
        )
    """
    Ingest a batch of events.

    This endpoint establishes SERVER authority for all events.
    SDK-provided hashes are logged but never trusted.
    """
    try:
        service = IngestionService(db)

        # Convert Pydantic models to dicts for service
        events = [event.model_dump() for event in request.events]

        result = service.ingest_batch(
            session_id_str=request.session_id, events=events, seal=request.seal
        )

        # Commit transaction
        db.commit()

        return IngestionResult(
            status="success",
            accepted_count=result.accepted_count,
            final_hash=result.final_hash,
            chain_authority="SERVER",
            sealed=result.sealed,
            seal_timestamp=result.seal_timestamp,
            session_digest=result.session_digest,
            evidence_class=result.evidence_class,
        )

    except StateConflictError as e:
        db.rollback()
        logger.warning("Ingestion conflict: %s - %s", e.code, e.message)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": "rejected",
                "code": e.code,
                "message": e.message,
                "details": e.details,
            },
        )

    except BadRequestError as e:
        db.rollback()
        logger.warning("Ingestion bad request: %s - %s", e.code, e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "rejected",
                "code": e.code,
                "message": e.message,
                "details": e.details,
            },
        )

    except Exception as e:
        db.rollback()
        logger.exception("Ingestion internal error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "Internal server error during ingestion",
            },
        )
