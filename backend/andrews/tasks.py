"""SQLite-backed workload and task state machine for Phase 3."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Iterable


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class TaskManagerError(RuntimeError):
    pass


class DuplicateTaskError(TaskManagerError):
    pass


class InvalidTaskTransition(TaskManagerError):
    pass


class TaskLimitError(TaskManagerError):
    pass


@dataclass(frozen=True)
class Task:
    id: int
    session_id: str
    task_reference: str
    status: TaskStatus
    attempt_count: int
    created_at: float
    started_at: float | None
    completed_at: float | None
    deadline_at: float | None
    verification_evidence: str | None


ALLOWED_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.SKIPPED, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {
        TaskStatus.NEEDS_REVIEW, TaskStatus.VERIFIED, TaskStatus.FAILED,
        TaskStatus.SKIPPED, TaskStatus.CANCELLED, TaskStatus.INTERRUPTED,
    },
    TaskStatus.NEEDS_REVIEW: {TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.INTERRUPTED: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
    TaskStatus.VERIFIED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.SKIPPED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskManager:
    def __init__(self, db_path: str = ":memory:", *, clock: Callable[[], float] = time.time, max_workload_limit: int = 1000) -> None:
        if max_workload_limit <= 0:
            raise ValueError("max_workload_limit must be positive")
        self._clock = clock
        self._max_workload_limit = max_workload_limit
        self._db = sqlite3.connect(db_path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self._db.close()

    def create_session(self, session_id: str, workload_limit: int, *, task_deadline_seconds: float = 600.0, max_corrections: int = 3) -> None:
        if not session_id.strip() or not 0 < workload_limit <= self._max_workload_limit:
            raise TaskLimitError("session ID or workload limit is invalid")
        if task_deadline_seconds <= 0 or not 0 <= max_corrections <= 10:
            raise TaskLimitError("task deadline or correction limit is invalid")
        try:
            self._db.execute(
                "INSERT INTO sessions(id, workload_limit, task_deadline_seconds, max_corrections, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, workload_limit, task_deadline_seconds, max_corrections, self._clock()),
            )
            self._db.commit()
        except sqlite3.IntegrityError as exc:
            raise TaskManagerError("session already exists") from exc

    def add_workload(self, session_id: str, task_references: Iterable[str]) -> list[int]:
        references = [reference.strip() for reference in task_references]
        if not references or any(not reference for reference in references):
            raise TaskManagerError("task references must not be empty")
        if len(set(references)) != len(references):
            raise DuplicateTaskError("duplicate task reference in workload")
        session = self._session(session_id)
        current_count = self._db.execute("SELECT COUNT(*) FROM tasks WHERE session_id = ?", (session_id,)).fetchone()[0]
        existing = self._db.execute(
            "SELECT task_reference FROM tasks WHERE session_id = ? AND task_reference IN ({})".format(",".join("?" * len(references))),
            (session_id, *references),
        ).fetchall()
        if existing:
            raise DuplicateTaskError("task reference already exists")
        if current_count + len(references) > session["workload_limit"]:
            raise TaskLimitError("workload exceeds owner-approved limit")
        now = self._clock()
        cursor = self._db.cursor()
        cursor.executemany(
            "INSERT INTO tasks(session_id, task_reference, status, attempt_count, created_at) VALUES (?, ?, ?, 0, ?)",
            [(session_id, reference, TaskStatus.PENDING.value, now) for reference in references],
        )
        self._db.commit()
        return [row[0] for row in self._db.execute("SELECT id FROM tasks WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, len(references))).fetchall()][::-1]

    def start_next(self, session_id: str) -> Task | None:
        session = self._session(session_id)
        row = self._db.execute("SELECT * FROM tasks WHERE session_id = ? AND status = ? ORDER BY id LIMIT 1", (session_id, TaskStatus.PENDING.value)).fetchone()
        if row is None:
            return None
        now = self._clock()
        deadline = now + session["task_deadline_seconds"]
        self._transition(row["id"], TaskStatus.IN_PROGRESS, reason="task started", deadline_at=deadline)
        return self.get_task(row["id"])

    def transition(self, task_id: int, target: TaskStatus, *, reason: str, verification_evidence: str | None = None) -> Task:
        self._transition(task_id, target, reason=reason, verification_evidence=verification_evidence)
        return self.get_task(task_id)

    def record_correction(self, task_id: int) -> Task:
        task = self.get_task(task_id)
        session = self._session(task.session_id)
        if task.status not in {TaskStatus.IN_PROGRESS, TaskStatus.NEEDS_REVIEW}:
            raise TaskManagerError("corrections are allowed only for active or review tasks")
        if task.attempt_count >= session["max_corrections"]:
            raise TaskLimitError("correction limit exceeded")
        self._db.execute("UPDATE tasks SET attempt_count = attempt_count + 1 WHERE id = ?", (task_id,))
        self._db.commit()
        return self.get_task(task_id)

    def checkpoint(self, session_id: str, task_id: int | None, payload: str) -> None:
        self._session(session_id)
        if not payload.strip() or len(payload) > 16_000:
            raise TaskManagerError("checkpoint payload is invalid")
        if task_id is not None:
            task = self.get_task(task_id)
            if task.session_id != session_id:
                raise TaskManagerError("task does not belong to session")
        self._db.execute("INSERT INTO checkpoints(session_id, task_id, payload, created_at) VALUES (?, ?, ?, ?)", (session_id, task_id, payload, self._clock()))
        self._db.commit()

    def interrupt_session(self, session_id: str, reason: str = "session interrupted") -> int:
        self._session(session_id)
        rows = self._db.execute("SELECT id FROM tasks WHERE session_id = ? AND status = ?", (session_id, TaskStatus.IN_PROGRESS.value)).fetchall()
        for row in rows:
            self._transition(row["id"], TaskStatus.INTERRUPTED, reason=reason)
        return len(rows)

    def enforce_deadlines(self, session_id: str) -> int:
        self._session(session_id)
        now = self._clock()
        rows = self._db.execute("SELECT id FROM tasks WHERE session_id = ? AND status = ? AND deadline_at <= ?", (session_id, TaskStatus.IN_PROGRESS.value, now)).fetchall()
        for row in rows:
            self._transition(row["id"], TaskStatus.NEEDS_REVIEW, reason="task deadline exceeded")
        return len(rows)

    def get_task(self, task_id: int) -> Task:
        row = self._db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskManagerError("unknown task")
        return Task(row["id"], row["session_id"], row["task_reference"], TaskStatus(row["status"]), row["attempt_count"], row["created_at"], row["started_at"], row["completed_at"], row["deadline_at"], row["verification_evidence"])

    def history(self, task_id: int) -> list[tuple[str, str]]:
        self.get_task(task_id)
        return [(row["from_status"], row["to_status"]) for row in self._db.execute("SELECT from_status, to_status FROM task_history WHERE task_id = ? ORDER BY id", (task_id,))]

    def _transition(self, task_id: int, target: TaskStatus, *, reason: str, deadline_at: float | None = None, verification_evidence: str | None = None) -> None:
        task = self.get_task(task_id)
        if target not in ALLOWED_TRANSITIONS[task.status]:
            raise InvalidTaskTransition(f"{task.status} -> {target} is not allowed")
        if target == TaskStatus.VERIFIED and not verification_evidence:
            raise InvalidTaskTransition("VERIFIED requires independent verification evidence")
        if target == TaskStatus.VERIFIED and verification_evidence.lower().startswith("ai"):
            raise InvalidTaskTransition("AI-generated output is not verification evidence")
        now = self._clock()
        completed_at = now if target in {TaskStatus.VERIFIED, TaskStatus.FAILED, TaskStatus.SKIPPED, TaskStatus.CANCELLED} else None
        self._db.execute(
            "UPDATE tasks SET status = ?, started_at = COALESCE(started_at, ?), completed_at = ?, deadline_at = ?, verification_evidence = COALESCE(?, verification_evidence) WHERE id = ?",
            (target.value, now if target == TaskStatus.IN_PROGRESS else task.started_at, completed_at, deadline_at, verification_evidence, task_id),
        )
        self._db.execute("INSERT INTO task_history(task_id, from_status, to_status, reason, created_at) VALUES (?, ?, ?, ?, ?)", (task_id, task.status.value, target.value, reason, now))
        self._db.commit()

    def _session(self, session_id: str) -> sqlite3.Row:
        row = self._db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise TaskManagerError("unknown session")
        return row

    def _create_schema(self) -> None:
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, workload_limit INTEGER NOT NULL,
                task_deadline_seconds REAL NOT NULL, max_corrections INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                task_reference TEXT NOT NULL, status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL,
                started_at REAL, completed_at REAL, deadline_at REAL,
                verification_evidence TEXT,
                UNIQUE(session_id, task_reference),
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
                from_status TEXT NOT NULL, to_status TEXT NOT NULL,
                reason TEXT NOT NULL, created_at REAL NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                task_id INTEGER, payload TEXT NOT NULL, created_at REAL NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
        """)
        self._db.commit()

