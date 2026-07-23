#!/usr/bin/env python3
"""Thin orchestrator: build the static HTML results dashboard.

Generates the figures, computes the evaluation metrics and invariant results, and
writes a self-contained ``output/dashboard.html`` that embeds them. Rendering and
analysis live in ``src/``; this script only orchestrates and handles I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.dashboard import write_dashboard  # noqa: E402
from src.evaluation import run_full_eval  # noqa: E402
from src.invariants import all_invariants  # noqa: E402
from src.provenance import load_verification_summary, write_artifact_manifest, write_verification_summary  # noqa: E402


def main() -> Path:
    """Generate figures, gather metrics + invariants, and write the dashboard."""
    # Generate figures into output/figures/ (reuse the figures orchestrator).
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_thalia_generate_figures", PROJECT_ROOT / "scripts" / "generate_figures.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the figure generator")
    figures_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures_mod)
    figure_paths = figures_mod.main()
    # The generator also returns its JSON registry. It is provenance, not an
    # image, and must never become a broken <img> in the dashboard.
    figure_names = [
        f"figures/{Path(p).name}"
        for p in figure_paths
        if Path(p).suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}
    ]

    metrics = run_full_eval()
    eval_bundle = PROJECT_ROOT / "output" / "data" / "eval_results.json"
    if eval_bundle.exists():
        metrics["statistical_scaling"] = json.loads(eval_bundle.read_text()).get("statistical_scaling")
    provenance = {}
    for filename, model_key, digest_key in (
        ("neural_eval.json", "neural_model", "neural_digest"),
        ("learned_retrieval.json", "embedding_model", "embedding_digest"),
    ):
        source = PROJECT_ROOT / "data" / filename
        if source.exists():
            payload = json.loads(source.read_text(encoding="utf-8"))
            provenance[model_key] = payload.get("model")
            provenance[digest_key] = (payload.get("model_metadata") or {}).get("digest")
            if payload.get("generation_options"):
                provenance["generation_options"] = payload["generation_options"]
            if payload.get("embedding_document_prefix") or payload.get("embedding_query_prefix"):
                provenance["embedding_prefixes"] = {
                    "document": payload.get("embedding_document_prefix"),
                    "query": payload.get("embedding_query_prefix"),
                }
    benchmark = PROJECT_ROOT / "data" / "longmemeval_results.json"
    if benchmark.exists():
        payload = json.loads(benchmark.read_text(encoding="utf-8"))
        provenance["benchmark_sha256"] = (payload.get("benchmark_provenance") or {}).get("sha256")
        provenance["benchmark_bytes"] = (payload.get("benchmark_provenance") or {}).get("size_bytes")
    metrics["provenance"] = provenance
    invariants = all_invariants()
    verification_path = write_verification_summary(PROJECT_ROOT / "output" / "reports" / "verification_summary.json")
    verification = load_verification_summary(verification_path).to_dict()
    demo_path = PROJECT_ROOT / "output" / "data" / "demo_result.json"
    demo = None
    if demo_path.exists():
        demo = json.loads(demo_path.read_text(encoding="utf-8"))

    output_path = PROJECT_ROOT / "output" / "dashboard.html"
    write_dashboard(output_path, metrics, invariants, figure_names, verification=verification, demo=demo)
    write_artifact_manifest(PROJECT_ROOT)
    print(str(output_path))
    return output_path


if __name__ == "__main__":
    main()
