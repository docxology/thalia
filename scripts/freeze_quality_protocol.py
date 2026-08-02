#!/usr/bin/env python3
"""Freeze a pilot-reviewed quality protocol before confirmation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.evaluation.accounting import file_provenance  # noqa: E402
from src.evaluation.quality import QualityProtocol, load_quality_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--pilot-report", type=Path, required=True)
    parser.add_argument("--rubric-version", required=True)
    parser.add_argument(
        "--rubric-json",
        type=Path,
        default=None,
        help="optional reviewed rubric mapping; defaults to the draft protocol rubric",
    )
    parser.add_argument("--primary-metric", default="correctness_full_rate")
    parser.add_argument("--threshold", action="append", default=[], help="name=value; repeat for each preregistered threshold")
    args = parser.parse_args(argv)
    thresholds: dict[str, float] = {}
    for item in args.threshold:
        if "=" not in item:
            raise ValueError(f"threshold must be name=value, got {item!r}")
        name, value = item.split("=", 1)
        if not name or name in thresholds:
            raise ValueError(f"threshold names must be non-empty and unique, got {name!r}")
        thresholds[name] = float(value)
    protocol = QualityProtocol.from_dict(json.loads(args.source.read_text(encoding="utf-8")))
    pilot_report = load_quality_report(args.pilot_report)
    if pilot_report.protocol_id != protocol.protocol_id or pilot_report.phase != "pilot":
        raise ValueError("pilot report must belong to this protocol and use the pilot phase")
    if pilot_report.status not in {"complete_not_promoted", "passed"}:
        raise ValueError("pilot report is incomplete or failed")
    blocking_issues = [issue for issue in pilot_report.issues if issue != "thresholds_not_frozen"]
    if blocking_issues:
        raise ValueError(f"pilot report has unresolved issues: {', '.join(blocking_issues)}")
    pilot_file = file_provenance(args.pilot_report)
    pilot_file["certificate_sha256"] = pilot_report.certificate_sha256
    pilot_protocol_sha256 = pilot_report.evidence_manifest.get("protocol_sha256")
    if not isinstance(pilot_protocol_sha256, str) or len(pilot_protocol_sha256) != 64:
        raise ValueError("pilot report must carry its source protocol digest")
    rubric = None
    if args.rubric_json is not None:
        rubric_payload = json.loads(args.rubric_json.read_text(encoding="utf-8"))
        if not isinstance(rubric_payload, dict):
            raise ValueError("--rubric-json must contain a JSON object")
        rubric = rubric_payload
    frozen = protocol.freeze(
        rubric_version=args.rubric_version,
        primary_metric=args.primary_metric,
        thresholds=thresholds,
        pilot_review_provenance={
            "report": pilot_file,
            "protocol_sha256": pilot_protocol_sha256,
            "status": pilot_report.status,
            "n_observations": pilot_report.n_observations,
            "n_annotations": pilot_report.n_annotations,
            "n_adjudications": pilot_report.n_adjudications,
        },
        rubric=rubric,
    )
    frozen.write(args.target)
    print(args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
