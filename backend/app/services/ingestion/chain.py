"""
backend/app/services/ingestion/chain.py — TRD §4.5

Server-side chain verification.

CRITICAL: All hash recomputation is server-side authority.
SDK-provided hashes are inputs to verify against, never trusted.
"""

import hashlib
import os
import sys

# CRITICAL: Import JCS from the single canonical copy in verifier/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'verifier'))
from jcs import canonicalize as jcs_canonicalize


class ChainVerifier:
    """
    Recomputes and verifies event hashes server-side.

    This is the ingestion service's authority boundary:
    every event entering the system is re-hashed here.
    SDK claims are never trusted.
    """

    def verify_event_hash(
        self,
        event: dict,
    ) -> tuple[bool, str, str]:
        """
        Recompute the event_hash from the event fields and compare to stored value.

        The hash covers all fields EXCEPT event_hash itself,
        using JCS canonicalization (RFC 8785) + SHA-256.

        Returns
        -------
        (is_valid, expected_hash, provided_hash)
        """
        event_for_hash = {k: v for k, v in event.items() if k != "event_hash"}
        canonical_bytes = jcs_canonicalize(event_for_hash)
        expected_hash = hashlib.sha256(canonical_bytes).hexdigest()
        provided_hash = event.get("event_hash", "")
        is_valid = expected_hash == provided_hash
        return (is_valid, expected_hash, provided_hash)

    def verify_prev_hash(
        self,
        event: dict,
        previous_event_hash: str,
    ) -> tuple[bool, str, str]:
        """
        Verify the chain linkage: event['prev_hash'] must equal
        the authoritative hash of the previous event.

        Returns
        -------
        (is_valid, expected_prev_hash, provided_prev_hash)
        """
        provided_prev_hash = event.get("prev_hash", "")
        is_valid = provided_prev_hash == previous_event_hash
        return (is_valid, previous_event_hash, provided_prev_hash)
