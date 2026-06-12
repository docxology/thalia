#!/usr/bin/env python3
"""Thin orchestrator: build the canonical deterministic ATLAS demo artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.demo import build_demo_artifacts  # noqa: E402


def main() -> dict[str, Path]:
    """Generate demo artifacts and print every output path."""
    paths = build_demo_artifacts(PROJECT_ROOT / "output")
    for path in paths.values():
        print(str(path))
    return paths


if __name__ == "__main__":
    main()
