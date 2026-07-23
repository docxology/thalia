#!/usr/bin/env python3
"""Thin orchestrator for the pre-registered ten-seed synthetic sensitivity lane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.evaluation import seed_sensitivity_eval  # noqa: E402


def main(output_path: str | Path | None = None, per_category: int = 10, n_boot: int = 2000) -> Path:
    """Generate the isolated sensitivity aggregate."""
    payload = seed_sensitivity_eval(per_category=per_category, n_boot=n_boot)
    target = Path(output_path) if output_path is not None else PROJECT_ROOT / "output" / "data" / "seed_sensitivity.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(target))
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--per-category", type=int, default=10)
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()
    main(args.output_path, args.per_category, args.n_boot)
