#!/usr/bin/env python3
"""Thin orchestrator: run the REAL DSPy runtime and serialise the result.

Runs a genuine ``dspy.Predict`` over the project's real ExtractiveLM backend, then
a genuine ``dspy.BootstrapFewShot`` optimizer over the demo dataset. Writes a JSON
summary under ``output/data/``. Logic lives in :mod:`src.dspy_runtime`.

If the optional ``dspy`` extra is not installed this prints a notice and exits 0,
so the working-render pipeline (which runs every script bare) is never blocked.
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

from src.dspy_runtime import DSPY_AVAILABLE  # noqa: E402


def main() -> int | str:
    """Run the real DSPy prediction + optimization and write the result JSON."""
    if not DSPY_AVAILABLE:
        print("[skip] dspy extra not installed; run `uv pip install 'dspy-ai>=2.5'` to enable the real DSPy runtime.")
        return 0

    from src.dspy_runtime import (
        DEFAULT_OLLAMA_MODEL,
        build_dataset,
        build_program,
        compile_program,
        configure,
        configure_ollama,
        held_out_optimizer_lift,
        model_in_tags,
        ollama_model_available,
        qa_metric,
    )

    _CTX = "User: my wifi password is bluefish42\nAssistant: noted\nThe cat is grey."
    _Q = "What is the wifi password?"

    # Deterministic real path (fast, always available): real dspy.Predict + a real
    # BootstrapFewShot optimizer, backed by the real deterministic ExtractiveLM.
    configure()
    demo = build_program()(context=_CTX, question=_Q)
    dataset = build_dataset()
    compiled = compile_program(program=build_program(), trainset=dataset)
    demos = compiled.predictors()[0].demos
    score = sum(qa_metric(ex, compiled(**ex.inputs())) for ex in dataset)

    # Measure the optimizer the only falsifiable way: held-out before/after.
    lift = held_out_optimizer_lift(train_size=4)

    result = {
        "dspy_version": __import__("dspy").__version__,
        "deterministic_backend": "ExtractiveDSPyLM (real deterministic ExtractiveLM)",
        "deterministic_prediction": demo.answer,
        "trainset_size": len(dataset),
        "optimizer": "BootstrapFewShot",
        "bootstrapped_demos": len(demos),
        "trainset_score": f"{score}/{len(dataset)}",
        "held_out_optimizer_lift": lift,
        "neural_backend": None,
        "neural_prediction": None,
    }

    # Real neural path when a live Ollama model is present: dspy -> litellm ->
    # ollama -> a real Gemma model. No mock; a genuine local LLM generation.
    if ollama_model_available():
        configure_ollama()
        result["neural_backend"] = f"ollama:{DEFAULT_OLLAMA_MODEL} (real neural LLM via dspy->litellm->ollama)"
        result["neural_prediction"] = build_program()(context=_CTX, question=_Q).answer
        # Record that the model was confirmed present in the Ollama tag listing.
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://localhost:11434/api/tags", timeout=3) as resp:
                import json as _json
                tags = _json.load(resp)
                result["neural_model_in_tags"] = model_in_tags(tags, DEFAULT_OLLAMA_MODEL)
        except Exception:
            result["neural_model_in_tags"] = None
        configure()  # restore the deterministic global LM

    out_dir = PROJECT_ROOT / "output" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dspy_result.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    result = main()
    sys.exit(0 if isinstance(result, str) or result == 0 else 1)
