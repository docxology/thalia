#!/usr/bin/env python3
"""Thin orchestrator for held-out MIPRO-/GEPA-style validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.evaluation import (  # noqa: E402
    DEFAULT_COMPILER_GENERALIZATION_SEEDS,
    compiler_generalization_eval,
)


def main(
    output_path: str | Path | None = None,
    per_category: int = 4,
    gepa_iterations: int = 4,
    seeds: tuple[int, ...] | None = None,
) -> Path:
    """Generate the isolated held-out compiler aggregate."""
    payload = compiler_generalization_eval(
        per_category=per_category,
        gepa_iterations=gepa_iterations,
        seeds=seeds if seeds is not None else DEFAULT_COMPILER_GENERALIZATION_SEEDS,
    )
    target = Path(output_path) if output_path is not None else PROJECT_ROOT / "output" / "data" / "compiler_generalization.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(target))
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--per-category", type=int, default=4)
    parser.add_argument("--gepa-iterations", type=int, default=4)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        metavar="SEED",
        help="independent task seeds; defaults to the quick five-seed smoke grid",
    )
    args = parser.parse_args()
    main(
        args.output_path,
        args.per_category,
        args.gepa_iterations,
        tuple(args.seeds) if args.seeds is not None else None,
    )
