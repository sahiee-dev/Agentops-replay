"""
Replay System Package.

CONSTITUTIONAL CONSTRAINT:
Replay must show what happened—nothing more, nothing less.
No inference. No interpretation. No helpful lies.

Core Principles:
- READ-ONLY: Replay cannot modify events
- LITERAL: Show exactly what was recorded
- TRANSPARENT: Gaps, drops, and uncertainties are explicit
- DETERMINISTIC: Same input → same output, always
- VERIFIED-FIRST: Replay consumes verified chains only
"""

from .engine import ReplayResult, build_replay, load_verified_session
from .frames import FrameType, ReplayFrame, VerificationStatus
from .warnings import ReplayWarning, WarningCode, WarningSeverity

__all__ = [
    "FrameType",
    "ReplayFrame",
    "ReplayResult",
    "ReplayWarning",
    "VerificationStatus",
    "WarningCode",
    "WarningSeverity",
    "build_replay",
    "load_verified_session",
]
