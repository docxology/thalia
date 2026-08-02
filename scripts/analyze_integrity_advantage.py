#!/usr/bin/env python3
"""Thin orchestrator for the current integrity-advantage evidence screen.

The compiler-generalization aggregate must exist before this report is built.
Analysis and statistical logic live in ``src/evaluation/integrity_advantage.py``;
this script only resolves paths, serializes the report, and prints its location.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.evaluation.integrity_advantage import build_integrity_advantage_report  # noqa: E402


def main() -> Path:
    """Build and write the source-bound report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "integrity_advantage.json",
        help="JSON destination; defaults to data/integrity_advantage.json",
    )
    args = parser.parse_args()
    output_path = args.output_path if args.output_path.is_absolute() else PROJECT_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_integrity_advantage_report(PROJECT_ROOT)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output_path)
    return output_path


if __name__ == "__main__":
    main()
