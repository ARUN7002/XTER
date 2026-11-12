"""Validated runtime configuration for ANDREWS."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})
VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})


@dataclass(frozen=True)
class Settings:
    data_root: Path
    log_level: str
    environment: str

    @classmethod
    def from_environment(cls) -> "Settings":
        raw_root = os.getenv("ANDREWS_DATA_ROOT", r"E:\ANDREWS").strip()
        if not raw_root:
            raise ValueError("ANDREWS_DATA_ROOT must not be empty")

        log_level = os.getenv("ANDREWS_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in VALID_LOG_LEVELS:
            raise ValueError(f"Unsupported ANDREWS_LOG_LEVEL: {log_level}")

        environment = os.getenv("ANDREWS_ENVIRONMENT", "development").strip().lower()
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError(f"Unsupported ANDREWS_ENVIRONMENT: {environment}")

        return cls(Path(raw_root), log_level, environment)

    def required_directories(self) -> tuple[Path, ...]:
        names = (
            "application", "guardian", "operator", "dashboard", "intelligence",
            "workload", "monitoring", "permissions", "tests", "reports",
            "database", "logs", "backups", "models", "vm",
        )
        return tuple(self.data_root / name for name in names)

