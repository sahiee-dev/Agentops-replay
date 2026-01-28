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
    Create an audit report summarizing TOOL_CALL events from an event stream for a session.
    
    This collects each TOOL_CALL event into a ToolCallSummary containing sequence number, wall timestamp, tool name, an abbreviated or redacted args summary, and a placeholder result summary ("See TOOL_RESULT event"). Unique tool names are accumulated and returned sorted.
    
    Parameters:
        events (List[Dict[str, Any]]): Ordered list of event dictionaries; TOOL_CALL events should contain a `payload` with `tool_name`, optional `args`, and top-level `sequence_number` and `timestamp_wall` keys.
        session_id (str): Session identifier (UUID) to associate with the generated report.
    
    Returns:
        ToolAuditReport: Aggregated audit report with `session_id`, `total_tool_calls`, `unique_tools` (sorted), and `tool_calls` (list of ToolCallSummary).
    """
    tool_calls = []
    unique_tools = set()
    
    for event in events:
        if event.get('event_type') == 'TOOL_CALL':
            payload = event.get('payload', {})
            tool_name = payload.get('tool_name', 'unknown')
            unique_tools.add(tool_name)
            
            # Build redacted args summary (NEVER include actual content)
            args = payload.get('args', {})
            if isinstance(args, dict):
                args_summary = f"<{len(args)} arguments>"
            elif isinstance(args, (list, tuple)):
                args_summary = f"<{len(args)} items>"
            elif isinstance(args, str):
                args_summary = f"<string of length {len(args)}>"
            elif isinstance(args, bytes):
                args_summary = f"<bytes of length {len(args)}>"
            elif args is None:
                args_summary = "<no arguments>"
            else:
                # For other types, show type and try to get length
                try:
                    args_summary = f"<{type(args).__name__} (length {len(args)})>"
                except TypeError:
                    args_summary = f"<{type(args).__name__}>"
            
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