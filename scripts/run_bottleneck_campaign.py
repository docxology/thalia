#!/usr/bin/env python3
"""Thin runner for the matched 100-question Inspector bottleneck campaign."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.dspy_runtime import ollama_model_metadata  # noqa: E402
from src.evaluation.campaign import CampaignSpec, CampaignTier, run_campaign  # noqa: E402
from src.evaluation.longmemeval import load_longmemeval, ranking_diagnostics  # noqa: E402
from src.evaluation.accounting import file_provenance  # noqa: E402


DEFAULT_CAMPAIGN_ROOT = Path("/Volumes/blue/data/thalia_campaigns")
DEFAULT_BENCHMARK = PROJECT_ROOT / "data" / "longmemeval" / "longmemeval_s.json"


def build_spec(campaign_id: str, benchmark: Path, sample_size: int) -> CampaignSpec:
    """Create the pre-registered five-policy matched cohort."""
    policies = (15, 30, 50, 100)
    tiers = tuple(
        CampaignTier(
            f"gemma-max-windows-{windows}",
            sample_size,
            "gemma3:4b",
            policy=f"max_windows={windows}",
            config_overrides=(("max_windows", windows),),
        )
        for windows in policies
    ) + (
        CampaignTier(
            "gemma-adaptive",
            sample_size,
            "gemma3:4b",
            policy="adaptive",
            config_overrides=(("adaptive_windows", True),),
        ),
    )
    return CampaignSpec(campaign_id=campaign_id, benchmark_path=benchmark, tiers=tiers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", default="thalia-v2-bottleneck")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--ranking-k", type=int, default=10)
    parser.add_argument("--embedding-model", default="nomic-embed-text")
    args = parser.parse_args(argv)
    if not args.benchmark.is_file():
        print(f"[skip] benchmark not found: {args.benchmark}")
        return 0
    spec = build_spec(args.campaign_id, args.benchmark, args.sample_size)
    examples = load_longmemeval(args.benchmark)
    metadata = {"gemma3:4b": ollama_model_metadata("gemma3:4b")}
    if not metadata["gemma3:4b"].get("available"):
        print("[skip] gemma3:4b is unavailable")
        return 0
    report = run_campaign(spec, examples, output_root=args.output_root, model_metadata=metadata)
    campaign_dir = args.output_root / args.campaign_id
    tier_id = next(iter(report.tiers))
    selected_ids = set(report.selected_ids_for_tier(tier_id))
    matched = [example for example in examples if example.example_id in selected_ids]
    diagnostics = ranking_diagnostics(matched, embed_model=args.embedding_model, k=args.ranking_k)
    diagnostics.update(
        {
            "campaign_id": args.campaign_id,
            "benchmark_provenance": file_provenance(args.benchmark),
            "embedding_model": args.embedding_model,
            "selected_ids": [example.example_id for example in matched],
            "evidence_tier": "live_model_ranking_diagnostic",
        }
    )
    (campaign_dir / "ranking_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"campaign={report.campaign_id} status={report.status} report={campaign_dir / 'campaign_report.json'}")
    print(f"ranking_diagnostics={campaign_dir / 'ranking_diagnostics.json'} available={diagnostics.get('available')}")
    return 0 if report.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
