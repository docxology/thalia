#!/usr/bin/env python3
"""Thin orchestrator: run a real neural LLM via OpenRouter and record the result.

Configures dspy with an OpenRouter-hosted model (default
``nvidia/nemotron-3-ultra-550b-a55b:free``), runs the same ``dspy.Predict``
program over the demo dataset, and writes the comparison to ``output/data/``.

The API key is read from the ``THALIA_OPENROUTER_API_KEY`` environment variable
or a ``.env`` file in the project root. Logic lives in :mod:`src.dspy_runtime`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

# Load .env if present
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> int | str:
    """Run the real OpenRouter prediction and write the result JSON."""
    from src.dspy_runtime import (
        DEFAULT_OPENROUTER_MODEL,
        build_dataset,
        build_program,
        configure_openrouter,
        qa_metric,
    )

    # Check if the API key is configured before making any calls.
    api_key = os.environ.get("THALIA_OPENROUTER_API_KEY", "")
    if not api_key:
        print("[skip] THALIA_OPENROUTER_API_KEY not set; create a .env file or export the variable.")
        return 0

    _CTX = "User: my wifi password is bluefish42\nAssistant: noted\nThe cat is grey."
    _Q = "What is the wifi password?"

    # Real neural path via OpenRouter
    try:
        configure_openrouter(api_key=api_key)
        program = build_program()
        prediction = program(context=_CTX, question=_Q).answer
        dataset = build_dataset()
        score = sum(qa_metric(ex, program(**ex.inputs())) for ex in dataset)
    except Exception as exc:
        print(f"[skip] OpenRouter API error: {exc}")
        return 0

    result = {
        "openrouter_model": DEFAULT_OPENROUTER_MODEL,
        "openrouter_prediction": prediction,
        "dataset_size": len(dataset),
        "dataset_score": f"{score}/{len(dataset)}",
        "temperature": 0.0,
    }

    out_dir = PROJECT_ROOT / "output" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "openrouter_result.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    result = main()
    sys.exit(0 if isinstance(result, str) or result == 0 else 1)