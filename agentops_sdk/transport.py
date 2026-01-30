"""
HTTP transport layer for SDK remote mode with retry logic.

CONSTITUTIONAL REQUIREMENTS:
- Exponential backoff (5 retries max)
- Deterministic LOG_DROP on persistent failure
- Fail-open semantics (SDK continues running)
"""

import time
from typing import Any

import httpx


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, message=None, *, error_class=None, attempts=None, last_error=None):
        super().__init__(message or "Retry attempts exhausted")
        self.error_class = error_class
        self.attempts = attempts
        self.last_error = last_error


def send_batch_with_retry(
    http_client: httpx.Client,
    session_id: str,
    events: list[dict[str, Any]],
    max_retries: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 10.0
) -> dict[str, Any]:
    """
    Send event batch to server with exponential backoff.
    
    CONSTITUTIONAL GUARANTEES:
    - Retries up to max_retries times
    - Exponential backoff between attempts
    - Returns error details on persistent failure
    
    Args:
        http_client: HTTP client instance
        session_id: Session UUID
        events: List of events to send
        max_retries: Maximum retry attempts
        min_wait: Minimum wait between retries (seconds)
        max_wait: Maximum wait between retries (seconds)
        
    Returns:
        Response dict with 'status', 'accepted_count', 'final_hash'
        
    Raises:
        RetryExhausted: After all retries are exhausted
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
            if 400 <= e.response.status_code < 500:
                # Client errors (4xx) - don't retry, convert to RetryExhausted for fail-open
                error_class = "CLIENT_ERROR"
                try:
                    error_body = e.response.json()
                    error_msg = error_body.get("detail", str(e))
                except Exception:
                    error_msg = str(e)

                last_error = f"HTTP {e.response.status_code}: {error_msg}"
                raise RetryExhausted(
                    f"Client error (4xx) - {last_error}",
                    error_class=error_class,
                    attempts=attempt + 1,
                    last_error=last_error
                ) from e
            else: # 5xx errors
                # Server errors (5xx) - will retry
                error_class = "SERVER_ERROR"
                last_error = f"HTTP {e.response.status_code}"

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
        f"Failed after {max_retries} attempts. Last error: {error_class} - {last_error}",
        error_class=error_class,
        attempts=attempt,
        last_error=last_error
    )
