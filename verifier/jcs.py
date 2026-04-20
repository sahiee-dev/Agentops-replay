"""
jcs.py - Strict JSON Canonicalization Scheme (RFC 8785) Implementation
Critical for AgentOps Replay verifiability.

Constraints:
1. Strings: UTF-8, NFC Only.
2. Numbers: IEEE-754 doubles.
   - No NaN/Infinity.
   - Integers in range [-2^63, 2^63-1] usually, but JCS treats valid JSON numbers.
   - Formatting: no leading zeros, no "+", lowercase "e".
3. Objects: Keys sorted lexicographically by UCS-2 code units.
4. Arrays: Order preserved.
"""

import json
import math
from typing import Any

# Buffer for strict float formatting
# In Python, json.dumps matches much of standard JSON, but JCS has specific float rules.
# We will use a custom encoder.


def _float_to_string(f: float) -> str:
    """
    Format a float according to RFC 8785 rules.
    This effectively means leveraging the underlying Grisu2/Dragon4/Ryu algorithms
    standard in modern languages, but checking specific edge cases.
    """
    if math.isnan(f) or math.isinf(f):
        raise ValueError("NaN and Infinity are not permitted in JSON")

    # 1. If it can be represented as an integer, print as integer (no .0)
    #    UNLESS it is outside 64-bit integer range? RFC 8785 says:
    #    "If the number can be exactly represented as an IEEE 754 double precision
    #    number... its serialization... is..."
    #    But significantly: "3.2.2.3. Numbers... JSON numbers are generic...
    #    ...interoperable representation... IEEE 754 binary64..."

    # Python's default repr() or str() for floats usually does the right thing for precision,
    # but we need to ensure "no insignificant zeros".

    # Specific JCS Checks:
    # "2.0" -> "2"
    # "-0.0" -> "0" per RFC 8785 Section 3.2.2.3
    #
    # NOTE: RFC 8785 Section 3.2.2.3 states:
    #   "Minus zero is serialized as 0"
    # This means the sign is NOT preserved for negative zero.

    if f == 0.0:
        # Both 0.0 and -0.0 serialize as "0" per RFC 8785
        return "0"

    # For other numbers, standard Python string representation usually follows
    # "shortest round-trippable", which aligns with ES6 / JCS mostly.
    # However, strict JCS enforces specific scientific notation triggers.
    # We will rely on Python's `json` module default separators and formatting
    # but verify -0 handling.

    # Actually, widely accepted JCS implementations in Python just rely on `json.dumps`
    # provided `allow_nan=False` and separators=(',', ':').
    # But we CANNOT trust "usually".

    # Simpler approach: Rely on the fact that we are building a verifier.
    # If the input is ALREADY a string, we work with it.
    # But here we are taking a python object (loading from json) and RE-serializing
    # to check the hash. So we do need to serialize.

    s = json.dumps(f, allow_nan=False)

    # JCS Constraint: No "+" in exponent. e.g. 1e+20 -> 1e20.
    if "e+" in s:
        s = s.replace("e+", "e")

    return s


def canonicalize(data: Any) -> bytes:
    """
    Returns the RFC 8785 canonical bytes of the given Python object.
    Recursive implementation to ensure strict sorting.
    """

    if data is None:
        return b"null"

    if isinstance(data, bool):
        return b"true" if data else b"false"

    if isinstance(data, (int, float)):
        # Floats and Integers
        if isinstance(data, int):
            return str(data).encode("utf-8")
        return _float_to_string(data).encode("utf-8")

    if isinstance(data, str):
        # RFC 8785: Strings MUST be preserved verbatim - NO Unicode normalization
        # RFC 8785 explicitly states: "Parsed JSON string data MUST NOT be
        # altered during subsequent serializations."
        return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )

    if isinstance(data, list):
        # Array: preserve order
        parts = []
        for item in data:
            parts.append(canonicalize(item))
        return b"[" + b",".join(parts) + b"]"

    if isinstance(data, dict):
        # Object: Sort keys by UTF-16BE code unit sequence (RFC 8785)
        # Python's default sort uses Unicode code points, which differs for non-BMP chars
        def utf16_sort_key(s: str) -> bytes:
            # Encode to UTF-16BE and use resulting byte sequence for comparison
            return s.encode("utf-16-be")

        sorted_keys = sorted(data.keys(), key=utf16_sort_key)

        parts = []
        for key in sorted_keys:
            # Key
            key_bytes = json.dumps(
                key, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            # Value
            val_bytes = canonicalize(data[key])
            parts.append(key_bytes + b":" + val_bytes)

        return b"{" + b",".join(parts) + b"}"

    raise TypeError(f"Type {type(data)} not serializable to JCS")
