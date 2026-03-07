"""
engine.py - Policy Engine orchestrator.

Loads, versions, and evaluates policies over committed events.

CONSTITUTIONAL CONSTRAINTS:
1. PolicyEngine.evaluate() is a PURE FUNCTION — no DB, no network, no side effects
2. Output is deterministic: same events + same policy set → identical violations
3. Every violation records policy_version and policy_hash
4. policy_hash = SHA-256(policy source code + canonical policy config subset)

STRUCTURAL PURITY:
- No database imports allowed in this module or any policy module
- No Redis, HTTP, or network imports
- No os.environ access for evaluation logic
- Policies receive CanonicalEvent, not raw dicts
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

UTC = timezone.utc


@dataclass(frozen=True)
class CanonicalEvent:
    """
    Immutable, canonical representation of a committed event.

    This is the ONLY input type for policy evaluation.
    Policies MUST NOT access raw dicts or ingestion-internal fields.
    """

    event_id: str
    session_id: str
    sequence_number: int
    event_type: str
    payload_canonical: str  # JCS-canonicalized JSON string
    payload_hash: str
    event_hash: str
    chain_authority: str


@dataclass(frozen=True)
class ViolationRecord:
    """
    Immutable output of a policy evaluation.

    This is a data transfer object — NOT an ORM model.
    The caller (Worker) is responsible for persistence.
    """

    id: str  # UUID
    session_id: str
    event_id: str
    event_sequence_number: int
    policy_name: str
    policy_version: str
    policy_hash: str
    severity: str  # WARNING | ERROR | CRITICAL
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDescriptor:
    """Identity of a single policy at load time."""

    name: str
    version: str
    source_hash: str
    enabled: bool


@dataclass(frozen=True)
class PolicySet:
    """Immutable snapshot of the active policy configuration."""

    version: str  # From policy.yaml
    config_hash: str  # SHA-256 of canonical policy.yaml content
    policies: tuple[PolicyDescriptor, ...]


class Policy(ABC):
    """
    Abstract base class for all policies.

    STRUCTURAL CONSTRAINTS:
    - evaluate() must be a pure function
    - No database access
    - No network access
    - No environment variable access for logic
    - Input: list of CanonicalEvent
    - Output: list of ViolationRecord
    """

    name: str
    version: str

    @abstractmethod
    def evaluate(
        self,
        events: list[CanonicalEvent],
        policy_version: str,
        policy_hash: str,
    ) -> list[ViolationRecord]:
        """
        Evaluate events and return violations.

        Args:
            events: Canonical committed events (immutable)
            policy_version: Version string of the active policy set
            policy_hash: SHA-256(source + config) for this policy

        Returns:
            List of ViolationRecord (may be empty)
        """
        ...

    def compute_source_hash(self) -> str:
        """SHA-256 of this policy's evaluate() method source code."""
        source = inspect.getsource(self.evaluate)
        return hashlib.sha256(source.encode("utf-8")).hexdigest()


class PolicyEngine:
    """
    Loads, versions, and runs policies.

    The engine is created once at Worker startup.
    It computes and logs the PolicySet identity (version + config_hash).
    """

    def __init__(self, config_path: str | Path = "policy.yaml") -> None:
        self._config_path = Path(config_path)
        self._policies: list[Policy] = []
        self._policy_set: PolicySet | None = None
        self._config: dict[str, Any] = {}
        self._config_canonical: str = ""

        self._load_config()

    def _load_config(self) -> None:
        """Load policy.yaml and compute config hash."""
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Policy config not found: {self._config_path}. "
                f"Worker cannot start without policy configuration."
            )

        raw = self._config_path.read_text(encoding="utf-8")
        self._config = yaml.safe_load(raw)
        if not isinstance(self._config, dict):
            raise ValueError(
                f"Policy config is not a valid YAML mapping: {self._config_path}"
            )

        # Canonical form for hashing (sorted JSON)
        self._config_canonical = json.dumps(self._config, sort_keys=True, separators=(",", ":"))
        logger.info(
            "Policy config loaded: version=%s",
            self._config.get("version", "UNKNOWN"),
        )

    def register(self, policy: Policy) -> None:
        """
        Register a policy with the engine.

        The policy is only active if enabled in policy.yaml.
        """
        policy_config = self._config.get("policies", {}).get(
            policy.name.lower().replace("_policy", "").replace("_", ""), {}
        )
        if not policy_config:
            # Also try exact name match
            policy_config = self._config.get("policies", {}).get(policy.name, {})

        enabled = policy_config.get("enabled", False) if policy_config else False

        if enabled:
            self._policies.append(policy)
            logger.info("Policy registered: %s (version: %s)", policy.name, policy.version)
        else:
            logger.info("Policy skipped (disabled): %s", policy.name)

        # Invalidate cached policy set
        self._policy_set = None

    def policy_set(self) -> PolicySet:
        """Return the immutable PolicySet identity."""
        if self._policy_set is None:
            config_hash = hashlib.sha256(
                self._config_canonical.encode("utf-8")
            ).hexdigest()

            descriptors = tuple(
                PolicyDescriptor(
                    name=p.name,
                    version=p.version,
                    source_hash=p.compute_source_hash(),
                    enabled=True,
                )
                for p in self._policies
            )

            self._policy_set = PolicySet(
                version=self._config.get("version", "0.0.0"),
                config_hash=config_hash,
                policies=descriptors,
            )

        return self._policy_set

    def compute_policy_hash(self, policy: Policy) -> str:
        """
        Compute policy_hash = SHA-256(policy source + canonical config subset).

        This captures the full evaluation semantics, not just the code.
        Config changes (e.g., allowed_tools list) change the hash.
        """
        source = inspect.getsource(policy.evaluate)

        # Extract this policy's config subset
        policy_config = self._config.get("policies", {}).get(
            policy.name.lower().replace("_policy", "").replace("_", ""), {}
        )
        if not policy_config:
            policy_config = self._config.get("policies", {}).get(policy.name, {})

        config_canonical = json.dumps(
            policy_config or {}, sort_keys=True, separators=(",", ":")
        )

        combined = source + "\n---\n" + config_canonical
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def evaluate(self, events: list[CanonicalEvent]) -> list[ViolationRecord]:
        """
        Evaluate all active policies over committed events.

        This is a PURE FUNCTION:
        - No database access
        - No network access
        - No side effects
        - Deterministic: same events + same policy set → same violations

        Args:
            events: Canonical committed events

        Returns:
            List of ViolationRecord from all active policies
        """
        ps = self.policy_set()
        all_violations: list[ViolationRecord] = []

        for policy in self._policies:
            policy_hash = self.compute_policy_hash(policy)

            try:
                violations = policy.evaluate(
                    events=events,
                    policy_version=ps.version,
                    policy_hash=policy_hash,
                )
                all_violations.extend(violations)
            except Exception:
                # Policy evaluation failure → propagate to caller
                # Caller (Worker) will rollback the entire batch
                logger.exception(
                    "Policy '%s' raised exception during evaluation", policy.name
                )
                raise

        return all_violations

    def get_config(self, policy_name: str) -> dict[str, Any]:
        """Get the config subset for a specific policy (for adapter use)."""
        policies = self._config.get("policies", {})
        config = policies.get(policy_name, {})
        if not config:
            # Try normalized name
            normalized = policy_name.lower().replace("_policy", "").replace("_", "")
            config = policies.get(normalized, {})
        return config or {}
