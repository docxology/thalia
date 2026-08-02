#!/usr/bin/env python3
"""Thin orchestrator: localise the LongMemEval bottleneck and record the fix.

Writes ``data/longmemeval_bottleneck.json`` (KB of aggregates): ranking-vs-Inspector
recall, the extractive ``max_windows`` citation-support sweep, and the neural accuracy gain
from a wider Inspector. Logic in
:func:`src.evaluation.longmemeval.bottleneck_analysis`.

Needs the benchmark (+ Ollama for the neural rows); otherwise prints a notice, exits 0.
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

from src.dspy_runtime import DEFAULT_OLLAMA_MODEL, ollama_model_available  # noqa: E402
from src.evaluation.longmemeval import longmemeval_available  # noqa: E402


def main(
    output_path: str | Path | None = None,
    *,
    ranking_limit: int = 40,
    sweep_values: tuple[int, ...] = (15, 30, 50, 100),
    neural_limit: int = 30,
    recall_modes_limit: int = 8,
) -> int | str:
    """Run the bottleneck analysis and write data/longmemeval_bottleneck.json."""
    if not longmemeval_available():
        print("[skip] LongMemEval_S not downloaded; run `bash scripts/get_longmemeval.sh` first.")
        return 0
    if not ollama_model_available():
        print(f"[skip] needs a live Ollama serving {DEFAULT_OLLAMA_MODEL}; data/longmemeval_bottleneck.json left as-is.")
        return 0

    from src.evaluation.longmemeval import bottleneck_analysis

    try:
        result = bottleneck_analysis(
            ranking_limit=ranking_limit,
            sweep_values=sweep_values,
            neural_limit=neural_limit,
            recall_modes_limit=recall_modes_limit,
        )
    except Exception as exc:
        print(f"[failed] LongMemEval bottleneck run: {type(exc).__name__}: {exc}; existing aggregate left as-is.")
        return 1
    out_path = Path(output_path) if output_path is not None else PROJECT_ROOT / "data" / "longmemeval_bottleneck.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    lo, hi = min(result["sweep_values"]), max(result["sweep_values"])
    print(f"ranking recall {result['ranking_recall_at_10']:.2f} vs Inspector recall {result['inspector_recall']:.2f}")
    print(f"neural accuracy: max_windows {lo} -> {result['neural_by_maxwindows'][lo]['accuracy']:.3f} "
          f"vs {hi} -> {result['neural_by_maxwindows'][hi]['accuracy']:.3f}")
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record LongMemEval bottleneck analysis.")
    parser.add_argument("--output-path", type=Path, default=None, help="isolated aggregate output path")
    parser.add_argument("--ranking-limit", type=int, default=40)
    parser.add_argument("--sweep-values", type=int, nargs="+", default=(15, 30, 50, 100))
    parser.add_argument("--neural-limit", type=int, default=30)
    parser.add_argument("--recall-modes-limit", type=int, default=8)
    args = parser.parse_args()
    out = main(
        args.output_path,
        ranking_limit=args.ranking_limit,
        sweep_values=tuple(args.sweep_values),
        neural_limit=args.neural_limit,
        recall_modes_limit=args.recall_modes_limit,
    )
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
