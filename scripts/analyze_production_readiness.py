#!/usr/bin/env python3
"""Aggregate operational acceptance observations without using model-quality evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.evaluation.production_readiness import (  # noqa: E402
    ProductionControls,
    ProductionObservation,
    ProductionReadinessProtocol,
    build_production_readiness_report,
)
from src.evaluation.quality import load_jsonl  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protocol = ProductionReadinessProtocol.from_dict(json.loads(args.protocol.read_text(encoding="utf-8")))
    observations = load_jsonl(args.observations, ProductionObservation.from_dict)
    controls = ProductionControls.from_dict(json.loads(args.controls.read_text(encoding="utf-8")))
    report = build_production_readiness_report(
        protocol,
        observations,
        controls,
        provenance={"protocol_path": str(args.protocol), "observations_path": str(args.observations)},
    )
    report.write(args.output)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.status in {"ready", "complete_not_ready", "pending_evidence"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
