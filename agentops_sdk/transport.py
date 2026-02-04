"""
agentops_sdk/transport.py - HTTP Transport Utilities
"""
import time
import random
import httpx

class RetryExhausted(Exception):
    """Raised when all retry attempts fail."""
    pass

def send_batch_with_retry(
    client: httpx.Client,
    session_id: str,
    events: list,
    max_retries: int,
    min_wait: float,
    max_wait: float,
) -> dict:
    """
    Send a batch of events with exponential backoff retry.
    """
    attempt = 0
    last_error = None
    
    if max_retries <= 0:
        raise ValueError(f"max_retries must be > 0 (got {max_retries})")
    
    while attempt < max_retries:
        try:
            response = client.post(
                f"/api/v1/ingest/sessions/{session_id}/events",
                json={"events": events}
            )
            response.raise_for_status()
            return response.json()
            
        except (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            # Check for non-transient 4xx errors
            if isinstance(e, httpx.HTTPStatusError):
                status = e.response.status_code
                # Allow retry for 408 (Request Timeout), 429 (Too Many Requests), or 5xx
                if 400 <= status < 500 and status not in [408, 429]:
                    last_error = e
                    break
            
            last_error = e
            attempt += 1
            
            if attempt >= max_retries:
                break
                
            # Exponential backoff with jitter
            wait = min(min_wait * (2 ** (attempt - 1)), max_wait)
            jitter = random.uniform(0, 0.1 * wait)
            time.sleep(wait + jitter)
            
    raise RetryExhausted(f"Failed after {max_retries} attempts: {last_error}")
