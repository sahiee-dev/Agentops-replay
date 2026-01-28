"""
pdf_export.py - Compliance-grade PDF export with verbatim disclaimer.

CRITICAL: Disc

laimer MUST be verbatim per PRD §8.7 - no paraphrasing allowed.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
from typing import Dict, Any
import uuid
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models import Session, EventChain, ChainSeal
from app.compliance.json_export import generate_json_export


# MANDATORY DISCLAIMER (VERBATIM - NO CHANGES ALLOWED)
EVIDENCE_DISCLAIMER = """EVIDENCE SUPPORT STATEMENT

This report provides cryptographic evidence to support audit and investigation activities. It does not certify compliance with any legal, regulatory, or contractual standard.

Evidence Class: {evidence_class}
Verification Status: {verification_status}
Export Date: {export_date}
Export Authority: {export_authority}"""


def generate_pdf_export(session_id: str, db: DBSession) -> bytes:
    """
    Generate compliance-grade PDF export.
    
    Sections:
    1. Executive Summary
    2. Session Timeline  
    3. Technical Verification Details
    4. MANDATORY Disclaimer (verbatim)
    5. Chain-of-Custody Statement
    
    Args:
        session_id: Session UUID string
        db: Database session
        
    Returns:
        PDF bytes
        
    Raises:
        ValueError: If session not found
    """
    # Get canonical export
    export_data = generate_json_export(session_id, db)
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#2a2a2a'),
        spaceAfter=10,
        spaceBefore=12
    )
    body_style = styles['BodyText']
    
    # Build PDF content
    story = []
    
    # --- 1. HEADER ---
    story.append(Paragraph("AgentOps Replay", title_style))
    story.append(Paragraph("Compliance Evidence Export", styles['Heading2']))
    story.append(Spacer(1, 0.2*inch))
    
    # --- 2. EXECUTIVE SUMMARY ---
    story.append(Paragraph("Executive Summary", heading_style))
    
    summary_text = f"""
    <b>Session ID:</b> {export_data['session_id']}<br/>
    <b>Evidence Class:</b> {export_data['evidence_class']}<br/>
    <b>Authority:</b> {export_data['chain_authority']}<br/>
    <b>Session Status:</b> {export_data['session_metadata']['status']}<br/>
    <b>Event Count:</b> {export_data['session_metadata']['event_count']}<br/>
    <b>Total Drops:</b> {export_data['session_metadata']['total_drops']}<br/>
    <b>Started:</b> {export_data['session_metadata']['started_at']}<br/>
    <b>Sealed:</b> {export_data['session_metadata']['sealed_at'] or 'Not sealed'}
    """
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 0.3*inch))
    
    # --- 3. SESSION TIMELINE ---
    story.append(Paragraph("Session Timeline", heading_style))
    
    # Create event timeline table
    timeline_data = [["Seq", "Event Type", "Timestamp"]]
    for event in export_data['events'][:20]:  # Limit to first 20 for PDF
        timeline_data.append([
            str(event['sequence_number']),
            event['event_type'],
            event['timestamp_wall'][:19]  # Trim microseconds
        ])
    
    if len(export_data['events']) > 20:
        timeline_data.append(["...", f"({len(export_data['events']) - 20} more events)", "..."])
    
    timeline_table = Table(timeline_data)
    timeline_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(timeline_table)
    story.append(Spacer(1, 0.3*inch))
    
    # --- 4. TECHNICAL VERIFICATION DETAILS ---
    story.append(PageBreak())
    story.append(Paragraph("Technical Verification Details", heading_style))
    
    # Seal information
    seal_info = export_data.get('seal', {})
    if seal_info.get('present'):
        seal_text = f"""
        <b>CHAIN_SEAL Present:</b> Yes<br/>
        <b>Ingestion Service ID:</b> {seal_info.get('ingestion_service_id')}<br/>
        <b>Seal Timestamp:</b> {seal_info.get('seal_timestamp')}<br/>
        <b>Session Digest:</b> {seal_info.get('session_digest')[:16]}...<br/>
        <b>Final Event Hash:</b> {seal_info.get('final_event_hash')[:16]}...
        """
    else:
        seal_text = "<b>CHAIN_SEAL Present:</b> No (session not sealed)"
    
    story.append(Paragraph(seal_text, body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # --- 5. MANDATORY DISCLAIMER (VERBATIM) ---
    story.append(PageBreak())
    disclaimer_text = EVIDENCE_DISCLAIMER.format(
        evidence_class=export_data['evidence_class'],
        verification_status="VERIFIED" if export_data['evidence_class'] == "AUTHORITATIVE_EVIDENCE" else "PARTIAL",
        export_date=datetime.utcnow().isoformat() + "Z",
        export_authority=export_data['chain_of_custody']['export_authority'] or "AgentOps Replay System"
    )
    
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=body_style,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#333333'),
        borderWidth=1,
        borderColor=colors.black,
        borderPadding=10,
        backColor=colors.HexColor('#f5f5f5')
    )
    story.append(Paragraph(disclaimer_text.replace('\n', '<br/>'), disclaimer_style))
    story.append(Spacer(1, 0.3*inch))
    
    # --- 6. CHAIN-OF-CUSTODY STATEMENT ---
    story.append(Paragraph("Chain-of-Custody Statement", heading_style))
    
    custody_text = f"""
    This export was generated from the AgentOps Replay immutable event store using RFC 8785 (JCS) canonical JSON serialization.
    <br/><br/>
    <b>Export Authority:</b> {export_data['chain_of_custody']['export_authority']}<br/>
    <b>Export Timestamp:</b> {export_data['chain_of_custody']['export_timestamp']}<br/>
    <b>Canonical Format:</b> {export_data['chain_of_custody']['canonical_format']}<br/>
    <b>Session Authority:</b> {export_data['chain_authority']}<br/>
    <br/>
    All event hashes can be independently verified using the AgentOps Replay verifier tool.
    """
    story.append(Paragraph(custody_text, body_style))
    
    # Build PDF
    doc.build(story)
    
    # Return bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
