#!/usr/bin/env python3
"""Thin runner for the THALIA v2 live research campaign.

All cohort, checkpoint, metric, and promotion logic lives in
``src.evaluation.campaign``.  Raw campaign material defaults to the external
volume so the repository keeps only validated aggregate evidence.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.dspy_runtime import ollama_model_metadata  # noqa: E402
from src.evaluation.campaign import (  # noqa: E402
    CampaignSpec,
    CampaignTier,
    promote_campaign_report,
    run_campaign,
)
from src.evaluation.longmemeval import load_longmemeval  # noqa: E402


DEFAULT_CAMPAIGN_ROOT = Path(
    os.environ.get("THALIA_CAMPAIGN_ROOT", Path.home() / "thalia_external" / "campaigns")
)
DEFAULT_BENCHMARK = PROJECT_ROOT / "data" / "longmemeval" / "longmemeval_s.json"


def build_default_spec(*, campaign_id: str, benchmark_path: Path, max_consecutive_failures: int) -> CampaignSpec:
    """Return the pre-registered Gemma-primary/Hermes-sensitivity matrix."""
    return CampaignSpec(
        campaign_id=campaign_id,
        benchmark_path=benchmark_path,
        tiers=(
            CampaignTier("gemma-100", 100, "gemma3:4b", policy="default"),
            CampaignTier("gemma-250", 250, "gemma3:4b", policy="default"),
            CampaignTier("gemma-500", 500, "gemma3:4b", policy="default"),
            CampaignTier("hermes-100", 100, "hermes3:latest", policy="sensitivity"),
        ),
        max_consecutive_failures=max_consecutive_failures,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the resumable THALIA v2 live campaign.")
    parser.add_argument("--campaign-id", default="thalia-v2-longmemeval", help="isolated campaign directory name")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--max-consecutive-failures", type=int, default=3)
    parser.add_argument(
        "--promote",
        type=Path,
        default=None,
        help="explicitly promote a complete report to this new aggregate path",
    )
    parser.add_argument(
        "--allow-scope-change",
        action="store_true",
        help="explicitly recompute under changed code/config scope into a sidecar checkpoint",
    )
    args = parser.parse_args(argv)
    if not args.benchmark.is_file():
        print(f"[skip] benchmark not found: {args.benchmark}")
        return 0
    if not args.output_root.parent.exists():
        raise FileNotFoundError(f"campaign output parent does not exist: {args.output_root.parent}")

    spec = build_default_spec(
        campaign_id=args.campaign_id,
        benchmark_path=args.benchmark,
        max_consecutive_failures=args.max_consecutive_failures,
    )
    examples = load_longmemeval(args.benchmark)
    models = sorted({tier.model for tier in spec.tiers})
    metadata = {model: ollama_model_metadata(model) for model in models}
    unavailable = [model for model, payload in metadata.items() if not payload.get("available")]
    if unavailable:
        print(f"[skip] Ollama models unavailable: {', '.join(unavailable)}")
        return 0

    report = run_campaign(
        spec,
        examples,
        output_root=args.output_root,
        model_metadata=metadata,
        allow_scope_change=args.allow_scope_change,
    )
    report_path = args.output_root / args.campaign_id / "campaign_report.json"
    print(f"campaign={report.campaign_id} status={report.status} report={report_path}")
    for tier_id, tier in report.tiers.items():
        print(
            f"tier={tier_id} status={tier['status']} requested={tier['n_requested']} "
            f"evaluated={tier['n_evaluated']} failed={tier['n_failed']}"
        )
    if args.promote is not None:
        promoted = promote_campaign_report(report_path, args.promote)
        print(f"promoted={promoted}")
    return 0 if report.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
