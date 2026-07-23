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
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.dspy_runtime import DEFAULT_OLLAMA_MODEL, ollama_model_available  # noqa: E402
from src.evaluation.longmemeval import longmemeval_available  # noqa: E402


def main(neural_limit: int = 50, output_path: str | Path | None = None, checkpoint_path: str | Path | None = None) -> int | str:
    """Run LongMemEval_S with resumable neural checkpoints."""
    if not longmemeval_available():
        print("[skip] LongMemEval_S not downloaded; run `bash scripts/get_longmemeval.sh` first.")
        return 0
    if not ollama_model_available():
        print(f"[skip] needs a live Ollama serving {DEFAULT_OLLAMA_MODEL}; data/longmemeval_results.json left as-is.")
        return 0

    from src.evaluation.longmemeval import longmemeval_eval

    if neural_limit <= 0:
        raise ValueError("neural_limit must be positive")
    out_path = Path(output_path) if output_path is not None else PROJECT_ROOT / "data" / "longmemeval_results.json"
    checkpoint = Path(checkpoint_path) if checkpoint_path is not None else PROJECT_ROOT / "output" / "checkpoints" / "longmemeval_neural.json"
    try:
        result = longmemeval_eval(neural_limit=neural_limit, checkpoint_path=checkpoint)
    except Exception as exc:
        print(f"[failed] LongMemEval neural run: {type(exc).__name__}: {exc}; existing aggregate left as-is.")
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    ea = result["extractive_accuracy"][0]
    na = result["neural_accuracy"][0]
    eg = result["extractive_grounding"][0]
    print(f"LongMemEval_S (n_ext={result['n_extractive']}, n_neural={result['n_neural']}): "
          f"extractive acc {ea:.3f} | neural acc {na:.3f} | session-grounding {eg:.3f}")
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record LongMemEval_S accuracy and grounding aggregates.")
    parser.add_argument(
        "--neural-limit",
        type=int,
        default=50,
        help="number of real neural examples to evaluate (default: 50; increase when Ollama capacity permits)",
    )
    parser.add_argument("--output-path", type=Path, default=None, help="isolated aggregate output path")
    parser.add_argument("--checkpoint-path", type=Path, default=None, help="resumable neural checkpoint path")
    args = parser.parse_args()
    out = main(neural_limit=args.neural_limit, output_path=args.output_path, checkpoint_path=args.checkpoint_path)
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
