"""
LangChain Version Compatibility Module

Tracks framework version and provides compatibility warnings per goal.md requirements:
- Version-pin integrations
- Emit framework version per session
- Add semantic compatibility warnings
"""

import importlib.metadata
from typing import Tuple, Optional
import warnings

# Integration version - bump on breaking changes
INTEGRATION_VERSION = "0.1.0"

# Supported LangChain version range
SUPPORTED_MIN = (0, 1, 0)
SUPPORTED_MAX = (0, 3, 0)  # Exclusive upper bound


def get_langchain_version() -> Optional[Tuple[int, int, int]]:
    """
    Get installed LangChain version as tuple.
    Returns None if LangChain is not installed or parse error.
    """
    try:
        version_str = importlib.metadata.version("langchain")
        
        # Strip local version metadata (e.g., "0.2.0+local" -> "0.2.0")
        if "+" in version_str:
            version_str = version_str.split("+")[0]
        
        parts = version_str.split(".")[:3]
        return tuple(int(p.split("a")[0].split("b")[0].split("rc")[0]) for p in parts)
    except (importlib.metadata.PackageNotFoundError, ValueError):
        return None


def get_langchain_version_string() -> str:
    """Get LangChain version as string."""
    try:
        return importlib.metadata.version("langchain")
    except importlib.metadata.PackageNotFoundError:
        return "not_installed"


def check_compatibility() -> dict:
    """
    Check if installed LangChain version is compatible.
    
    Returns:
        dict with:
            - compatible: bool
            - version: str
            - warning: Optional[str]
    """
    version = get_langchain_version()
    version_str = get_langchain_version_string()
    
    if version is None:
        return {
            "compatible": False,
            "version": "not_installed",
            "warning": "LangChain is not installed. Install with: pip install langchain"
        }
    
    if version < SUPPORTED_MIN:
        return {
            "compatible": False,
            "version": version_str,
            "warning": f"LangChain {version_str} is below minimum supported version {'.'.join(map(str, SUPPORTED_MIN))}. Replay accuracy not guaranteed."
        }
    
    if version >= SUPPORTED_MAX:
        return {
            "compatible": False,
            "version": version_str,
            "warning": f"LangChain {version_str} is above maximum tested version. Replay accuracy not guaranteed for LangChain >= {'.'.join(map(str, SUPPORTED_MAX))}"
        }
    
    return {
        "compatible": True,
        "version": version_str,
        "warning": None
    }


def warn_if_incompatible():
    """Emit warning if LangChain version is not fully compatible."""
    compat = check_compatibility()
    if not compat["compatible"] and compat["warning"]:
        warnings.warn(
            f"AgentOps Replay: {compat['warning']}",
            UserWarning,
            stacklevel=3
        )
