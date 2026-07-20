#!/usr/bin/env python3
"""Thin orchestrator: validate the generated artifact manifest and refuse drift."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.provenance import validate_artifact_manifest  # noqa: E402


def main() -> int:
    """Validate the current output manifest and print every finding."""
    report = validate_artifact_manifest(PROJECT_ROOT)
    print(f"checked={report.checked} required={report.required} ok={report.ok}")
    for issue in report.issues:
        print(f"[error] {issue}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
