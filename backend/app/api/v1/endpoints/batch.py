"""
batch.py - Async batch ingestion endpoint.

Accepts event batches, pushes to Redis Stream (WAL), returns 202 Accepted.
Schema validation happens here (reject malformed at the gate).
Hash computation and DB persistence happen in the Worker.

CONSTITUTIONAL:
- No server authority artifacts emitted here (that's the worker/IngestService)
- Pydantic validation rejects invalid input before it reaches Redis
- batch_id provides traceability from API → Redis → Worker
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from app.schemas.ingestion import IngestBatchRequest

router = APIRouter()
logger = logging.getLogger(__name__)


class BatchAcceptedResponse:
    """Response model for accepted batches."""

    def __init__(self, batch_id: str, accepted_count: int) -> None:
        self.batch_id = batch_id
        self.accepted_count = accepted_count


@router.post(
    "/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Async batch ingestion via Redis WAL",
)
def ingest_batch(request: IngestBatchRequest):
    """
    Accept a batch of events for async processing.

    Events are pushed to Redis Stream and processed by the Worker.
    Returns 202 Accepted immediately — processing is asynchronous.

    The Worker will:
    1. Validate sequence continuity
    2. Recompute hashes server-side
    3. Persist to the immutable event store
    4. Seal if requested and valid
    """
    # Late import to avoid circular dependency at module load time
    from app.core.redis import STREAM_NAME, get_redis_client

    batch_id = str(uuid.uuid4())

    # Serialize batch for Redis Stream
    # IngestBatchRequest already validated by Pydantic at this point
    batch_payload = {
        "batch_id": batch_id,
        "session_id": request.session_id,
        "seal": str(request.seal),
        "events": json.dumps(
            [event.model_dump(mode="json") for event in request.events]
        ),
    }

    try:
        redis_client = get_redis_client()
        message_id = redis_client.xadd(STREAM_NAME, batch_payload)
        logger.info(
            "Batch %s accepted: %d events → Redis message %s",
            batch_id,
            len(request.events),
            message_id,
        )
    except Exception:
        logger.exception("Failed to push batch %s to Redis", batch_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion queue unavailable. Retry later.",
        )

    return {
        "status": "accepted",
        "batch_id": batch_id,
        "accepted_count": len(request.events),
    }
