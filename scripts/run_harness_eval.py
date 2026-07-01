#!/usr/bin/env python3
"""Thin orchestrator: run the full THALIA evaluation and serialise results.

All computation lives in ``src/evaluation``; this script only handles I/O.
Writes ``output/data/eval_results.json`` and prints the path to stdout for
manifest collection.
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

from src.evaluation import noise_scaling_experiment, run_full_eval  # noqa: E402


def main() -> Path:
    """Run the evaluation bundle and write it to output/data/eval_results.json."""
    output_dir = PROJECT_ROOT / "output" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = run_full_eval()
    results["noise_scaling"] = noise_scaling_experiment()

    output_path = output_dir / "eval_results.json"
    output_path.write_text(json.dumps(results, indent=2, sort_keys=True))
    print(str(output_path))
    return output_path


if __name__ == "__main__":
    main()
