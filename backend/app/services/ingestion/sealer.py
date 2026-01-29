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
    Seal an event chain, establishing server authority.
    
    CRITICAL INVARIANTS:
    - A sealed chain can never be re-sealed
    - A sealed chain can never be extended
    - Missing events result in PARTIAL_AUTHORITATIVE
    
    Args:
        session_id: Session UUID
        events: List of events to seal (will be recomputed)
        ingestion_service_id: ID of the ingestion service issuing the seal
        existing_seal: If not None, indicates chain was previously sealed → REJECT
        total_drops: Number of LOG_DROP events (affects evidence class)
        
    Returns:
        SealResult with seal details or rejection reason
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
    
    seal_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + \
                     f'{datetime.now(timezone.utc).microsecond // 1000:03d}Z'
    
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
    Compute session digest from all event hashes.
    
    Digest = SHA256(session_id + event_hash_0 + event_hash_1 + ... + final_hash)
    """
    digest_input = session_id
    
    for event in events:
        digest_input += event.get('event_hash', '')
    
    digest_input += final_hash
    
    return hashlib.sha256(digest_input.encode('utf-8')).hexdigest()


def _determine_evidence_class(total_drops: int, event_count: int) -> str:
    """
    Determine evidence class based on chain completeness.
    
    Returns:
        - AUTHORITATIVE_EVIDENCE: No drops, complete chain
        - PARTIAL_AUTHORITATIVE_EVIDENCE: Has drops or incomplete
    """
    if total_drops == 0 and event_count > 0:
        return "AUTHORITATIVE_EVIDENCE"
    
    return "PARTIAL_AUTHORITATIVE_EVIDENCE"


def create_chain_seal_event(seal_result: SealResult, session_id: str) -> Dict[str, Any]:
    """
    Create a CHAIN_SEAL event from a seal result.
    
    This is the event that gets persisted to mark chain finalization.
    Only the INGESTION SERVICE can emit CHAIN_SEAL events.
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
