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
    Create the Flask application for the Ingestion Service.
    """
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_PAYLOAD_SIZE
    
    # Initialize store
    store = EventStore(database_url)
    
    @app.before_request
    def enforce_content_type():
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
        POST /v1/ingest/events
        
        Accepts single event or batch of events.
        Append-only. No update. No delete.
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
        GET /v1/sessions/<session_id>/export
        
        Read-only export of sealed session.
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
        return jsonify({"status": "ok"}), 200
    
    return app


def _process_single_event(store: EventStore, raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single event through the ingestion pipeline.
    
    Returns result dict (never raises to caller).
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
    Run the ingestion server.
    """
    app = create_app(database_url)
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    import os
    db_url = os.environ.get("DATABASE_URL", "sqlite:///agentops_ingest.db")
    run_server(db_url)
