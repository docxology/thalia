"""Command-line interface for optional common-harness backend observations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .evaluation.backend_benchmark import (
    build_benchmark_backends,
    run_backend_benchmark,
    write_backend_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the THALIA backend benchmark CLI."""
    parser = argparse.ArgumentParser(prog="thalia-benchmark", description=__doc__)
    parser.add_argument("--ollama-model", action="append", default=[], help="Explicit local model; repeatable")
    parser.add_argument("--openrouter-model", action="append", default=[], help="Explicit cloud model; repeatable")
    parser.add_argument("--allow-cloud", action="store_true", help="Permit explicitly selected OpenRouter requests")
    parser.add_argument("--limit", type=int, help="Limit after category round-robin ordering")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-category", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument(
        "--output", type=Path, default=Path("output/data/backend_benchmark.json"),
        help="Artifact destination relative to the caller's working directory unless absolute",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Record selected backends, print the actual artifact path, and return status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        backends = build_benchmark_backends(
            ollama_models=args.ollama_model, openrouter_models=args.openrouter_model,
            timeout=args.timeout, max_tokens=args.max_tokens,
            allow_cloud=args.allow_cloud, observe_models=True,
        )
        payload = run_backend_benchmark(
            backends, per_category=args.per_category, seed=args.seed, limit=args.limit,
            allow_cloud=args.allow_cloud,
        )
    except ValueError as exc:
        parser.error(str(exc))
    path = write_backend_benchmark(payload, args.output)
    print(path)
    if payload["status"] != "complete":
        print("Backend benchmark incomplete; diagnostic evidence saved, destination preserved.", file=sys.stderr)
        return 1
    return 0


__all__ = ["build_parser", "main"]
