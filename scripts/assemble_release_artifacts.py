#!/usr/bin/env python3
"""Assemble an explicitly reviewed frozen supplement; print its member receipt."""

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

from src.release_artifacts import (  # noqa: E402
    assemble_release_artifacts,
    load_release_allowlist,
)


def main(argv: list[str] | None = None) -> int:
    """Write the archive and emit a JSON receipt for external storage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True, help="Frozen source-plus-output stage")
    parser.add_argument("--allowlist", type=Path, required=True, help="Reviewed JSON array of project-relative files")
    parser.add_argument("--output", type=Path, required=True, help="New tar.gz destination; never overwritten")
    parser.add_argument("--prefix", default="", help="Optional canonical archive member prefix")
    args = parser.parse_args(argv)
    try:
        receipt = assemble_release_artifacts(
            args.project_root, load_release_allowlist(args.allowlist), args.output, prefix=args.prefix,
        )
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(1, f"assembly refused: {exc}\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
