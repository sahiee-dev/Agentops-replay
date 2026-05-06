def validate_event_structure(event: dict) -> list[str]:
    """
    Validate required fields are present in an event dict.
    Returns list of error strings. Empty list = valid.
    Required fields: seq, event_type, session_id, timestamp,
                     payload, prev_hash, event_hash
    """
    errors = []
    required = ["seq", "event_type", "session_id", "timestamp",
                "payload", "prev_hash", "event_hash"]
    for field in required:
        if field not in event:
            errors.append(f"Missing required field: {field}")
    return errors
