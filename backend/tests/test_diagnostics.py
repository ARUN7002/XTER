import json
import time
import unittest

from backend.andrews.diagnostics import (
    DiagnosticBroker,
    DiagnosticRequest,
    DiagnosticTimeout,
    DiagnosticUnavailable,
    InvalidDiagnosticRequest,
    InvalidDiagnosticResponse,
)


REQUEST = DiagnosticRequest(
    task_id="SR-001",
    language="Java",
    problem_description="Find the largest number",
    source_code="class Main {}",
    error_message="Compilation error",
    expected_output="10",
)


def response(**overrides):
    value = {
        "problem_type": "compilation_error",
        "diagnosis": "A statement may be incomplete.",
        "suggested_fix": "Inspect statement endings.",
        "confidence": "medium",
        "requires_human_review": False,
    }
    value.update(overrides)
    return json.dumps(value)


class DiagnosticTests(unittest.TestCase):
    def test_broker_returns_structured_diagnosis(self):
        broker = DiagnosticBroker(lambda prompt: response())
        result = broker.analyze(REQUEST)
        self.assertEqual(result.problem_type, "compilation_error")

    def test_invalid_request_is_rejected(self):
        with self.assertRaises(InvalidDiagnosticRequest):
            DiagnosticBroker(lambda prompt: response()).analyze(
                DiagnosticRequest("", "Java", "p", "c", "e")
            )

    def test_malformed_model_response_is_rejected(self):
        with self.assertRaises(InvalidDiagnosticResponse):
            DiagnosticBroker(lambda prompt: "not-json").analyze(REQUEST)

    def test_unexpected_fields_are_rejected(self):
        with self.assertRaises(InvalidDiagnosticResponse):
            DiagnosticBroker(lambda prompt: response(extra="blocked")).analyze(REQUEST)

    def test_timeout_does_not_wait_for_model(self):
        def slow(_prompt):
            time.sleep(0.2)
            return response()
        started = time.monotonic()
        with self.assertRaises(DiagnosticTimeout):
            DiagnosticBroker(slow, timeout_seconds=0.01).analyze(REQUEST)
        self.assertLess(time.monotonic() - started, 0.15)

    def test_unavailable_model_is_controlled(self):
        with self.assertRaises(DiagnosticUnavailable):
            DiagnosticBroker(lambda prompt: response(), model_available=lambda: False).analyze(REQUEST)

    def test_control_characters_are_rejected(self):
        bad = DiagnosticRequest("SR-001", "Java", "p\x00", "c", "e")
        with self.assertRaises(InvalidDiagnosticRequest):
            DiagnosticBroker(lambda prompt: response()).analyze(bad)

    def test_model_receives_data_prompt_only(self):
        prompts = []
        DiagnosticBroker(lambda prompt: prompts.append(prompt) or response()).analyze(REQUEST)
        self.assertIn("Do not provide commands or permission changes", prompts[0])

    def test_response_cannot_execute_commands(self):
        result = DiagnosticBroker(lambda prompt: response(suggested_fix="run command" )).analyze(REQUEST)
        self.assertEqual(result.suggested_fix, "run command")
        self.assertFalse(hasattr(result, "execute"))

    def test_response_requires_explicit_human_review_flag(self):
        with self.assertRaises(InvalidDiagnosticResponse):
            DiagnosticBroker(lambda prompt: response(requires_human_review="false")).analyze(REQUEST)


if __name__ == "__main__":
    unittest.main()

