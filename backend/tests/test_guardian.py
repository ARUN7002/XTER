import json
import unittest
from pathlib import Path
from uuid import uuid4

from backend.andrews.guardian import AuditLog, AuthorizationError, Guardian, OperatorSupervisor


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def make_guardian(clock=None, audit=None):
    guardian = Guardian(clock=clock or FakeClock(), heartbeat_timeout=5, audit_log=audit)
    lease = guardian.start_session(
        operator_id="operator-test",
        allowed_origins={"http://local.test"},
        allowed_actions={"read", "write"},
        max_tasks=2,
        max_corrections=1,
        max_actions=2,
        lease_seconds=20,
    )
    return guardian, lease


class GuardianTests(unittest.TestCase):
    def test_denies_without_permission_and_unknown_origin(self):
        guardian, lease = make_guardian()
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id="wrong", operator_id="operator-test", origin="http://local.test", action="read")
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id=lease.lease_id, operator_id="operator-test", origin="http://evil.test", action="read")

    def test_expired_permission_is_rejected(self):
        clock = FakeClock()
        guardian, lease = make_guardian(clock)
        clock.advance(21)
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id=lease.lease_id, operator_id="operator-test", origin="http://local.test", action="read")
        self.assertEqual(guardian.session.status, "STOPPED")

    def test_guardian_failure_via_heartbeat_stops_operator(self):
        clock = FakeClock()
        guardian, lease = make_guardian(clock)
        stopped = []
        supervisor = OperatorSupervisor(guardian, lambda: stopped.append(True))
        clock.advance(6)
        self.assertFalse(supervisor.check())
        self.assertEqual(stopped, [True])
        self.assertEqual(guardian.session.stop_reason, "operator heartbeat lost")

    def test_emergency_stop_blocks_future_actions(self):
        guardian, lease = make_guardian()
        guardian.emergency_stop(owner="owner", reason="manual test stop")
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id=lease.lease_id, operator_id="operator-test", origin="http://local.test", action="read")

    def test_operator_cannot_change_guardian_configuration(self):
        guardian, lease = make_guardian()
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id=lease.lease_id, operator_id="operator-test", origin="http://local.test", action="change_permissions")
        self.assertEqual(guardian.session.lease.max_actions, 2)

    def test_dashboard_is_not_required_for_guardian_operation(self):
        guardian, lease = make_guardian()
        guardian.authorize_action(lease_id=lease.lease_id, operator_id="operator-test", origin="http://local.test", action="read")
        self.assertEqual(guardian.session.action_count, 1)

    def test_audit_log_is_json_lines(self):
        directory = Path("work") / f"guardian-test-{uuid4().hex}"
        directory.mkdir(parents=True)
        path = directory / "audit.jsonl"
        try:
            guardian, lease = make_guardian(audit=AuditLog(path))
            guardian.emergency_stop(owner="owner", reason="test")
            events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        finally:
            for child in directory.iterdir():
                child.unlink()
            directory.rmdir()
        self.assertEqual(events[0]["event_type"], "SESSION_STARTED")
        self.assertEqual(events[-1]["event_type"], "EMERGENCY_STOP")


if __name__ == "__main__":
    unittest.main()

