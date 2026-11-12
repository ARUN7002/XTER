"""Safe Operator boundary for Phase 4.

This phase implements state and authorization contracts only. It intentionally
does not drive a desktop, browser, VM, or external website.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .guardian import AuthorizationError, Guardian, GuardianError, PermissionLease


class OperatorState(StrEnum):
    STOPPED = "STOPPED"
    PAUSED = "PAUSED"
    READY = "READY"
    RUNNING = "RUNNING"
    MANUAL_CONTROL = "MANUAL_CONTROL"


class BrowserState(StrEnum):
    NOT_ATTACHED = "NOT_ATTACHED"
    READY = "READY"
    LOADING = "LOADING"
    CRASHED = "CRASHED"


class OperatorScopeError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserAttachment:
    origin: str
    profile_path: str
    dedicated_vm: bool


class Operator:
    def __init__(self, guardian: Guardian, lease: PermissionLease, *, operator_id: str, vm_id: str) -> None:
        if not vm_id.strip():
            raise ValueError("vm_id is required")
        self.guardian = guardian
        self.lease = lease
        self.operator_id = operator_id
        self.vm_id = vm_id
        self.state = OperatorState.STOPPED
        self.browser_state = BrowserState.NOT_ATTACHED
        self.browser: BrowserAttachment | None = None

    def start(self) -> None:
        self._heartbeat_or_stop()
        self.state = OperatorState.READY

    def attach_browser(self, attachment: BrowserAttachment) -> None:
        if not attachment.dedicated_vm:
            raise OperatorScopeError("browser must be attached inside the dedicated VM")
        if not attachment.profile_path.strip():
            raise OperatorScopeError("dedicated browser profile is required")
        self._authorize(attachment.origin, "read")
        self.browser = attachment
        self.browser_state = BrowserState.READY

    def set_browser_state(self, state: BrowserState) -> None:
        self.browser_state = state
        if state == BrowserState.CRASHED:
            self.state = OperatorState.PAUSED

    def request_input(self, *, origin: str, action: str) -> None:
        if self.state not in {OperatorState.READY, OperatorState.RUNNING}:
            raise OperatorScopeError("operator is not authorized to send automated input")
        if self.browser_state != BrowserState.READY:
            self.state = OperatorState.PAUSED
            raise OperatorScopeError("browser is not ready")
        self._authorize(origin, action)
        self.state = OperatorState.RUNNING

    def take_control(self, *, owner: str) -> None:
        self.guardian.revoke_automated_input(owner=owner)
        self.state = OperatorState.MANUAL_CONTROL

    def resume(self, *, owner: str) -> None:
        if self.state != OperatorState.MANUAL_CONTROL:
            raise OperatorScopeError("operator is not under manual control")
        self.guardian.resume_automated_input(owner=owner)
        self._heartbeat_or_stop()
        self.state = OperatorState.READY

    def guardian_disconnected(self) -> None:
        self.state = OperatorState.STOPPED

    def _authorize(self, origin: str, action: str) -> None:
        try:
            self.guardian.authorize_action(
                lease_id=self.lease.lease_id,
                operator_id=self.operator_id,
                origin=origin,
                action=action,
            )
        except (AuthorizationError, GuardianError) as exc:
            self.state = OperatorState.PAUSED
            raise OperatorScopeError(str(exc)) from exc

    def _heartbeat_or_stop(self) -> None:
        try:
            self.guardian.heartbeat(operator_id=self.operator_id)
        except GuardianError as exc:
            self.state = OperatorState.STOPPED
            raise OperatorScopeError("Guardian heartbeat unavailable") from exc

