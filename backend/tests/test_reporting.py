import os
import unittest
from pathlib import Path
from uuid import uuid4

from backend.andrews.reporting import (
    DiagnosticRecord,
    ReportError,
    ReportGenerator,
    ReportTask,
    VerifiedFixKnowledgeBase,
    cleanup_old_files,
)


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.task = ReportTask("T-1", "ref-1", "VERIFIED", "local_test", "passed")

    def test_html_report_escapes_untrusted_text(self):
        report = ReportGenerator().html_report(session_id="S-1<script>", tasks=[ReportTask("T", "<x>", "FAILED", "AI suggestion", "bad & text")])
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("AI suggestion", report)

    def test_csv_contains_task_and_verification_columns(self):
        csv_text = ReportGenerator().csv_tasks([self.task])
        self.assertIn("task_id,reference,status,verification_source,summary", csv_text)
        self.assertIn("T-1,ref-1,VERIFIED,local_test,passed", csv_text)

    def test_html_includes_diagnostics_and_errors(self):
        report = ReportGenerator().html_report(
            session_id="S-1", tasks=[self.task],
            diagnostics=[DiagnosticRecord("T-1", "runtime_error", "bad input", "medium", True)],
            errors=[ReportError("now", "operator", "AMBER", "browser paused")],
        )
        self.assertIn("bad input", report)
        self.assertIn("browser paused", report)
        self.assertIn("yes", report)

    def test_knowledge_base_rejects_ai_only_fix(self):
        kb = VerifiedFixKnowledgeBase()
        self.addCleanup(kb.close)
        with self.assertRaises(ValueError):
            kb.add(problem_type="runtime_error", symptom="x", fix="y", verification_source="ai_generated")

    def test_knowledge_base_stores_verified_fix(self):
        kb = VerifiedFixKnowledgeBase()
        self.addCleanup(kb.close)
        kb.add(problem_type="runtime_error", symptom="null", fix="check value", verification_source="local_test")
        self.assertEqual(kb.search("runtime_error"), [("null", "check value", "local_test")])

    def test_cleanup_is_scoped_and_keeps_recent_files(self):
        directory = Path("work") / f"report-test-{uuid4().hex}"
        directory.mkdir(parents=True)
        old_log = directory / "old.log"
        new_log = directory / "new.log"
        keep = directory / "keep.txt"
        try:
            old_log.write_text("old", encoding="utf-8")
            new_log.write_text("new", encoding="utf-8")
            keep.write_text("keep", encoding="utf-8")
            os.utime(old_log, (0, 0))
            removed = cleanup_old_files(directory, older_than_seconds=10, now=100)
            self.assertEqual(removed, [old_log])
            self.assertFalse(old_log.exists())
            self.assertTrue(new_log.exists())
            self.assertTrue(keep.exists())
        finally:
            for child in directory.iterdir():
                child.unlink()
            directory.rmdir()


if __name__ == "__main__":
    unittest.main()

