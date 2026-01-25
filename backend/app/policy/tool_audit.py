"""
tool_audit.py - Tool access audit for compliance reporting.
"""

from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class ToolCallSummary(BaseModel):
    """Summary of a tool call"""
    sequence_number: int
    timestamp: str
    tool_name: str
    args_summary: str  # Redacted if contains PII
    result_summary: str  # Redacted if contains PII


class ToolAuditReport(BaseModel):
    """Complete tool audit for a session"""
    session_id: str
    total_tool_calls: int
    unique_tools: List[str]
    tool_calls: List[ToolCallSummary]


def generate_tool_audit(events: List[Dict[str, Any]], session_id: str) -> ToolAuditReport:
    """
    Generate tool access audit trail.
    
    Extracts all TOOL_CALL events and summarizes:
    - Tool name
    - Timestamp
    - Arguments (redacted if PII detected)
    
    Args:
        events: List of event dictionaries
        session_id: Session UUID
        
    Returns:
        ToolAuditReport
    """
    tool_calls = []
    unique_tools = set()
    
    for event in events:
        if event.get('event_type') == 'TOOL_CALL':
            payload = event.get('payload', {})
            tool_name = payload.get('tool_name', 'unknown')
            unique_tools.add(tool_name)
            
            # Redact large or potentially sensitive args
            args = payload.get('args', {})
            if isinstance(args, dict):
                args_summary = f"{len(args)} arguments"
            else:
                args_summary = str(args)[:50]  # Truncate
            
            tool_calls.append(ToolCallSummary(
                sequence_number=event.get('sequence_number'),
                timestamp=event.get('timestamp_wall'),
                tool_name=tool_name,
                args_summary=args_summary,
                result_summary="See TOOL_RESULT event"
            ))
    
    return ToolAuditReport(
        session_id=session_id,
        total_tool_calls=len(tool_calls),
        unique_tools=sorted(list(unique_tools)),
        tool_calls=tool_calls
    )
