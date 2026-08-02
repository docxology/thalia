#!/usr/bin/env python3
"""Create separated keyed P0 adjudication packets, an internal key, and receipt.

The packet file can be shown to expert scorers.  Keep the key file internal: it
restores the raw condition rows after annotation and must never be sent with a
blinded packet bundle. The sealed receipt commits to the packet/key bundle and
a hash of the private blinding salt for later audit.
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

from src.evaluation.provenance_p0 import (  # noqa: E402
    P0Protocol,
    P0RunRow,
    create_p0_blinded_packets,
    create_p0_blinding_manifest,
    load_p0_jsonl,
    write_p0_jsonl,
)


def main() -> tuple[Path, Path, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True, help="Immutable P0 raw-row JSONL")
    parser.add_argument("--packets", type=Path, required=True, help="Blinded scorer packet JSONL")
    parser.add_argument("--blind-key", type=Path, required=True, help="Internal key JSONL; do not distribute")
    parser.add_argument("--blinding-manifest", type=Path, required=True, help="Sealed packet/key receipt retained for audit")
    parser.add_argument("--blind-salt", required=True, help="Secret stable salt for this adjudication packet set")
    args = parser.parse_args()
    protocol = P0Protocol.from_dict(json.loads(args.protocol.read_text(encoding="utf-8")))
    rows = [P0RunRow.from_dict(row) for row in load_p0_jsonl(args.rows)]
    packets, keys = create_p0_blinded_packets(protocol, rows, blind_salt=args.blind_salt)
    packets_path = args.packets if args.packets.is_absolute() else PROJECT_ROOT / args.packets
    key_path = args.blind_key if args.blind_key.is_absolute() else PROJECT_ROOT / args.blind_key
    manifest_path = args.blinding_manifest if args.blinding_manifest.is_absolute() else PROJECT_ROOT / args.blinding_manifest
    write_p0_jsonl(packets_path, (packet.to_dict() for packet in packets))
    write_p0_jsonl(key_path, (key.to_dict() for key in keys))
    create_p0_blinding_manifest(protocol, rows, packets, keys, blind_salt=args.blind_salt).write(manifest_path)
    print(packets_path)
    print(key_path)
    print(manifest_path)
    return packets_path, key_path, manifest_path


if __name__ == "__main__":
    main()
