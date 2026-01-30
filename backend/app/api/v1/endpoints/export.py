"""
export.py - Export API endpoints for JSON and PDF compliance artifacts.
"""

import logging
import os
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session as DBSession

# Add verifier to path for JCS
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../verifier'))
import jcs
from app.compliance import generate_json_export, generate_pdf_from_verified_dict
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = "json",
    db: DBSession = Depends(get_db)
):
    """
    Export session in JSON or PDF format.
    
    Args:
        session_id: Session UUID
        format: "json" or "pdf"
        db: Database session
        
    Returns:
        JSON or PDF export
    """
    try:
        if format == "json":
            export_data = generate_json_export(session_id, db)
            # Use RFC 8785 canonical JSON
            canonical_bytes = jcs.canonicalize(export_data)
            return Response(
                content=canonical_bytes,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="session_{session_id}_export.json"'
                }
            )

        elif format == "pdf":
            export_data = generate_json_export(session_id, db)
            pdf_bytes = generate_pdf_from_verified_dict(export_data)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="session_{session_id}_compliance.pdf"'
                }
            )

        else:
            raise HTTPException(status_code=400, detail=f"Invalid format: {format}. Must be 'json' or 'pdf'")

    except ValueError:
        # Invalid UUID or session not found
        try:
            uuid.UUID(session_id)
            # Valid UUID, session not found
            raise HTTPException(status_code=404, detail="Session not found")
        except ValueError:
            # Invalid UUID format
            raise HTTPException(status_code=400, detail="Invalid session ID")
    except Exception:
        # Log full exception server-side
        logger.exception("Export error for session %s format %s", session_id, format)
        raise HTTPException(status_code=500, detail="Internal server error")
