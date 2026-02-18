"""
agentops_ingest/api.py - HTTP Ingress Layer

Trust Boundary #1.

Responsibilities:
- Owns HTTP lifecycle
- Zero business logic
- Parse JSON
- Enforce content-type
- Enforce size limits
- Route to validator

If this layer crashes, nothing is written.
"""
import json
from typing import Dict, Any, List, Union

from flask import Flask, request, jsonify, Response

from .validator import validate_claim, ValidatedClaim
from .sealer import seal_event, SealedEvent
from .store import EventStore
from .errors import (
    IngestException,
    IngestError,
    ErrorClassification,
    accepted,
    schema_invalid,
)


# Configuration
MAX_PAYLOAD_SIZE = 1 * 1024 * 1024  # 1MB
MAX_BATCH_SIZE = 100


def create_app(database_url: str) -> Flask:
    """
    Create and configure the Flask application used by the ingestion service.
    
    The application enforces a maximum request payload size, requires POST requests to use
    Content-Type starting with "application/json", and registers the ingestion and export
    HTTP routes used by the service:
    
    - POST /v1/ingest/events: accepts a single event (object) or a batch (array) of events,
      enforces a maximum batch size, processes each event through the ingestion pipeline,
      and returns 201 on full success or 400 when a hard rejection occurs.
    - GET /v1/sessions/<session_id>/export: returns sealed session events or 404 if none found.
    - GET /health: returns service health status.
    
    Parameters:
        database_url (str): Database connection URL used to initialize the EventStore.
    
    Returns:
        app (Flask): Configured Flask application instance for the ingestion service.
    """
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_PAYLOAD_SIZE
    
    # Initialize store
    store = EventStore(database_url)
    
    @app.before_request
    def enforce_content_type():
        """
        Enforces that POST requests have a Content-Type header of "application/json".
        
        If the current request is a POST and the Content-Type header is missing or does not start with "application/json", returns a 400 JSON error response with fields:
        - error_code: "INGEST_CONTENT_TYPE_INVALID"
        - classification: "HARD_REJECT"
        - message: "Content-Type must be application/json"
        - details: {"received": <received content type>}
        
        Returns:
            response_or_none: A Flask JSON response tuple with status 400 when the Content-Type is invalid, `None` otherwise.
        """
        if request.method == 'POST':
            # Accept application/json with or without charset parameter
            if not request.content_type or not request.content_type.startswith('application/json'):
                return jsonify({
                    "error_code": "INGEST_CONTENT_TYPE_INVALID",
                    "classification": "HARD_REJECT",
                    "message": "Content-Type must be application/json",
                    "details": {"received": request.content_type}
                }), 400
    
    @app.route('/v1/ingest/events', methods=['POST'])
    def ingest_events():
        """
        Handle POST /v1/ingest/events by accepting a single event object or a batch of events, processing each through the ingestion pipeline, and returning per-event results.
        
        Processes each event in order and stops further processing on the first event that yields a HARD_REJECT classification. Enforces a maximum batch size of MAX_BATCH_SIZE and expects a JSON object or array as the request body.
        
        Returns:
            A JSON response containing a `results` list with one result object per processed event.
            - If all events are accepted: responds with status 201 and the `results` list of accepted entries.
            - If the request JSON is invalid, the body is neither object nor array, the batch exceeds MAX_BATCH_SIZE, or any event yields a HARD_REJECT: responds with status 400 and `results` (if applicable) or an error object with `error_code`, `classification`, `message`, and `details` fields. 
        """
        try:
            data = request.get_json(force=True)
        except Exception as e:
            return jsonify({
                "error_code": "INGEST_JSON_INVALID",
                "classification": "HARD_REJECT",
                "message": "Invalid JSON",
                "details": {"error": str(e)}
            }), 400
        
        # Normalize to list
        if isinstance(data, dict):
            events = [data]
        elif isinstance(data, list):
            events = data
        else:
            return jsonify({
                "error_code": "INGEST_SCHEMA_INVALID",
                "classification": "HARD_REJECT",
                "message": "Request body must be object or array",
                "details": {}
            }), 400
        
        # Batch size limit
        if len(events) > MAX_BATCH_SIZE:
            return jsonify({
                "error_code": "INGEST_BATCH_TOO_LARGE",
                "classification": "HARD_REJECT",
                "message": f"Batch size exceeds limit of {MAX_BATCH_SIZE}",
                "details": {"received": len(events)}
            }), 400
        
        # Process each event
        results = []
        for raw_event in events:
            if not isinstance(raw_event, dict):
                 return jsonify({
                    "error_code": "INGEST_SCHEMA_INVALID",
                    "classification": "HARD_REJECT",
                    "message": "Each batch item must be an object",
                    "details": {"index": events.index(raw_event), "type": str(type(raw_event))}
                }), 400
            
            result = _process_single_event(store, raw_event)
            results.append(result)
            
            # Stop on first hard failure
            if result["classification"] == ErrorClassification.HARD_REJECT.value:
                return jsonify({"results": results}), 400
        
        # All accepted
        return jsonify({"results": results}), 201
    
    @app.route('/v1/sessions/<session_id>/export', methods=['GET'])
    def export_session(session_id: str):
        """
        Export all sealed events for the given session.
        
        Parameters:
            session_id (str): Identifier of the session to export.
        
        Returns:
            tuple: A Flask JSON response and status code. On success, returns the session's sealed events as JSON with HTTP 200. If no events are found, returns an error object with `error_code` "SESSION_NOT_FOUND", a `message`, `details` containing the `session_id`, and HTTP 404.
        """
        from .export import export_session as do_export
        events = do_export(store, session_id)
        
        if not events:
            return jsonify({
                "error_code": "SESSION_NOT_FOUND",
                "message": "No events found for session",
                "details": {"session_id": session_id}
            }), 404
        
        return jsonify(events), 200
    
    @app.route('/health', methods=['GET'])
    def health():
        """
        Return a simple health check response.
        
        Returns:
            A JSON response body `{"status": "ok"}` paired with HTTP status code `200`.
        """
        return jsonify({"status": "ok"}), 200
    
    return app


def _process_single_event(store: EventStore, raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single raw event through validation, sealing, and persistence.
    
    The function returns a result dictionary describing either a successful acceptance or a structured error. If validation, sealing, or storage succeeds the result represents an accepted event (including event identifiers); if an IngestException occurs the embedded error is returned; if an unexpected exception occurs a generic `INGEST_INTERNAL_ERROR` with `HARD_REJECT` classification is returned. The function itself does not raise exceptions to the caller.
    
    Returns:
        dict: A result dictionary. On success contains acceptance fields (e.g. event identifiers and classification). On failure contains error fields: `error_code`, `classification`, `message`, and `details`.
    """
    try:
        # 1. Validate
        claim = validate_claim(raw_event)
        
        # 2. Get chain state
        chain_state = store.get_chain_state(claim.session_id)
        
        # 3. Seal
        sealed = seal_event(claim, chain_state, strict_mode=True)
        
        # 4. Store
        store.insert(sealed)
        
        # 5. Success
        result = accepted(sealed.event_id, sealed.event_hash)
        return result.to_dict()
        
    except IngestException as e:
        return e.error.to_dict()
    except Exception as e:
        # Log full exception server-side (import logging at top if needed)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected ingestion error: {e}", exc_info=True)
        
        # Return generic error to client
        return {
            "error_code": "INGEST_INTERNAL_ERROR",
            "classification": ErrorClassification.HARD_REJECT.value,
            "message": "Internal error",
            "details": {}
        }


def run_server(database_url: str, host: str = "0.0.0.0", port: int = 8080):
    """
    Start the HTTP ingestion Flask server configured with the provided database URL.
    
    Parameters:
        database_url (str): Connection URL used to initialize the EventStore for the app.
        host (str): Host interface to bind the server to.
        port (int): TCP port to listen on.
    """
    app = create_app(database_url)
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    import os
    db_url = os.environ.get("DATABASE_URL", "sqlite:///agentops_ingest.db")
    run_server(db_url)