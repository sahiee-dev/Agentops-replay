"""
pdf_export.py - Compliance-grade PDF export from VERIFIED JSON.

CRITICAL CONSTRAINTS (per user review):
1. PDF is NOT a canonical artifact - JSON is the only verifiable artifact
2. PDF MUST consume a verified JSON file, not raw DB rows
3. PDF MUST explicitly state it is a rendering of a verified JSON export
4. All hashes are copied VERBATIM from JSON - no recomputation
5. Disclaimer MUST be verbatim per PRD §8.7
"""

import json
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# MANDATORY DISCLAIMER (VERBATIM - NO CHANGES ALLOWED)
EVIDENCE_DISCLAIMER = """EVIDENCE SUPPORT STATEMENT

This report is a RENDERING of a verified JSON export. It is not the primary evidence artifact.

The source JSON file is the only verifiable artifact. This PDF is provided as a human-readable aid only.

This export is provided as EVIDENCE ONLY. It is not:
• A certification of compliance
• A guarantee of agent correctness
• Legal or regulatory advice
• A complete record (if evidence class is PARTIAL)

Evidence Class: {evidence_class}
Verification Status: {verification_status}
Export Date: {export_date}
Export Authority: {export_authority}"""


def generate_pdf_from_verified_json(verified_json_path: str) -> bytes:
    """
    Generate compliance-grade PDF from a VERIFIED JSON export.
    
    CRITICAL: This function takes a path to a verified JSON file, NOT a session_id.
    The JSON must have already passed verification before being passed here.
    
    Structure (per user specification):
    1. Cover Page (Evidence Class, Verification Status, Session ID, Disclaimer)
    2. Executive Summary (Non-technical, no hashes)
    3. Event Timeline (Seq, Type, Timestamp; explicit LOG_DROP markers)
    4. Verification Annex (Hash chain, Session digest, CHAIN_SEAL, Verifier version)
    
    Args:
        verified_json_path: Absolute path to a verified JSON export file
        
    Returns:
        PDF bytes
        
    Raises:
        FileNotFoundError: If JSON file not found
        ValueError: If JSON is malformed
    """
    # Load verified JSON
    with open(verified_json_path, encoding='utf-8') as f:
        export_data = json.load(f)

    return _render_pdf(export_data)


def generate_pdf_from_verified_dict(export_data: dict[str, Any]) -> bytes:
    """
    Generate PDF from an already-loaded verified JSON dict.
    
    Use this when you have the verified data in memory.
    """
    return _render_pdf(export_data)


def _render_pdf(export_data: dict[str, Any]) -> bytes:
    """
    Internal: Render PDF from export data.
    """
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=6
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

    story = []

    # === 1. COVER PAGE ===
    story.append(Paragraph("AgentOps Replay", title_style))
    story.append(Paragraph("Evidence Export Report", styles['Heading2']))
    story.append(Spacer(1, 0.3*inch))

    # Cover page key info
    cover_data = [
        ["Evidence Class", export_data.get('evidence_class', 'UNKNOWN')],
        ["Verification Status", _get_verification_status(export_data)],
        ["Session ID", export_data.get('session_id', 'N/A')],
        ["Export Timestamp", export_data.get('export_timestamp', 'N/A')],
    ]
    cover_table = Table(cover_data, colWidths=[2*inch, 4*inch])
    cover_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e0e0')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 0.4*inch))

    # Disclaimer on cover page
    disclaimer_text = EVIDENCE_DISCLAIMER.format(
        evidence_class=export_data.get('evidence_class', 'UNKNOWN'),
        verification_status=_get_verification_status(export_data),
        export_date=export_data.get('export_timestamp', 'N/A'),
        export_authority=export_data.get('chain_of_custody', {}).get('export_authority') or "AgentOps Replay System"
    )

    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=body_style,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#333333'),
        borderWidth=1,
        borderColor=colors.black,
        borderPadding=10,
        backColor=colors.HexColor('#fff3cd')  # Warning yellow
    )
    story.append(Paragraph(disclaimer_text.replace('\n', '<br/>'), disclaimer_style))

    # === 2. EXECUTIVE SUMMARY (No hashes) ===
    story.append(PageBreak())
    story.append(Paragraph("Executive Summary", heading_style))

    session_meta = export_data.get('session_metadata', {})
    summary_text = f"""
    <b>Agent:</b> {session_meta.get('agent_name', 'Unknown')}<br/>
    <b>Session Started:</b> {session_meta.get('started_at', 'N/A')}<br/>
    <b>Session Sealed:</b> {session_meta.get('sealed_at') or 'Not sealed'}<br/>
    <b>Status:</b> {session_meta.get('status', 'UNKNOWN')}<br/>
    <b>Total Events:</b> {session_meta.get('event_count', 0)}<br/>
    <b>Events Dropped:</b> {session_meta.get('total_drops', 0)}
    """
    story.append(Paragraph(summary_text, body_style))

    if session_meta.get('total_drops', 0) > 0:
        story.append(Spacer(1, 0.1*inch))
        warning_style = ParagraphStyle(
            'Warning',
            parent=body_style,
            fontSize=10,
            textColor=colors.red,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph(
            f"⚠️ WARNING: {session_meta.get('total_drops')} events were dropped due to buffer overflow.",
            warning_style
        ))

    story.append(Spacer(1, 0.3*inch))

    # === 3. EVENT TIMELINE ===
    story.append(Paragraph("Event Timeline", heading_style))

    timeline_data = [["Seq", "Event Type", "Timestamp"]]
    events = export_data.get('events', [])

    for event in events[:50]:  # Limit for PDF readability
        event_type = event.get('event_type', '')
        # Explicit LOG_DROP marker
        if event_type == 'LOG_DROP':
            event_type = "⚠️ LOG_DROP"

        timestamp = event.get('timestamp_wall') or ''
        timeline_data.append([
            str(event.get('sequence_number', '')),
            event_type,
            timestamp[:23]  # Trim to milliseconds
        ])

    if len(events) > 50:
        timeline_data.append(["...", f"({len(events) - 50} more events)", "..."])

    timeline_table = Table(timeline_data, colWidths=[0.6*inch, 2.5*inch, 2.5*inch])
    timeline_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a4a4a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
    ]))
    story.append(timeline_table)

    # === 4. VERIFICATION ANNEX ===
    story.append(PageBreak())
    story.append(Paragraph("Verification Annex", heading_style))
    story.append(Paragraph(
        "<i>All hashes below are copied verbatim from the verified JSON export.</i>",
        body_style
    ))
    story.append(Spacer(1, 0.2*inch))

    seal = export_data.get('seal', {})
    if seal.get('present'):
        annex_data = [
            ["CHAIN_SEAL", "PRESENT"],
            ["Ingestion Service", seal.get('ingestion_service_id', 'N/A')],
            ["Seal Timestamp", seal.get('seal_timestamp', 'N/A')],
            ["Session Digest", seal.get('session_digest', 'N/A')],
            ["Final Event Hash", seal.get('final_event_hash', 'N/A')],
            ["Sealed Event Count", str(seal.get('event_count', 'N/A'))],
        ]
    else:
        annex_data = [
            ["CHAIN_SEAL", "NOT PRESENT"],
            ["Reason", "Session was not sealed by ingestion service"],
        ]

    annex_table = Table(annex_data, colWidths=[2*inch, 4*inch])
    annex_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8e8e8')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Courier'),
        ('FONTSIZE', (1, 0), (1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(annex_table)
    story.append(Spacer(1, 0.3*inch))

    # Chain-of-custody
    story.append(Paragraph("Chain-of-Custody", heading_style))
    custody = export_data.get('chain_of_custody', {})
    custody_text = f"""
    <b>Export Authority:</b> {custody.get('export_authority', 'N/A')}<br/>
    <b>Export Timestamp:</b> {custody.get('export_timestamp', 'N/A')}<br/>
    <b>Canonical Format:</b> {custody.get('canonical_format', 'N/A')}<br/>
    <br/>
    <i>This PDF is a rendering of the verified JSON export. For cryptographic verification, 
    use the source JSON file with the AgentOps Replay verifier tool.</i>
    """
    story.append(Paragraph(custody_text, body_style))

    # Build PDF
    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def _get_verification_status(export_data: dict[str, Any]) -> str:
    """
    Determine verification status display string.
    """
    evidence_class = export_data.get('evidence_class', '')
    if evidence_class == 'AUTHORITATIVE_EVIDENCE':
        return 'VERIFIED'
    elif evidence_class == 'PARTIAL_AUTHORITATIVE_EVIDENCE':
        return 'PARTIAL (incomplete chain)'
    else:
        return 'NON-AUTHORITATIVE (development only)'
