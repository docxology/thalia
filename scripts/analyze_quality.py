#!/usr/bin/env python3
"""Aggregate blinded quality annotations into a fail-closed report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.evaluation.quality import (  # noqa: E402
    QualityAdjudication,
    QualityAnnotation,
    QualityObservation,
    QualityProtocol,
    build_quality_report,
    load_jsonl,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--phase", choices=("pilot", "confirmatory"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, default=None, help="root containing raw/<condition>/<question>.json files")
    args = parser.parse_args(argv)
    protocol = QualityProtocol.from_dict(json.loads(args.protocol.read_text(encoding="utf-8")))
    observations = load_jsonl(args.observations, QualityObservation.from_dict)
    annotations = load_jsonl(args.annotations, QualityAnnotation.from_dict)
    adjudications = load_jsonl(args.adjudications, QualityAdjudication.from_dict)
    evidence_root = args.evidence_root or args.observations.parent
    report = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase=args.phase,
        provenance={
            "protocol_path": str(args.protocol),
            "observations_path": str(args.observations),
            "annotations_path": str(args.annotations),
            "adjudications_path": str(args.adjudications),
        },
        evidence_root=evidence_root,
    )
    report.write(args.output)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.status in {"complete_not_promoted", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
