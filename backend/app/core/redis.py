"""
redis.py - Redis client for async ingestion pipeline.

Provides connection to Redis Streams used as a Write-Ahead Log (WAL)
between the API (producer) and the Worker (consumer).

CONSTITUTIONAL JUSTIFICATION:
Redis is the durability layer between event receipt and DB persistence.
Events survive Redis restart via AOF persistence (configured in docker-compose).
"""

import logging
from functools import lru_cache

import redis

from app.config import settings

logger = logging.getLogger(__name__)

# Stream and consumer group constants
STREAM_NAME = "agentops:events:ingest"
DLQ_STREAM_NAME = "agentops:events:dlq"
CONSUMER_GROUP = "ingestion-workers"
MAX_RETRIES = 3


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """
    Get singleton Redis client.

    Returns:
        redis.Redis: Connected Redis client.

    Raises:
        redis.ConnectionError: If Redis is unreachable.
    """
    client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    # Verify connection on first use
    client.ping()
    logger.info("Redis client connected to %s", settings.REDIS_URL)
    return client


def ensure_consumer_group(client: redis.Redis) -> None:
    """
    Create consumer group if it doesn't exist.

    Idempotent — safe to call on every worker startup.
    """
    try:
        client.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        logger.info(
            "Created consumer group '%s' on stream '%s'",
            CONSUMER_GROUP,
            STREAM_NAME,
        )
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            # Group already exists — expected on restart
            logger.debug("Consumer group '%s' already exists", CONSUMER_GROUP)
        else:
            raise
