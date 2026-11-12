import unittest

from backend.andrews.tasks import (
    DuplicateTaskError,
    InvalidTaskTransition,
    TaskManager,
    TaskLimitError,
    TaskStatus,
)


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.manager = TaskManager(clock=self.clock, max_workload_limit=5)
        self.manager.create_session("S-1", 2, task_deadline_seconds=10, max_corrections=2)

    def tearDown(self):
        self.manager.close()

    def test_workload_limit_and_duplicate_detection(self):
        self.manager.add_workload("S-1", ["A", "B"])
        with self.assertRaises(DuplicateTaskError):
            self.manager.add_workload("S-1", ["B"])
        with self.assertRaises(TaskLimitError):
            self.manager.add_workload("S-1", ["C"])

    def test_queue_and_status_transition(self):
        ids = self.manager.add_workload("S-1", ["A", "B"])
        task = self.manager.start_next("S-1")
        self.assertEqual(task.id, ids[0])
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
        self.assertEqual(self.manager.history(task.id), [("PENDING", "IN_PROGRESS")])

    def test_invalid_status_transition_rejected(self):
        self.manager.add_workload("S-1", ["A"])
        task = self.manager.start_next("S-1")
        with self.assertRaises(InvalidTaskTransition):
            self.manager.transition(task.id, TaskStatus.PENDING, reason="backwards")

    def test_correction_limit_enforced(self):
        self.manager.add_workload("S-1", ["A"])
        task = self.manager.start_next("S-1")
        self.manager.record_correction(task.id)
        self.manager.record_correction(task.id)
        with self.assertRaises(TaskLimitError):
            self.manager.record_correction(task.id)

    def test_deadline_moves_task_to_review(self):
        self.manager.add_workload("S-1", ["A"])
        task = self.manager.start_next("S-1")
        self.clock.advance(11)
        self.assertEqual(self.manager.enforce_deadlines("S-1"), 1)
        self.assertEqual(self.manager.get_task(task.id).status, TaskStatus.NEEDS_REVIEW)

    def test_verified_requires_independent_evidence(self):
        self.manager.add_workload("S-1", ["A"])
        task = self.manager.start_next("S-1")
        with self.assertRaises(InvalidTaskTransition):
            self.manager.transition(task.id, TaskStatus.VERIFIED, reason="ai answer", verification_evidence="AI generated")
        verified = self.manager.transition(task.id, TaskStatus.VERIFIED, reason="local test", verification_evidence="local test passed")
        self.assertEqual(verified.status, TaskStatus.VERIFIED)

    def test_checkpoint_is_persisted(self):
        self.manager.add_workload("S-1", ["A"])
        task = self.manager.start_next("S-1")
        self.manager.checkpoint("S-1", task.id, '{"step":"started"}')
        row = self.manager._db.execute("SELECT payload FROM checkpoints WHERE task_id = ?", (task.id,)).fetchone()
        self.assertEqual(row[0], '{"step":"started"}')

    def test_interruption_does_not_silently_resume(self):
        self.manager.add_workload("S-1", ["A"])
        task = self.manager.start_next("S-1")
        self.assertEqual(self.manager.interrupt_session("S-1"), 1)
        self.assertEqual(self.manager.get_task(task.id).status, TaskStatus.INTERRUPTED)
        self.assertIsNone(self.manager.start_next("S-1"))

    def test_attempt_history_is_preserved(self):
        self.manager.add_workload("S-1", ["A"])
        task = self.manager.start_next("S-1")
        self.manager.transition(task.id, TaskStatus.NEEDS_REVIEW, reason="error")
        self.manager.transition(task.id, TaskStatus.IN_PROGRESS, reason="owner resumed")
        self.assertEqual(self.manager.history(task.id), [("PENDING", "IN_PROGRESS"), ("IN_PROGRESS", "NEEDS_REVIEW"), ("NEEDS_REVIEW", "IN_PROGRESS")])


if __name__ == "__main__":
    unittest.main()

