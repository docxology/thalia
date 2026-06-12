#!/usr/bin/env python3
"""Thin orchestrator: localise the LongMemEval bottleneck and record the fix.

Writes ``data/longmemeval_bottleneck.json`` (KB of aggregates): ranking-vs-Inspector
recall, the extractive ``max_windows`` grounding sweep, and the neural accuracy gain
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


def main() -> int | str:
    """Run the bottleneck analysis and write data/longmemeval_bottleneck.json."""
    if not longmemeval_available():
        print("[skip] LongMemEval_S not downloaded; run `bash scripts/get_longmemeval.sh` first.")
        return 0
    if not ollama_model_available():
        print(f"[skip] needs a live Ollama serving {DEFAULT_OLLAMA_MODEL}; data/longmemeval_bottleneck.json left as-is.")
        return 0

    from src.evaluation.longmemeval import bottleneck_analysis

    result = bottleneck_analysis()
    out_path = PROJECT_ROOT / "data" / "longmemeval_bottleneck.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    lo, hi = min(result["sweep_values"]), max(result["sweep_values"])
    print(f"ranking recall {result['ranking_recall_at_10']:.2f} vs Inspector recall {result['inspector_recall']:.2f}")
    print(f"neural accuracy: max_windows {lo} -> {result['neural_by_maxwindows'][lo]['accuracy']:.3f} "
          f"vs {hi} -> {result['neural_by_maxwindows'][hi]['accuracy']:.3f}")
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    out = main()
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
