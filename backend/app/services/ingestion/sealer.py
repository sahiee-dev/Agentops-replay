"""
sealer.py - Chain sealing logic for establishing authority.

CRITICAL INVARIANT: A sealed chain can NEVER be re-sealed or extended.

Seal Rules:
1. Event after seal → REJECT
2. Double seal attempt → REJECT  
3. Missing events at seal time → PARTIAL_AUTHORITATIVE
4. Complete chain → AUTHORITATIVE_EVIDENCE
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional
import uuid

from .hasher import recompute_chain, ChainResult, GENESIS_HASH


class SealStatus(Enum):
    """Result status of sealing attempt."""
    SEALED = "SEALED"
    ALREADY_SEALED = "ALREADY_SEALED"
    INVALID_CHAIN = "INVALID_CHAIN"
    POST_SEAL_EVENT = "POST_SEAL_EVENT"


@dataclass
class SealResult:
    """Result of a chain sealing operation."""
    status: SealStatus
    evidence_class: Optional[str] = None
    session_digest: Optional[str] = None
    final_event_hash: Optional[str] = None
    seal_timestamp: Optional[str] = None
    event_count: int = 0
    ingestion_service_id: Optional[str] = None
    rejection_reason: Optional[str] = None


def seal_chain(
    session_id: str,
    events: List[Dict[str, Any]],
    ingestion_service_id: str,
    existing_seal: Optional[Dict[str, Any]] = None,
    total_drops: int = 0
) -> SealResult:
    """
    Seal an event chain to establish server authority for a session.
    
    If the chain is not previously sealed and recomputation validates the events, returns a SEALED result containing evidence_class, session_digest, final_event_hash, seal_timestamp, event_count, and ingestion_service_id. If an existing seal is provided, returns ALREADY_SEALED and preserves the original seal_timestamp and session_digest. If recomputation fails, returns INVALID_CHAIN with a rejection_reason.
    
    Parameters:
        session_id: Session UUID for which the chain is being sealed.
        events: Events to be recomputed and validated as the chain to seal.
        ingestion_service_id: Identifier of the ingestion service issuing the seal.
        existing_seal: If provided, indicates the chain was already sealed and will cause an ALREADY_SEALED result.
        total_drops: Number of LOG_DROP events observed; influences the evidence class (authoritative vs partial).
    
    Returns:
        SealResult: A dataclass describing the outcome. For a successful seal, includes evidence_class, session_digest, final_event_hash, seal_timestamp, event_count, and ingestion_service_id. For rejections, includes status and rejection_reason.
    """
    # INVARIANT 1: No re-sealing
    if existing_seal is not None:
        return SealResult(
            status=SealStatus.ALREADY_SEALED,
            rejection_reason="Chain was already sealed. Re-sealing is forbidden.",
            seal_timestamp=existing_seal.get('seal_timestamp'),
            session_digest=existing_seal.get('session_digest')
        )
    
    # Recompute chain to establish authority
    chain_result = recompute_chain(events)
    
    if not chain_result.valid:
        return SealResult(
            status=SealStatus.INVALID_CHAIN,
            rejection_reason=f"{chain_result.rejection_reason.value}: {chain_result.rejection_details}"
        )
    
    # Compute session digest (hash of all event hashes)
    session_digest = _compute_session_digest(
        session_id=session_id,
        events=chain_result.recomputed_events,
        final_hash=chain_result.final_hash
    )
    
    # Determine evidence class
    evidence_class = _determine_evidence_class(
        total_drops=total_drops,
        event_count=chain_result.event_count
    )
    
    # Capture timestamp once for consistency
    now = datetime.now(timezone.utc)
    seal_timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'
    
    return SealResult(
        status=SealStatus.SEALED,
        evidence_class=evidence_class,
        session_digest=session_digest,
        final_event_hash=chain_result.final_hash,
        seal_timestamp=seal_timestamp,
        event_count=chain_result.event_count,
        ingestion_service_id=ingestion_service_id
    )


def reject_post_seal_event(
    session_id: str,
    seal_timestamp: str,
    event_timestamp: str
) -> SealResult:
    """
    Reject an event that arrived after the chain was sealed.
    
    INVARIANT: A sealed chain can never be extended.
    
    Args:
        session_id: Session UUID
        seal_timestamp: When the chain was sealed
        event_timestamp: When the late event arrived
        
    Returns:
        SealResult with POST_SEAL_EVENT status
    """
    return SealResult(
        status=SealStatus.POST_SEAL_EVENT,
        rejection_reason=f"Event received at {event_timestamp} after seal at {seal_timestamp}. "
                         f"Sealed chains cannot be extended."
    )


def _compute_session_digest(
    session_id: str,
    events: List[Dict[str, Any]],
    final_hash: str
) -> str:
    """
    Compute a SHA-256 digest that represents the session by combining the session ID, the events' hashes, and the final hash.
    
    Parameters:
    	session_id (str): The session identifier to include in the digest.
    	events (List[Dict[str, Any]]): Ordered list of event objects; each event's 'event_hash' value is concatenated if present (missing 'event_hash' is treated as an empty string).
    	final_hash (str): The final hash of the recomputed chain to include in the digest.
    
    Returns:
    	session_digest (str): Hexadecimal SHA-256 digest of the concatenated inputs.
    """
    digest_input = session_id
    
    for event in events:
        digest_input += event.get('event_hash', '')
    
    digest_input += final_hash
    
    return hashlib.sha256(digest_input.encode('utf-8')).hexdigest()


def _determine_evidence_class(total_drops: int, event_count: int) -> str:
    """
    Classify the chain's evidence as authoritative or partial based on drops and event count.
    
    Parameters:
        total_drops (int): Number of dropped events detected during ingestion.
        event_count (int): Number of events present in the recomputed chain.
    
    Returns:
        str: `"AUTHORITATIVE_EVIDENCE"` if `total_drops` is 0 and `event_count` is greater than 0, `"PARTIAL_AUTHORITATIVE_EVIDENCE"` otherwise.
    """
    if total_drops == 0 and event_count > 0:
        return "AUTHORITATIVE_EVIDENCE"
    
    return "PARTIAL_AUTHORITATIVE_EVIDENCE"


def create_chain_seal_event(seal_result: SealResult, session_id: str) -> Dict[str, Any]:
    """
    Create a CHAIN_SEAL event payload for a sealed session.
    
    Parameters:
        seal_result (SealResult): A `SealResult` with status `SealStatus.SEALED` containing seal metadata.
        session_id (str): Identifier of the session being sealed.
    
    Returns:
        dict: A CHAIN_SEAL event dictionary with the following structure:
            - event_id (str): UUID for the event.
            - session_id (str): The provided session identifier.
            - event_type (str): `"CHAIN_SEAL"`.
            - timestamp_wall (str): Seal timestamp from `seal_result`.
            - payload (dict): Contains `evidence_class`, `session_digest`, `final_event_hash`, `event_count`, and `ingestion_service_id`.
            - chain_authority (str): `"SERVER"`.
    
    Raises:
        ValueError: If `seal_result.status` is not `SealStatus.SEALED`.
    """
    if seal_result.status != SealStatus.SEALED:
        raise ValueError(f"Cannot create CHAIN_SEAL event from non-sealed result: {seal_result.status}")
    
    return {
        "event_id": str(uuid.uuid4()),
        "session_id": session_id,
        "event_type": "CHAIN_SEAL",
        "timestamp_wall": seal_result.seal_timestamp,
        "payload": {
            "evidence_class": seal_result.evidence_class,
            "session_digest": seal_result.session_digest,
            "final_event_hash": seal_result.final_event_hash,
            "event_count": seal_result.event_count,
            "ingestion_service_id": seal_result.ingestion_service_id
        },
        "chain_authority": "SERVER"
    }