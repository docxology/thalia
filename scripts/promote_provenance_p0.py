#!/usr/bin/env python3
"""Explicitly promote an eligible P0 report after evidence revalidation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.evaluation.provenance_p0 import promote_p0_report  # noqa: E402


def main() -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    target = args.target if args.target.is_absolute() else PROJECT_ROOT / args.target
    result = promote_p0_report(
        args.report,
        target,
        evidence_root=args.evidence_root,
        acceptance_path=args.acceptance,
        overwrite=args.overwrite,
    )
    print(result)
    return result


if __name__ == "__main__":
    main()
