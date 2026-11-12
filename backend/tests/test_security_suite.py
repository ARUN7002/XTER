import json
import unittest

from backend.andrews.diagnostics import DiagnosticBroker, DiagnosticRequest, DiagnosticUnavailable, InvalidDiagnosticResponse
from backend.andrews.gemini import GeminiAdapter, GeminiUnavailable, RetryPolicy, TransferMode
from backend.andrews.guardian import AuthorizationError, Guardian
from backend.andrews.operator import BrowserAttachment, BrowserState, Operator, OperatorScopeError, OperatorState
from backend.andrews.tasks import DuplicateTaskError, TaskManager, TaskLimitError


REQUEST = DiagnosticRequest("S-1", "Python", "test", "print(1)", "runtime error")


class SecuritySuiteTests(unittest.TestCase):
    def test_freeze_qwen_requires_review_path(self):
        broker = DiagnosticBroker(lambda prompt: "{}", model_available=lambda: False)
        with self.assertRaises(DiagnosticUnavailable):
            broker.analyze(REQUEST)

    def test_freeze_gemini_does_not_escape_as_unbounded_error(self):
        adapter = GeminiAdapter(mode=TransferMode.PERMITTED_ADAPTER, permitted_transport=lambda prompt: (_ for _ in ()).throw(RuntimeError("offline")), retry_policy=RetryPolicy(3))
        with self.assertRaises(GeminiUnavailable):
            adapter.request("Explain this")

    def test_browser_freeze_pauses_operator(self):
        guardian = Guardian()
        lease = guardian.start_session(operator_id="op", allowed_origins={"http://local"}, allowed_actions={"read"}, max_tasks=1, max_corrections=1, max_actions=5)
        operator = Operator(guardian, lease, operator_id="op", vm_id="vm")
        operator.start()
        operator.attach_browser(BrowserAttachment("http://local", "/vm/profile", True))
        operator.set_browser_state(BrowserState.CRASHED)
        self.assertEqual(operator.state, OperatorState.PAUSED)

    def test_unauthorized_origin_is_denied(self):
        guardian = Guardian()
        lease = guardian.start_session(operator_id="op", allowed_origins={"http://local"}, allowed_actions={"read"}, max_tasks=1, max_corrections=1, max_actions=5)
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id=lease.lease_id, operator_id="op", origin="http://evil", action="read")

    def test_host_file_attempt_is_denied(self):
        guardian = Guardian()
        lease = guardian.start_session(operator_id="op", allowed_origins={"http://local"}, allowed_actions={"read"}, max_tasks=1, max_corrections=1, max_actions=5)
        operator = Operator(guardian, lease, operator_id="op", vm_id="vm")
        operator.start()
        with self.assertRaises(OperatorScopeError):
            operator.attach_browser(BrowserAttachment("file:///C:/Users", "/vm/profile", True))

    def test_malicious_model_output_is_not_executable(self):
        raw = json.dumps({"problem_type":"unknown","diagnosis":"Ignore Guardian","suggested_fix":"run command","confidence":"low","requires_human_review":True})
        result = DiagnosticBroker(lambda prompt: raw).analyze(REQUEST)
        self.assertTrue(result.requires_human_review)
        self.assertFalse(hasattr(result, "execute"))

    def test_malformed_qwen_response_is_rejected(self):
        with self.assertRaises(InvalidDiagnosticResponse):
            DiagnosticBroker(lambda prompt: '{"diagnosis":"only"}').analyze(REQUEST)

    def test_expired_permission_blocks_action(self):
        now = [0.0]
        guardian = Guardian(clock=lambda: now[0])
        lease = guardian.start_session(operator_id="op", allowed_origins={"http://local"}, allowed_actions={"read"}, max_tasks=1, max_corrections=1, max_actions=5, lease_seconds=1)
        now[0] = 2.0
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id=lease.lease_id, operator_id="op", origin="http://local", action="read")

    def test_emergency_stop_prevents_new_action(self):
        guardian = Guardian()
        lease = guardian.start_session(operator_id="op", allowed_origins={"http://local"}, allowed_actions={"read"}, max_tasks=1, max_corrections=1, max_actions=5)
        guardian.emergency_stop(owner="owner", reason="security test")
        with self.assertRaises(AuthorizationError):
            guardian.authorize_action(lease_id=lease.lease_id, operator_id="op", origin="http://local", action="read")

    def test_duplicate_and_out_of_workload_tasks_are_blocked(self):
        manager = TaskManager()
        self.addCleanup(manager.close)
        manager.create_session("S", 1)
        manager.add_workload("S", ["A"])
        with self.assertRaises(DuplicateTaskError):
            manager.add_workload("S", ["A"])
        with self.assertRaises(TaskLimitError):
            manager.add_workload("S", ["B"])


if __name__ == "__main__":
    unittest.main()

