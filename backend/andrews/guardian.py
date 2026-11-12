"""Independent Guardian authority for Phase 1.

This module deliberately contains no browser, VM, AI, or dashboard integration.
It is a small, deterministic authorization boundary that later components must
call before requesting an action.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


class GuardianError(RuntimeError):
    """Base class for Guardian failures."""


class AuthorizationError(GuardianError):
    """Raised when an action is not authorized."""


@dataclass(frozen=True)
class PermissionLease:
    session_id: str
    lease_id: str
    operator_id: str
    allowed_origins: frozenset[str]
    allowed_actions: frozenset[str]
    issued_at: float
    expires_at: float
    max_tasks: int
    max_corrections: int
    max_actions: int


@dataclass
class SessionState:
    lease: PermissionLease
    status: str = "ACTIVE"
    action_count: int = 0
    correction_count: int = 0
    last_heartbeat: float = 0.0
    stop_reason: str | None = None
    audit_events: list[dict[str, object]] = field(default_factory=list)


class AuditLog:
    """Append-only JSONL audit sink owned by the Guardian."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append(self, event: dict[str, object]) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":"))
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


class Guardian:
    """Authoritative, owner-controlled permission authority."""

    def __init__(
        self,
        *,
        heartbeat_timeout: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
        audit_log: AuditLog | None = None,
    ) -> None:
        if heartbeat_timeout <= 0:
            raise ValueError("heartbeat_timeout must be positive")
        self.heartbeat_timeout = heartbeat_timeout
        self._clock = clock
        self._audit = audit_log or AuditLog()
        self._lock = threading.RLock()
        self._session: SessionState | None = None
        self._stopped = False

    @property
    def session(self) -> SessionState | None:
        with self._lock:
            return self._session

    def start_session(
        self,
        *,
        operator_id: str,
        allowed_origins: Iterable[str],
        allowed_actions: Iterable[str],
        max_tasks: int,
        max_corrections: int,
        max_actions: int,
        lease_seconds: float = 900.0,
    ) -> PermissionLease:
        now = self._clock()
        if self._session and self._session.status == "ACTIVE":
            raise GuardianError("an active session already exists")
        if self._stopped:
            raise GuardianError("Guardian is stopped; explicit restart is required")
        if not operator_id.strip():
            raise ValueError("operator_id must not be empty")
        if lease_seconds <= 0 or max_tasks <= 0 or max_corrections < 0 or max_actions <= 0:
            raise ValueError("session limits are invalid")

        lease = PermissionLease(
            session_id=secrets.token_urlsafe(18),
            lease_id=secrets.token_urlsafe(24),
            operator_id=operator_id,
            allowed_origins=frozenset(self._validate_values(allowed_origins, "origin")),
            allowed_actions=frozenset(self._validate_values(allowed_actions, "action")),
            issued_at=now,
            expires_at=now + lease_seconds,
            max_tasks=max_tasks,
            max_corrections=max_corrections,
            max_actions=max_actions,
        )
        self._session = SessionState(lease=lease, last_heartbeat=now)
        self._record("SESSION_STARTED", session_id=lease.session_id, operator_id=operator_id)
        return lease

    def heartbeat(self, *, operator_id: str) -> None:
        with self._lock:
            session = self._require_session()
            if session.lease.operator_id != operator_id or session.status != "ACTIVE":
                self._deny("HEARTBEAT_REJECTED", operator_id=operator_id)
                raise GuardianError("heartbeat rejected")
            session.last_heartbeat = self._clock()
            self._record("HEARTBEAT", session_id=session.lease.session_id, operator_id=operator_id)

    def authorize_action(
        self,
        *,
        lease_id: str,
        operator_id: str,
        origin: str,
        action: str,
        task_id: str | None = None,
    ) -> None:
        with self._lock:
            session = self._require_session()
            lease = session.lease
            now = self._clock()
            reason = self._authorization_reason(session, lease_id, operator_id, origin, action, now)
            if reason:
                self._deny("ACTION_DENIED", session_id=lease.session_id, reason=reason, origin=origin, action=action)
                raise AuthorizationError(reason)
            session.action_count += 1
            self._record("ACTION_ALLOWED", session_id=lease.session_id, origin=origin, action=action, task_id=task_id)

    def emergency_stop(self, *, owner: str, reason: str) -> None:
        with self._lock:
            if not owner.strip():
                raise ValueError("owner must not be empty")
            session = self._session
            if session:
                session.status = "STOPPED"
                session.stop_reason = reason.strip() or "owner emergency stop"
                self._record("EMERGENCY_STOP", session_id=session.lease.session_id, owner=owner, reason=session.stop_reason)
            self._stopped = True

    def watchdog_tick(self) -> bool:
        """Return True when the session is healthy; stop it on lease/heartbeat expiry."""
        with self._lock:
            session = self._session
            if not session or session.status != "ACTIVE":
                return False
            now = self._clock()
            if now >= session.lease.expires_at:
                self._stop_locked("permission lease expired", "LEASE_EXPIRED")
            elif now - session.last_heartbeat > self.heartbeat_timeout:
                self._stop_locked("operator heartbeat lost", "HEARTBEAT_TIMEOUT")
            return session.status == "ACTIVE"

    def _authorization_reason(self, session: SessionState, lease_id: str, operator_id: str, origin: str, action: str, now: float) -> str | None:
        lease = session.lease
        if self._stopped or session.status != "ACTIVE":
            return "Guardian is stopped"
        if lease_id != lease.lease_id:
            return "unknown permission lease"
        if operator_id != lease.operator_id:
            return "unrecognized operator"
        if now >= lease.expires_at:
            self._stop_locked("permission lease expired", "LEASE_EXPIRED")
            return "permission lease expired"
        if origin not in lease.allowed_origins:
            return "origin is not approved"
        if action not in lease.allowed_actions:
            return "action category is not approved"
        if session.action_count >= lease.max_actions:
            return "action budget exceeded"
        return None

    def _stop_locked(self, reason: str, event_type: str) -> None:
        if self._session:
            self._session.status = "STOPPED"
            self._session.stop_reason = reason
            self._record(event_type, session_id=self._session.lease.session_id, reason=reason)
        self._stopped = True

    def _require_session(self) -> SessionState:
        if not self._session:
            raise GuardianError("no active session")
        return self._session

    @staticmethod
    def _validate_values(values: Iterable[str], label: str) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if not normalized or any(not value for value in normalized):
            raise ValueError(f"{label} values must not be empty")
        return normalized

    def _record(self, event_type: str, **fields: object) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "event_type": event_type, **fields}
        if self._session:
            self._session.audit_events.append(event)
        self._audit.append(event)

    def _deny(self, event_type: str, **fields: object) -> None:
        self._record(event_type, **fields)


class OperatorSupervisor:
    """Independent watchdog adapter used to stop an Operator on Guardian failure."""

    def __init__(self, guardian: Guardian, stop_operator: Callable[[], None]) -> None:
        self.guardian = guardian
        self.stop_operator = stop_operator

    def check(self) -> bool:
        healthy = self.guardian.watchdog_tick()
        if not healthy:
            self.stop_operator()
        return healthy

