#!/usr/bin/env python3
"""Thin orchestrator: record the surrogate-vs-learned retrieval measurement.

Compares the deterministic hashing-trigram semantic lane against a real neural
embedder (Ollama) on paraphrase probes the surrogate structurally cannot bridge,
and writes ``data/learned_retrieval.json`` — a tracked, regenerable measurement that
the figure pipeline and §evaluation tokens read. Logic lives in
:mod:`src.retrieval.learned`.

Needs a live Ollama embedding model; otherwise prints a notice, leaves any existing
``data/learned_retrieval.json`` untouched, and exits 0.
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

from src.retrieval.learned import DEFAULT_EMBED_MODEL, embed_model_available  # noqa: E402
from src.evaluation.accounting import runtime_provenance  # noqa: E402
from src.evaluation.statistics import wilson_interval  # noqa: E402


def main(output_path: str | Path | None = None) -> int | str:
    """Record the surrogate-vs-learned recall@1 comparison to an aggregate path."""
    if not embed_model_available():
        print(f"[skip] needs a live Ollama serving {DEFAULT_EMBED_MODEL}; tracked aggregate left as-is.")
        return 0

    from src.retrieval.learned import paraphrase_retrieval_probe

    result = paraphrase_retrieval_probe()
    result["runtime_provenance"] = runtime_provenance(
        models={"model": result.get("model"), "model_metadata": result.get("model_metadata")}
    )
    n = result["n_probes"]
    result["surrogate_recall_ci"] = wilson_interval(round(result["surrogate_recall_at_1"] * n), n)
    result["learned_recall_ci"] = wilson_interval(round(result["learned_recall_at_1"] * n), n)
    result.setdefault("sample_accounting", {}).update({
        "unit": "paraphrase_probe",
        "n_requested": n,
        "n_evaluated": result.get("sample_accounting", {}).get("n_evaluated", n),
        "n_failed": result.get("sample_accounting", {}).get("n_failed", 0),
    })
    out_path = Path(output_path) if output_path is not None else PROJECT_ROOT / "data" / "learned_retrieval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(f"recall@1  surrogate {result['surrogate_recall_at_1']:.3f}  |  learned {result['learned_recall_at_1']:.3f}")
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record learned retrieval probes.")
    parser.add_argument("--output-path", type=Path, default=None, help="isolated aggregate output path")
    out = main(parser.parse_args().output_path)
    sys.exit(0 if isinstance(out, str) or out == 0 else 1)
