"""
export.py - Export API endpoints for JSON and PDF compliance artifacts.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.orm import Session as DBSession
import json

from app.database import get_db
from app.compliance import generate_json_export, generate_pdf_export

router = APIRouter()


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = "json",
    db: DBSession = Depends(get_db)
):
    """
    Export a session as a downloadable JSON or PDF artifact.
    
    Parameters:
        session_id (str): Session UUID to export.
        format (str): Export format, either "json" or "pdf". Defaults to "json".
        
    Returns:
        Response: A FastAPI Response containing either:
            - JSON content (pretty-printed) with media type "application/json" and
              filename "session_{session_id}_export.json", or
            - PDF bytes with media type "application/pdf" and
              filename "session_{session_id}_compliance.pdf".
    
    Raises:
        HTTPException: 400 if `format` is invalid; 404 if the session is not found;
                       500 for other export errors.
    """
    try:
        if format == "json":
            export_data = generate_json_export(session_id, db)
            return Response(
                content=json.dumps(export_data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="session_{session_id}_export.json"'
                }
            )
        
        elif format == "pdf":
            pdf_bytes = generate_pdf_export(session_id, db)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="session_{session_id}_compliance.pdf"'
                }
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Invalid format: {format}. Must be 'json' or 'pdf'")
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")