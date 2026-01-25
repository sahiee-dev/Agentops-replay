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
