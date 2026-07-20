#!/usr/bin/env python3
"""Thin orchestrator: record the real extractive-vs-neural backend comparison.

Runs the real ExtractiveLM and the real neural Ollama model (Gemma) over the demo
dataset through identical real dspy programs, scores token-F1 against gold, and
writes ``data/neural_eval.json`` — a tracked, reproducible measurement that the
deterministic figure pipeline reads (so the figure renders without re-running the
model). Logic lives in :func:`src.dspy_runtime.evaluate_backends`.

Needs the project's ``dspy-ai`` dependency and a live Ollama serving the model;
otherwise prints a notice, leaves any existing ``data/neural_eval.json``
untouched, and exits 0.
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


def main() -> int | str:
    """Record the real backend comparison to data/neural_eval.json."""
    if not ollama_model_available():
        print(f"[skip] needs a live Ollama serving {DEFAULT_OLLAMA_MODEL}; data/neural_eval.json left as-is.")
        return 0

    from src.dspy_runtime import evaluate_backends

    result = evaluate_backends()
    out_path = PROJECT_ROOT / "data" / "neural_eval.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(f"extractive mean F1 {result['mean_extractive_f1']:.3f} | neural mean F1 {result['mean_neural_f1']:.3f}")
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    out = main()
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
