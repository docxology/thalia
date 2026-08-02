#!/usr/bin/env python3
"""Freeze a reviewed P0 provenance protocol draft into canonical JSON.

The draft must already declare all source records, the 120 attack probes plus
clean controls, safety margins, a held-out-family admission, and an independently
admitted rerun record.
This script has no experiment logic; it only validates and serializes the
protocol digest used by external raw rows.
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

from src.evaluation.provenance_p0 import P0Protocol  # noqa: E402


def main() -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path, help="Unsigned reviewed P0 protocol draft JSON")
    parser.add_argument("output", type=Path, help="Frozen protocol JSON destination")
    args = parser.parse_args()
    try:
        payload = json.loads(args.draft.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read P0 protocol draft: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("P0 protocol draft must be a JSON object")
    protocol = P0Protocol.from_draft_dict(payload)
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    protocol.write(output)
    print(output)
    return output


if __name__ == "__main__":
    main()
