#!/usr/bin/env python3
"""Thin orchestrator: generate all manuscript figures.

Plotting logic lives in ``src/figures.py``; data comes from ``src/evaluation``
and ``src/compiler/``. Writes PNGs under ``output/figures/`` and prints each path.
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

from src.compiler.mipro import MIPROCompiler  # noqa: E402
from src.evaluation import (  # noqa: E402
    build_demo_dataset,
    category_component_breakdown,
    gepa_component_trajectory,
    large_dataset_eval,
    no_harness_baseline,
    pipeline_evidence_flow,
    retriever_comparison,
    run_full_eval,
)
from src.figures import (  # noqa: E402
    plot_backend_comparison,
    plot_category_breakdown,
    plot_category_components,
    plot_bottleneck,
    plot_gepa_trajectory,
    plot_injection_resistance,
    plot_longmemeval,
    plot_orchestration_value,
    plot_paraphrase_retrieval,
    plot_pipeline_flow,
    plot_scaling_ci,
    plot_compiler_convergence,
    plot_consolidation_curve,
    plot_evidence_funnel,
    plot_method_ablation,
    plot_mmr_tradeoff,
    plot_noise_scaling,
    plot_retriever_comparison,
    plot_rrf_weight_sensitivity,
)
from src.harness import build_run_fn  # noqa: E402
from src.provenance import write_artifact_manifest, write_figure_registry  # noqa: E402


def main() -> list[Path]:
    """Generate all manuscript + dashboard figures and return their paths."""
    fig_dir = PROJECT_ROOT / "output" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    comparison = retriever_comparison()
    compiled = MIPROCompiler(auto="heavy").compile(lambda c: build_run_fn(c), build_demo_dataset())
    full_eval = run_full_eval()
    category_means = full_eval["category_means"]
    components = {k: full_eval[k] for k in ("accuracy", "grounding", "efficiency")}

    paths = [
        plot_retriever_comparison(comparison, fig_dir / "retriever_comparison.png"),
        plot_rrf_weight_sensitivity(fig_dir / "rrf_sensitivity.png"),
        plot_compiler_convergence(list(compiled.trace), fig_dir / "compiler_convergence.png", components=components),
        plot_consolidation_curve(fig_dir / "consolidation_curve.png"),
        plot_category_breakdown(category_means, fig_dir / "category_breakdown.png"),
        plot_evidence_funnel(fig_dir / "evidence_funnel.png"),
        plot_noise_scaling(fig_dir / "noise_scaling.png"),
        plot_mmr_tradeoff(fig_dir / "mmr_tradeoff.png"),
        plot_method_ablation(fig_dir / "method_ablation.png"),
        plot_orchestration_value(no_harness_baseline(), fig_dir / "orchestration_value.png"),
        plot_scaling_ci(large_dataset_eval(), fig_dir / "scaling_ci.png"),
        plot_category_components(category_component_breakdown(), fig_dir / "category_components.png"),
        plot_pipeline_flow(pipeline_evidence_flow(), fig_dir / "pipeline_flow.png"),
        plot_gepa_trajectory(gepa_component_trajectory(), fig_dir / "gepa_trajectory.png"),
    ]

    # Real extractive-vs-neural comparison from the committed measurement.
    neural_eval = PROJECT_ROOT / "data" / "neural_eval.json"
    if neural_eval.exists():
        data = json.loads(neural_eval.read_text())
        paths.append(plot_backend_comparison(data, fig_dir / "backend_comparison.png"))

    # Real surrogate-vs-learned semantic-lane comparison from the committed measurement.
    learned_eval = PROJECT_ROOT / "data" / "learned_retrieval.json"
    if learned_eval.exists():
        data = json.loads(learned_eval.read_text())
        paths.append(plot_paraphrase_retrieval(data, fig_dir / "paraphrase_retrieval.png"))

    # Context-poisoning resistance from the committed measurement.
    injection_eval = PROJECT_ROOT / "data" / "injection_eval.json"
    if injection_eval.exists():
        data = json.loads(injection_eval.read_text())
        paths.append(plot_injection_resistance(data, fig_dir / "injection_resistance.png"))

    # Real LongMemEval_S benchmark from the committed aggregates.
    lme = PROJECT_ROOT / "data" / "longmemeval_results.json"
    if lme.exists():
        data = json.loads(lme.read_text())
        paths.append(plot_longmemeval(data, fig_dir / "longmemeval.png"))

    # Bottleneck localisation + the max_windows fix.
    bn = PROJECT_ROOT / "data" / "longmemeval_bottleneck.json"
    if bn.exists():
        data = json.loads(bn.read_text())
        paths.append(plot_bottleneck(data, fig_dir / "bottleneck.png"))

    registry = write_figure_registry(paths)
    write_artifact_manifest(PROJECT_ROOT)
    paths.append(registry)

    for path in paths:
        print(str(path))
    return paths


if __name__ == "__main__":
    main()
