"""Minimal Phase 0 command-line entry point."""

from __future__ import annotations

import argparse

from .config import Settings
from .logging import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(prog="andrews")
    parser.add_argument("command", choices=("check-config",))
    args = parser.parse_args()
    settings = Settings.from_environment()
    logger = configure_logging(settings.log_level)
    if args.command == "check-config":
        logger.info("configuration validated for %s", settings.environment)
        print(f"data_root={settings.data_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

