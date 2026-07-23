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
from src.evaluation.accounting import runtime_provenance  # noqa: E402


def main(output_path: str | Path | None = None, model: str = DEFAULT_OLLAMA_MODEL) -> int | str:
    """Record the real backend comparison to data/neural_eval.json."""
    if not ollama_model_available(model):
        print(f"[skip] needs a live Ollama serving {model}; output left as-is.")
        return 0

    from src.dspy_runtime import evaluate_backends

    result = evaluate_backends(model=model)
    result["runtime_provenance"] = runtime_provenance(
        models={"model": result.get("model"), "model_metadata": result.get("model_metadata")}
    )
    out_path = Path(output_path) if output_path is not None else PROJECT_ROOT / "data" / "neural_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(f"extractive mean F1 {result['mean_extractive_f1']:.3f} | neural mean F1 {result['mean_neural_f1']:.3f}")
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record the backend comparison.")
    parser.add_argument("--output-path", type=Path, default=None, help="isolated aggregate output path")
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    args = parser.parse_args()
    out = main(args.output_path, args.model)
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
