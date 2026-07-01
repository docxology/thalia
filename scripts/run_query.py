#!/usr/bin/env python3
"""Thin orchestrator: run a single query against the THALIA harness from the CLI.

All logic lives in ``src/cli.py``; this wrapper only sets up the import path and
delegates. Example:

    uv run --project working/thalia python working/thalia/scripts/run_query.py \\
        --query "What is the wifi password?" \\
        --session-history "User: my wifi password is bluefish42" --json
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
