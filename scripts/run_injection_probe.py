#!/usr/bin/env python3
"""Thin orchestrator: record the context-poisoning resistance comparison.

Writes ``data/injection_eval.json`` combining the deterministic harness/naive
results with the real neural model's injection poison rate, so the figure and the
§evaluation cognitive-security tokens regenerate from a tracked measurement. Logic
lives in :func:`src.evaluation.injection_resistance` and
:func:`src.dspy_runtime.injection_resistance_neural`.

Needs a live Ollama model for the neural row; otherwise records the deterministic
rows only and notes the neural row is pending.
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

from src.dspy_runtime import DSPY_AVAILABLE, ollama_model_available  # noqa: E402
from src.evaluation import injection_resistance  # noqa: E402


def main() -> int | str:
    """Record the injection-resistance comparison to data/injection_eval.json."""
    result = dict(injection_resistance())
    if DSPY_AVAILABLE and ollama_model_available():
        from src.dspy_runtime import injection_resistance_neural

        neural = injection_resistance_neural()
        result["neural_model"] = neural["model"]
        result["neural_model_metadata"] = neural["model_metadata"]
        result["neural_generation_options"] = neural["generation_options"]
        result["neural_poison_rate"] = neural["neural_poison_rate"]
        result["neural_correct_rate"] = neural["neural_correct_rate"]
        result["neural_rows"] = neural["rows"]
    else:
        result["neural_model"] = None
        result["neural_model_metadata"] = None
        result["neural_generation_options"] = None
        result["neural_poison_rate"] = None
        result["neural_correct_rate"] = None
        result["neural_rows"] = []

    out_path = PROJECT_ROOT / "data" / "injection_eval.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(
        f"poison: harness {result['harness_poison_rate']:.2f} naive {result['naive_poison_rate']:.2f} "
        f"neural {result['neural_poison_rate']}  | audit: harness {result['harness_audit_rate']:.2f} naive {result['naive_audit_rate']:.2f}"
    )
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    out = main()
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
