#!/usr/bin/env python3
"""Record a separate optional common-harness backend benchmark artifact."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.benchmark_cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
