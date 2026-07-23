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

from src.dspy_runtime import DEFAULT_OLLAMA_MODEL, ollama_model_available  # noqa: E402
from src.evaluation import injection_resistance  # noqa: E402
from src.evaluation.accounting import runtime_provenance  # noqa: E402
from src.evaluation.statistics import wilson_interval  # noqa: E402


def main(output_path: str | Path | None = None, model: str = DEFAULT_OLLAMA_MODEL) -> int | str:
    """Record the injection comparison, optionally into an isolated output path.

    The tracked aggregate is only touched when the neural service is available.
    This keeps optional-service skips from replacing a previously recorded neural
    measurement with a partial deterministic-only result. Tests and exploratory
    runs can pass ``output_path`` to write an isolated aggregate in any state.
    """
    out_path = Path(output_path) if output_path is not None else PROJECT_ROOT / "data" / "injection_eval.json"
    neural_available = ollama_model_available(model)
    if not neural_available and output_path is None:
        print(
            "[skip] Ollama model unavailable; leaving the existing tracked "
            "data/injection_eval.json unchanged."
        )
        return 0

    result = dict(injection_resistance())
    result["runtime_provenance"] = runtime_provenance()
    n = result["n_probes"]
    result["harness_poison_ci"] = wilson_interval(round(result["harness_poison_rate"] * n), n)
    result["harness_audit_ci"] = wilson_interval(round(result["harness_audit_rate"] * n), n)
    result["naive_poison_ci"] = wilson_interval(round(result["naive_poison_rate"] * n), n)
    result["naive_audit_ci"] = wilson_interval(round(result["naive_audit_rate"] * n), n)
    result["sample_accounting"] = {
        "unit": "injection_probe",
        "n_requested": n,
        "n_evaluated": n,
        "n_failed": 0,
    }
    if neural_available:
        from src.dspy_runtime import injection_resistance_neural

        neural = injection_resistance_neural(model=model)
        result["neural_model"] = neural["model"]
        result["neural_model_metadata"] = neural["model_metadata"]
        result["neural_generation_options"] = neural["generation_options"]
        result["neural_poison_rate"] = neural["neural_poison_rate"]
        result["neural_correct_rate"] = neural["neural_correct_rate"]
        result["neural_poison_ci"] = neural["neural_poison_ci"]
        result["neural_correct_ci"] = neural["neural_correct_ci"]
        result["neural_rows"] = neural["rows"]
        result["runtime_provenance"] = runtime_provenance(
            models={"model": neural.get("model"), "model_metadata": neural.get("model_metadata")}
        )
    else:
        result["neural_model"] = None
        result["neural_model_metadata"] = None
        result["neural_generation_options"] = None
        result["neural_poison_rate"] = None
        result["neural_correct_rate"] = None
        result["neural_rows"] = []

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(
        f"poison: harness {result['harness_poison_rate']:.2f} naive {result['naive_poison_rate']:.2f} "
        f"neural {result['neural_poison_rate']}  | audit: harness {result['harness_audit_rate']:.2f} naive {result['naive_audit_rate']:.2f}"
    )
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record context-poisoning resistance.")
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    args = parser.parse_args()
    out = main(args.output_path, args.model)
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
