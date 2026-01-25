"""
HTTP transport layer for SDK remote mode with retry logic.

CONSTITUTIONAL REQUIREMENTS:
- Exponential backoff (5 retries max)
- Deterministic LOG_DROP on persistent failure
- Fail-open semantics (SDK continues running)
"""

import time
import httpx
from typing import List, Dict, Any, Optional


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


def send_batch_with_retry(
    http_client: httpx.Client,
    session_id: str,
    events: List[Dict[str, Any]],
    max_retries: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 10.0
) -> Dict[str, Any]:
    """
    Send a batch of events to the ingest endpoint, retrying with exponential backoff on transient failures.
    
    Parameters:
        http_client (httpx.Client): HTTP client used to perform requests.
        session_id (str): Session UUID to include in the request path and payload.
        events (List[Dict[str, Any]]): List of event objects to send.
        max_retries (int): Maximum number of attempts before giving up.
        min_wait (float): Minimum backoff delay in seconds.
        max_wait (float): Maximum backoff delay in seconds.
    
    Returns:
        dict: Parsed JSON response from the server (e.g., contains keys like 'status', 'accepted_count', 'final_hash').
    
    Raises:
        RetryExhausted: If all retry attempts are exhausted without a successful response.
    """
    attempt = 0
    last_error = None
    error_class = "UNKNOWN_ERROR"
    
    while attempt < max_retries:
        try:
            response = http_client.post(
                f"/api/v1/ingest/sessions/{session_id}/events",
                json={"session_id": session_id, "events": events}
            )
            response.raise_for_status()
            return response.json()
        
        except httpx.TimeoutException as e:
            error_class = "TIMEOUT"
            last_error = str(e)
            
        except httpx.NetworkError as e:
            error_class = "NETWORK_FAILURE"
            last_error = str(e)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                error_class = "SERVER_ERROR"
                last_error = f"HTTP {e.response.status_code}"
            else:
                # 4xx errors are not retryable
                raise
        
        except Exception as e:
            error_class = "UNKNOWN_ERROR"
            last_error = str(e)
        
        # Exponential backoff
        attempt += 1
        if attempt < max_retries:
            wait_time = min(min_wait * (2 ** attempt), max_wait)
            print(f"⚠️  Retry {attempt}/{max_retries} after {wait_time:.1f}s... ({error_class})")
            time.sleep(wait_time)
    
    # All retries exhausted
    raise RetryExhausted(
        f"Failed after {max_retries} attempts. Last error: {error_class} - {last_error}"
    )