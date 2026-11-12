"""Safe HTML/CSV reporting and verified-fix knowledge base for Phase 7."""

from __future__ import annotations

import csv
import html
import io
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def safe_text(value: str | None, limit: int = 8_000) -> str:
    text = _CONTROL_CHARS.sub("", value or "").strip()
    return text[:limit]


@dataclass(frozen=True)
class ReportTask:
    task_id: str
    reference: str
    status: str
    verification_source: str
    summary: str = ""


@dataclass(frozen=True)
class DiagnosticRecord:
    task_id: str
    problem_type: str
    diagnosis: str
    confidence: str
    human_review_required: bool


@dataclass(frozen=True)
class ReportError:
    timestamp: str
    component: str
    severity: str
    message: str


class ReportGenerator:
    def html_report(
        self,
        *,
        session_id: str,
        tasks: Iterable[ReportTask],
        diagnostics: Iterable[DiagnosticRecord] = (),
        errors: Iterable[ReportError] = (),
    ) -> str:
        task_rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(safe_text(value))}</td>" for value in (
                task.task_id, task.reference, task.status, task.verification_source, task.summary
            )) + "</tr>"
            for task in tasks
        )
        diagnostic_rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(safe_text(value))}</td>" for value in (
                record.task_id, record.problem_type, record.diagnosis, record.confidence,
                "yes" if record.human_review_required else "no",
            )) + "</tr>"
            for record in diagnostics
        )
        error_rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(safe_text(value))}</td>" for value in (
                error.timestamp, error.component, error.severity, error.message,
            )) + "</tr>"
            for error in errors
        )
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>ANDREWS session {html.escape(safe_text(session_id))}</title>
<style>body{{font-family:system-ui;max-width:1100px;margin:2rem auto}} table{{border-collapse:collapse;width:100%;margin-bottom:2rem}} th,td{{border:1px solid #bbb;padding:.4rem;text-align:left}} th{{background:#eee}}</style></head>
<body><h1>ANDREWS session report</h1><p>Session: <code>{html.escape(safe_text(session_id))}</code></p>
<h2>Tasks</h2><table><tr><th>ID</th><th>Reference</th><th>Status</th><th>Verification source</th><th>Summary</th></tr>{task_rows}</table>
<h2>Diagnostics</h2><table><tr><th>Task</th><th>Type</th><th>Diagnosis</th><th>Confidence</th><th>Human review</th></tr>{diagnostic_rows}</table>
<h2>Errors</h2><table><tr><th>Timestamp</th><th>Component</th><th>Severity</th><th>Message</th></tr>{error_rows}</table>
</body></html>"""

    def csv_tasks(self, tasks: Iterable[ReportTask]) -> str:
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(("task_id", "reference", "status", "verification_source", "summary"))
        for task in tasks:
            writer.writerow((safe_text(task.task_id), safe_text(task.reference), safe_text(task.status), safe_text(task.verification_source), safe_text(task.summary)))
        return output.getvalue()

    def write_html(self, path: Path, **kwargs: object) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.html_report(**kwargs), encoding="utf-8")
        return path

    def write_csv(self, path: Path, tasks: Iterable[ReportTask]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.csv_tasks(tasks), encoding="utf-8", newline="")
        return path


class VerifiedFixKnowledgeBase:
    """Stores only independently verified fixes, never AI-only suggestions."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db = sqlite3.connect(db_path)
        self._db.execute("CREATE TABLE IF NOT EXISTS fixes (id INTEGER PRIMARY KEY, problem_type TEXT, symptom TEXT, fix TEXT, verification_source TEXT, created_at REAL)")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def add(self, *, problem_type: str, symptom: str, fix: str, verification_source: str) -> int:
        source = safe_text(verification_source).lower()
        if source not in {"local_test", "owner_review", "independent_check"}:
            raise ValueError("knowledge-base entries require independent verification")
        cursor = self._db.execute(
            "INSERT INTO fixes(problem_type, symptom, fix, verification_source, created_at) VALUES (?, ?, ?, ?, ?)",
            (safe_text(problem_type), safe_text(symptom), safe_text(fix), source, time.time()),
        )
        self._db.commit()
        return cursor.lastrowid

    def search(self, problem_type: str) -> list[tuple[str, str, str]]:
        return [(row[0], row[1], row[2]) for row in self._db.execute("SELECT symptom, fix, verification_source FROM fixes WHERE problem_type = ? ORDER BY id DESC", (safe_text(problem_type),))]


def cleanup_old_files(directory: Path, *, older_than_seconds: float, allowed_suffixes: tuple[str, ...] = (".log", ".csv", ".html"), now: float | None = None) -> list[Path]:
    """Remove only old files directly under an explicitly supplied report/log directory."""
    if not directory.is_dir() or older_than_seconds < 0:
        raise ValueError("cleanup directory or age is invalid")
    cutoff = (time.time() if now is None else now) - older_than_seconds
    removed: list[Path] = []
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in allowed_suffixes and path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path)
    return removed

