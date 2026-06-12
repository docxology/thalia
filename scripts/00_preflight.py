#!/usr/bin/env python3
"""Thin orchestrator: preflight check that the ATLAS package imports and runs.

Imports the package, runs one harness turn on a demo example, and confirms the
output is well-formed. Exits non-zero on failure so the pipeline halts early.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.evaluation import build_demo_dataset  # noqa: E402
from src.harness import AutoHarness  # noqa: E402
from src.signatures import HarnessOutput  # noqa: E402


def main() -> int:
    """Run a single harness turn and validate the output shape."""
    example = build_demo_dataset()[0]
    out = AutoHarness().run(example)
    assert isinstance(out, HarnessOutput), "harness did not return a HarnessOutput"
    assert out.answer, "harness produced an empty answer"
    assert out.memory_written.turn_id == 0, "first turn id should be 0"
    print(
        f"[ok] preflight passed: category={out.task_category.value} "
        f"delivery={out.delivery_mode.value} cited={len(out.evidence_citations)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
