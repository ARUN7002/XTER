import unittest

from backend.andrews.guardian import Guardian
from backend.andrews.operator import BrowserAttachment, BrowserState, Operator, OperatorScopeError, OperatorState


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.guardian = Guardian(heartbeat_timeout=5)
        self.lease = self.guardian.start_session(
            operator_id="operator-test",
            allowed_origins={"http://local.test"},
            allowed_actions={"read", "mouse", "keyboard"},
            max_tasks=1,
            max_corrections=1,
            max_actions=20,
        )
        self.operator = Operator(self.guardian, self.lease, operator_id="operator-test", vm_id="vm-test")
        self.operator.start()

    def attach(self):
        self.operator.attach_browser(BrowserAttachment("http://local.test", "/vm/profile", True))

    def test_operator_requires_dedicated_vm(self):
        with self.assertRaises(OperatorScopeError):
            self.operator.attach_browser(BrowserAttachment("http://local.test", "/host/profile", False))

    def test_unauthorized_origin_is_rejected(self):
        self.attach()
        with self.assertRaises(OperatorScopeError):
            self.operator.request_input(origin="http://evil.test", action="mouse")
        self.assertEqual(self.operator.state, OperatorState.PAUSED)

    def test_browser_crash_pauses_operator(self):
        self.attach()
        self.operator.set_browser_state(BrowserState.CRASHED)
        self.assertEqual(self.operator.state, OperatorState.PAUSED)
        with self.assertRaises(OperatorScopeError):
            self.operator.request_input(origin="http://local.test", action="mouse")

    def test_guardian_disconnect_stops_operator(self):
        self.attach()
        self.operator.guardian_disconnected()
        self.assertEqual(self.operator.state, OperatorState.STOPPED)

    def test_manual_takeover_revokes_input_before_control(self):
        self.attach()
        self.operator.take_control(owner="owner")
        self.assertEqual(self.operator.state, OperatorState.MANUAL_CONTROL)
        with self.assertRaises(OperatorScopeError):
            self.operator.request_input(origin="http://local.test", action="mouse")

    def test_resume_requires_explicit_owner_action(self):
        self.attach()
        self.operator.take_control(owner="owner")
        self.operator.resume(owner="owner")
        self.assertEqual(self.operator.state, OperatorState.READY)
        self.operator.request_input(origin="http://local.test", action="mouse")
        self.assertEqual(self.operator.state, OperatorState.RUNNING)

    def test_read_does_not_enable_host_access(self):
        self.attach()
        with self.assertRaises(OperatorScopeError):
            self.operator.request_input(origin="file:///C:/Users", action="read")


if __name__ == "__main__":
    unittest.main()

