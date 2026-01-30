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

from .frames import FrameType, ReplayFrame, VerificationStatus
from .warnings import WarningSeverity, ReplayWarning, WarningCode
from .engine import load_verified_session, build_replay, ReplayResult

__all__ = [
    'FrameType',
    'ReplayFrame',
    'VerificationStatus',
    'WarningSeverity',
    'ReplayWarning',
    'WarningCode',
    'load_verified_session',
    'build_replay',
    'ReplayResult',
]
