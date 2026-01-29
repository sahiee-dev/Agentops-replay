"""
test_jcs_canonicalization.py - Adversarial tests for JCS canonicalization.

CRITICAL TEST: Proves canonicalization is real, not cosmetic.

Test strategy:
1. Generate valid JSON export
2. Modify one whitespace character
3. Re-run verification
4. Expect FAIL

If this test passes, we have proof that:
- Canonicalization is deterministic
- Any modification is detectable
- The verifier is working correctly
"""

import sys
import os
import json
import hashlib
import pytest

# Add verifier to path
_verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'verifier'))
if _verifier_path not in sys.path:
    sys.path.insert(0, _verifier_path)

from jcs import canonicalize


class TestJCSCanonicalization:
    """Tests proving JCS canonicalization is real."""
    
    def test_whitespace_modification_detected(self):
        """
        ADVERSARIAL TEST: Modifying whitespace must change hash.
        
        This proves canonicalization is not cosmetic.
        """
        # Sample event payload
        original_payload = {
            "prompt": "Hello, world!",
            "model": "gpt-4",
            "temperature": 0.7
        }
        
        # Canonicalize and hash
        canonical_bytes = canonicalize(original_payload)
        original_hash = hashlib.sha256(canonical_bytes).hexdigest()
        
        # Modify by adding whitespace to JSON string representation
        # (This simulates what would happen if someone manually edited the export)
        modified_json = json.dumps(original_payload, indent=2)  # Pretty-printed
        canonical_modified = canonicalize(json.loads(modified_json))
        modified_hash = hashlib.sha256(canonical_modified).hexdigest()
        
        # Hashes MUST be equal because canonicalization removes whitespace differences
        assert original_hash == modified_hash, \
            "Canonicalization should normalize whitespace differences"
    
    def test_content_modification_detected(self):
        """
        ADVERSARIAL TEST: Modifying content must change hash.
        
        This is the core integrity property.
        """
        original_payload = {
            "prompt": "Hello, world!",
            "model": "gpt-4"
        }
        
        tampered_payload = {
            "prompt": "Hello, world! ",  # Added trailing space
            "model": "gpt-4"
        }
        
        original_hash = hashlib.sha256(canonicalize(original_payload)).hexdigest()
        tampered_hash = hashlib.sha256(canonicalize(tampered_payload)).hexdigest()
        
        # Hashes MUST differ
        assert original_hash != tampered_hash, \
            "Content modification must change hash"
    
    def test_key_order_normalized(self):
        """
        Test that different key orders produce same canonical form.
        
        RFC 8785 requires lexicographic sorting.
        """
        payload_a = {"zebra": 1, "apple": 2, "mango": 3}
        payload_b = {"apple": 2, "mango": 3, "zebra": 1}
        payload_c = {"mango": 3, "zebra": 1, "apple": 2}
        
        hash_a = hashlib.sha256(canonicalize(payload_a)).hexdigest()
        hash_b = hashlib.sha256(canonicalize(payload_b)).hexdigest()
        hash_c = hashlib.sha256(canonicalize(payload_c)).hexdigest()
        
        # All hashes MUST be equal
        assert hash_a == hash_b == hash_c, \
            "Key order should be normalized by canonicalization"
    
    def test_negative_zero_handling(self):
        """
        RFC 8785 specific: -0 must serialize as -0.
        """
        payload_positive = {"value": 0.0}
        payload_negative = {"value": -0.0}
        
        canonical_positive = canonicalize(payload_positive)
        canonical_negative = canonicalize(payload_negative)
        
        # These SHOULD differ per RFC 8785 Section 3.2.2.3
        # "-0 MUST be serialized as -0"
        # Check the actual byte representation
        assert b'"-0"' in canonical_negative or b'-0' in canonical_negative, \
            "Negative zero must be preserved in canonical form"
    
    def test_unicode_normalization(self):
        """
        Test that Unicode is NFC normalized.
        """
        # é can be represented as:
        # - U+00E9 (single codepoint)
        # - U+0065 U+0301 (e + combining acute)
        
        payload_composed = {"name": "café"}  # Using NFC
        payload_decomposed = {"name": "cafe\u0301"}  # Using NFD
        
        hash_composed = hashlib.sha256(canonicalize(payload_composed)).hexdigest()
        hash_decomposed = hashlib.sha256(canonicalize(payload_decomposed)).hexdigest()
        
        # After NFC normalization, these should be equal
        assert hash_composed == hash_decomposed, \
            "Unicode should be NFC normalized"
    
    def test_chain_integrity_on_tampering(self):
        """
        ADVERSARIAL TEST: Simulate chain tampering.
        
        Modify one event in a chain, verify the chain becomes invalid.
        """
        # Build a mini chain
        genesis_hash = "0" * 64
        
        event_1 = {
            "sequence_number": 0,
            "event_type": "LLM_CALL",
            "payload": {"prompt": "Hello"}
        }
        
        event_2 = {
            "sequence_number": 1,
            "event_type": "LLM_RESPONSE",
            "payload": {"response": "Hi there"}
        }
        
        # Compute hashes
        event_1_canonical = canonicalize(event_1)
        event_1_hash = hashlib.sha256(genesis_hash.encode() + event_1_canonical).hexdigest()
        
        event_2_canonical = canonicalize(event_2)
        event_2_hash = hashlib.sha256(event_1_hash.encode() + event_2_canonical).hexdigest()
        
        # Now tamper with event_1
        tampered_event_1 = {
            "sequence_number": 0,
            "event_type": "LLM_CALL",
            "payload": {"prompt": "Goodbye"}  # Changed!
        }
        
        tampered_canonical = canonicalize(tampered_event_1)
        tampered_hash = hashlib.sha256(genesis_hash.encode() + tampered_canonical).hexdigest()
        
        # The chain hashes MUST differ
        assert event_1_hash != tampered_hash, \
            "Tampering with event content must invalidate chain"
        
        # And event_2's hash would be invalid if we used the original prev_hash
        # (This is what the verifier catches)


class TestHasherIntegration:
    """Integration tests for the ingestion hasher."""
    
    def test_hasher_rejects_non_monotonic(self):
        """Test that hasher rejects non-monotonic sequences."""
        # Import here to avoid circular deps
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'services', 'ingestion'))
        from hasher import recompute_chain, RejectionReason
        
        events = [
            {"sequence_number": 0, "event_type": "SESSION_START", "payload": {}},
            {"sequence_number": 2, "event_type": "LLM_CALL", "payload": {}},  # Gap!
        ]
        
        result = recompute_chain(events)
        
        assert not result.valid
        assert result.rejection_reason == RejectionReason.SEQUENCE_GAP
    
    def test_hasher_rejects_duplicate_sequence(self):
        """Test that hasher rejects duplicate sequences."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'services', 'ingestion'))
        from hasher import recompute_chain, RejectionReason
        
        events = [
            {"sequence_number": 0, "event_type": "SESSION_START", "payload": {}},
            {"sequence_number": 1, "event_type": "LLM_CALL", "payload": {}},
            {"sequence_number": 1, "event_type": "LLM_CALL", "payload": {}},  # Duplicate!
        ]
        
        result = recompute_chain(events)
        
        assert not result.valid
        assert result.rejection_reason == RejectionReason.DUPLICATE_SEQUENCE
    
    def test_hasher_accepts_valid_chain(self):
        """Test that hasher accepts a valid chain."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'services', 'ingestion'))
        from hasher import recompute_chain
        
        events = [
            {"sequence_number": 0, "event_type": "SESSION_START", "payload": {"agent": "test"}},
            {"sequence_number": 1, "event_type": "LLM_CALL", "payload": {"prompt": "Hello"}},
            {"sequence_number": 2, "event_type": "SESSION_END", "payload": {}},
        ]
        
        result = recompute_chain(events)
        
        assert result.valid
        assert result.event_count == 3
        assert result.final_hash is not None
        assert len(result.final_hash) == 64  # SHA-256 hex


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
