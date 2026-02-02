from enum import Enum

class SessionStatus(str, Enum):
    ACTIVE = "active"
    SEALED = "sealed"
    FAILED = "failed"
    CLOSED = "closed"

class ChainAuthority(str, Enum):
    SERVER = "server"
    SDK = "sdk"
    LOCAL = "local"
