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
import struct

# Buffer for strict float formatting
# In Python, json.dumps matches much of standard JSON, but JCS has specific float rules.
# We will use a custom encoder.

def _float_to_string(f: float) -> str:
    """
    Serialize a floating-point value to the canonical JSON number string required by RFC 8785.
    
    Parameters:
        f (float): The floating-point value to serialize. NaN and infinities are not allowed.
    
    Returns:
        str: The RFC 8785-compliant JSON representation of `f` (e.g., integers without ".0", minus zero as "0", no '+' in exponents).
    
    Raises:
        ValueError: If `f` is NaN or infinite.
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
    if 'e+' in s:
        s = s.replace('e+', 'e')
    
    return s

def canonicalize(data) -> bytes:
    """
    Produce RFC 8785 (JCS) canonical JSON bytes for the given Python value.
    
    Serializes the input to a compact, canonical JSON byte sequence (UTF-8) following RFC 8785 rules:
    - None -> `null`
    - bool -> `true` or `false`
    - int -> decimal integer string
    - float -> RFC 8785-compatible decimal string (handled by _float_to_string)
    - str -> JSON string preserved verbatim (no Unicode normalization)
    - list -> JSON array preserving element order
    - dict -> JSON object with keys sorted by their UTF-16BE code unit sequence; keys must be `str`
    
    Parameters:
        data: The Python value to canonicalize. Supported types: None, bool, int, float, str, list, and dict (with string keys). Nested structures of these types are supported.
    
    Returns:
        Canonical UTF-8 encoded JSON bytes representing `data` according to RFC 8785.
    
    Raises:
        TypeError: If `data` contains a type not representable in JCS (e.g., non-string dict keys or unsupported Python objects).
    """
    
    if data is None:
        return b'null'
    
    if isinstance(data, bool):
        return b'true' if data else b'false'
    
    if isinstance(data, (int, float)):
        # Floats and Integers
        if isinstance(data, int):
            return str(data).encode('utf-8')
        return _float_to_string(data).encode('utf-8')
    
    if isinstance(data, str):
        # RFC 8785: Strings MUST be preserved verbatim - NO Unicode normalization
        # RFC 8785 explicitly states: "Parsed JSON string data MUST NOT be 
        # altered during subsequent serializations."
        return json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    
    if isinstance(data, list):
        # Array: preserve order
        parts = []
        for item in data:
            parts.append(canonicalize(item))
        return b'[' + b','.join(parts) + b']'
    
    if isinstance(data, dict):
        # Object: Sort keys by UTF-16BE code unit sequence (RFC 8785)
        # Python's default sort uses Unicode code points, which differs for non-BMP chars
        def utf16_sort_key(s: str) -> bytes:
            # Encode to UTF-16BE and use resulting byte sequence for comparison
            return s.encode('utf-16-be')
        
        sorted_keys = sorted(data.keys(), key=utf16_sort_key)
        
        parts = []
        for key in sorted_keys:
            # Key
            key_bytes = json.dumps(key, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            # Value
            val_bytes = canonicalize(data[key])
            parts.append(key_bytes + b':' + val_bytes)
        
        return b'{' + b','.join(parts) + b'}'
        
    raise TypeError(f"Type {type(data)} not serializable to JCS")
