"""Command-line interface for matched backend and context-method observations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .config import load_config
from .evaluation.backend_benchmark import (
    build_benchmark_backends,
    build_benchmark_methods,
    run_backend_benchmark,
    write_backend_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the THALIA backend benchmark CLI."""
    parser = argparse.ArgumentParser(prog="thalia-benchmark", description=__doc__)
    parser.add_argument("--ollama-model", action="append", default=[], help="Explicit local model; repeatable")
    parser.add_argument("--openrouter-model", action="append", default=[], help="Explicit cloud model; repeatable")
    parser.add_argument("--allow-cloud", action="store_true", help="Permit explicitly selected OpenRouter requests")
    parser.add_argument("--limit", type=int, help="Global example limit after balanced seed/category ordering")
    parser.add_argument("--seed", type=int, action="append", help="Cohort seed; repeatable, default 0")
    parser.add_argument(
        "--method", action="append",
        help="Repeatable: harness (default), full_context, lexical_only, adaptive",
    )
    parser.add_argument("--config", type=Path, help="Base harness configuration; environment overrides disabled")
    parser.add_argument("--reference-method", default="full_context", help="Paired reference, if selected")
    parser.add_argument("--n-boot", type=int, default=2000, help="Seed-cluster bootstrap resamples")
    parser.add_argument("--analysis-seed", type=int, default=0, help="Bootstrap randomness seed")
    parser.add_argument("--per-category", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--num-ctx", type=int, help="Requested Ollama context size; no retention guarantee")
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
        config = load_config(args.config, apply_env=False) if args.config is not None else None
        methods = build_benchmark_methods(args.method or ("harness",), config=config)
        backends = build_benchmark_backends(
            ollama_models=args.ollama_model, openrouter_models=args.openrouter_model,
            timeout=args.timeout, max_tokens=args.max_tokens, num_ctx=args.num_ctx,
            allow_cloud=args.allow_cloud, observe_models=True,
        )
        payload = run_backend_benchmark(
            backends, methods=methods, per_category=args.per_category,
            seeds=tuple(args.seed or (0,)), limit=args.limit, allow_cloud=args.allow_cloud,
            reference_method=args.reference_method, n_boot=args.n_boot,
            analysis_seed=args.analysis_seed,
        )
    except yaml.YAMLError as exc:
        parser.error(f"Invalid configuration YAML ({type(exc).__name__})")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    path = write_backend_benchmark(payload, args.output)
    print(path)
    if payload["status"] != "complete":
        print("Backend benchmark incomplete; diagnostic evidence saved, destination preserved.", file=sys.stderr)
        return 1
    return 0


__all__ = ["build_parser", "main"]
