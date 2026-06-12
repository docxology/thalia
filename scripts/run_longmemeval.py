#!/usr/bin/env python3
"""Thin orchestrator: run the real LongMemEval_S benchmark and record aggregates.

Writes ``data/longmemeval_results.json`` (a few KB of aggregate metrics — accuracy,
session-level grounding, composite with bootstrap CIs for the extractive and neural
backends). The 277 MB benchmark itself stays gitignored; the committed aggregates let
the figure and §evaluation tokens regenerate without re-running. Logic is in
:func:`src.evaluation.longmemeval.longmemeval_eval`.

Needs the downloaded benchmark (``bash scripts/get_longmemeval.sh``) and, for the
neural rows, a live Ollama model; otherwise prints a notice and exits 0.
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
    """Run LongMemEval_S and write data/longmemeval_results.json."""
    if not longmemeval_available():
        print("[skip] LongMemEval_S not downloaded; run `bash scripts/get_longmemeval.sh` first.")
        return 0
    if not ollama_model_available():
        print(f"[skip] needs a live Ollama serving {DEFAULT_OLLAMA_MODEL}; data/longmemeval_results.json left as-is.")
        return 0

    from src.evaluation.longmemeval import longmemeval_eval

    result = longmemeval_eval()
    out_path = PROJECT_ROOT / "data" / "longmemeval_results.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    ea = result["extractive_accuracy"][0]
    na = result["neural_accuracy"][0]
    eg = result["extractive_grounding"][0]
    print(f"LongMemEval_S (n_ext={result['n_extractive']}, n_neural={result['n_neural']}): "
          f"extractive acc {ea:.3f} | neural acc {na:.3f} | session-grounding {eg:.3f}")
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    out = main()
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
