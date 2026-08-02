#!/usr/bin/env python3
"""Analyze bound P0 row/packet/key/label ledgers without promoting them."""

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

from src.evaluation.provenance_p0 import (  # noqa: E402
    P0Adjudication,
    P0BlindKey,
    P0BlindingManifest,
    P0BlindedPacket,
    P0Protocol,
    P0RunReceipt,
    P0RunRow,
    build_p0_provenance_report,
    load_p0_jsonl,
)


def _load_protocol(path: Path) -> P0Protocol:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read frozen P0 protocol: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("frozen P0 protocol must be a JSON object")
    return P0Protocol.from_dict(payload)


def main() -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--run-receipts", type=Path, required=True, help="Retained run-level receipt JSONL")
    parser.add_argument("--packets", type=Path, required=True, help="Retained blinded-packet JSONL shown to scorers")
    parser.add_argument("--blind-key", type=Path, required=True)
    parser.add_argument("--blinding-manifest", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True, help="Root resolving retained relative evidence paths")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = _load_protocol(args.protocol)
    rows = [P0RunRow.from_dict(row) for row in load_p0_jsonl(args.rows)]
    run_receipts = [P0RunReceipt.from_dict(row) for row in load_p0_jsonl(args.run_receipts)]
    packets = [P0BlindedPacket.from_dict(row) for row in load_p0_jsonl(args.packets)]
    keys = [P0BlindKey.from_dict(row) for row in load_p0_jsonl(args.blind_key)]
    blinding_manifest_payload = json.loads(args.blinding_manifest.read_text(encoding="utf-8"))
    if not isinstance(blinding_manifest_payload, dict):
        raise SystemExit("blinding manifest must be a JSON object")
    blinding_manifest = P0BlindingManifest.from_dict(blinding_manifest_payload)
    adjudications = [P0Adjudication.from_dict(row) for row in load_p0_jsonl(args.adjudications)]
    report = build_p0_provenance_report(
        protocol,
        rows,
        run_receipts,
        packets,
        keys,
        blinding_manifest,
        adjudications,
        evidence_root=args.evidence_root,
        source_paths={
            "protocol": args.protocol,
            "rows": args.rows,
            "run_receipts": args.run_receipts,
            "packets": args.packets,
            "blind_keys": args.blind_key,
            "blinding_manifest": args.blinding_manifest,
            "adjudications": args.adjudications,
        },
    )
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    report.write(output)
    print(output)
    return output


if __name__ == "__main__":
    main()
