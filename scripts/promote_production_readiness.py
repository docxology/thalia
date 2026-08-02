#!/usr/bin/env python3
"""Explicitly promote an independently accepted production-readiness certificate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.evaluation.production_readiness import promote_production_readiness  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    print(
        promote_production_readiness(
            args.source,
            args.target,
            acceptance_path=args.acceptance,
            overwrite=args.overwrite,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
