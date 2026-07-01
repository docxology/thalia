#!/usr/bin/env python3
"""Thin orchestrator: build the static HTML results dashboard.

Generates the figures, computes the evaluation metrics and invariant results, and
writes a self-contained ``output/dashboard.html`` that embeds them. Rendering and
analysis live in ``src/``; this script only orchestrates and handles I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path

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
    figures_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures_mod)
    figure_paths = figures_mod.main()
    figure_names = [f"figures/{Path(p).name}" for p in figure_paths]

    metrics = run_full_eval()
    invariants = all_invariants()
    verification_path = write_verification_summary(PROJECT_ROOT / "output" / "reports" / "verification_summary.json")
    verification = load_verification_summary(verification_path).to_dict()
    demo_path = PROJECT_ROOT / "output" / "data" / "demo_result.json"
    demo = None
    if demo_path.exists():
        import json

        demo = json.loads(demo_path.read_text(encoding="utf-8"))

    output_path = PROJECT_ROOT / "output" / "dashboard.html"
    write_dashboard(output_path, metrics, invariants, figure_names, verification=verification, demo=demo)
    write_artifact_manifest(PROJECT_ROOT)
    print(str(output_path))
    return output_path


if __name__ == "__main__":
    main()
