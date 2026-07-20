#!/usr/bin/env python3
"""Thin orchestrator: exercise the composable Pipeline and serialise the result.

Runs the :class:`src.pipeline.Pipeline` with all four stages over the demo
dataset and writes a JSON summary under ``output/data/``. The pipeline exposes
intermediate state after each stage — this script records that trace so the
manuscript and dashboard can show the narrowing funnel explicitly.

All computation lives in :mod:`src.pipeline`; this script handles I/O only.
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

from src.config import default_config  # noqa: E402
from src.evaluation import build_demo_dataset  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402


def main() -> Path:
    """Run the Pipeline over the demo dataset and write the result JSON."""
    output_dir = PROJECT_ROOT / "output" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = default_config()
    dataset = build_demo_dataset()

    rows = []
    for example in dataset:
        pipe = Pipeline(config=config).with_all_stages()
        out = pipe.run(query=example.query, session_history=example.session_history)
        intermediate_names = [name for name, _ in pipe.intermediates]
        rows.append(
            {
                "query": example.query,
                "expected_answer": example.expected_answer,
                "answer": out.answer,
                "task_category": out.task_category.value,
                "delivery_mode": out.delivery_mode.value,
                "citations": [
                    {"source_index": c.source_index, "excerpt": c.excerpt}
                    for c in out.evidence_citations
                ],
                "intermediate_steps": intermediate_names,
                "n_ranked_evidence": len(out.ranked_evidence),
                "consolidation_applied": out.consolidation_applied,
            }
        )

    result = {
        "config": config.to_dict(),
        "n_examples": len(dataset),
        "rows": rows,
    }

    out_path = output_dir / "pipeline_result.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(str(out_path))
    return out_path


if __name__ == "__main__":
    main()
