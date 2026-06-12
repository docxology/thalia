#!/usr/bin/env python3
"""Thin orchestrator: run the MIPRO + GEPA compilers and serialise the result.

Computation lives in ``src/compiler/``; this script handles I/O only. Writes
``output/data/compile_result.json`` and prints the path to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.compiler.gepa import GEPAOptimizer  # noqa: E402
from src.compiler.metrics import evaluate  # noqa: E402
from src.compiler.mipro import MIPROCompiler  # noqa: E402
from src.evaluation import build_demo_dataset  # noqa: E402
from src.harness import build_run_fn  # noqa: E402


def _config_dict(config) -> dict:
    return {
        "top_k": config.top_k,
        "max_windows": config.max_windows,
        "max_evidence": config.max_evidence,
        "rrf_k": config.rrf_k,
        "lexical_weight": config.lexical_weight,
        "semantic_weight": config.semantic_weight,
        "rerank": config.rerank,
        "adaptive_windows": config.adaptive_windows,
        "adaptive_window_ratio": config.adaptive_window_ratio,
    }


def _trace_rows(trace, dataset) -> list[dict]:
    rows = []
    for config, score in trace:
        report = evaluate(build_run_fn(config), dataset)
        rows.append(
            {
                "config": _config_dict(config),
                "score": score,
                "metric_components": {
                    "accuracy": report.accuracy,
                    "grounding": report.grounding,
                    "efficiency": report.efficiency,
                },
            }
        )
    return rows


def main() -> Path:
    """Run both compilers on the demo dataset and write the combined result."""
    output_dir = PROJECT_ROOT / "output" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = build_demo_dataset()

    mipro = MIPROCompiler(auto="heavy").compile(lambda c: build_run_fn(c), dataset)
    gepa = GEPAOptimizer().evolve(lambda c: build_run_fn(c), dataset, iterations=8)

    payload = {
        "mipro": {
            "best_config": _config_dict(mipro.best_config),
            "best_score": mipro.best_score,
            "n_candidates": mipro.n_candidates,
            "trace": _trace_rows(mipro.trace, dataset),
            "selection_rationale": "MIPRO-style exhaustive structural HarnessConfig search; ties keep the earliest candidate.",
        },
        "gepa": {
            "best_config": _config_dict(gepa.best_config),
            "best_score": gepa.best_score,
            "n_candidates": gepa.n_candidates,
            "trace": _trace_rows(gepa.trace, dataset),
            "selection_rationale": "GEPA-style bounded metric-component reflection over HarnessConfig; not the external DSPy optimizer.",
        },
    }
    output_path = output_dir / "compile_result.json"
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(str(output_path))
    return output_path


if __name__ == "__main__":
    main()
