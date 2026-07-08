#!/usr/bin/env python3
"""Thin orchestrator: generate all manuscript figures.

Plotting logic lives in ``src/figures/``; data comes from ``src/evaluation``
and ``src/compiler/``. Writes PNGs under ``output/figures/`` and prints each path.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

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
from src.evaluation.schemas import (  # noqa: E402
    BottleneckPayload,
    InjectionEvalPayload,
    LearnedRetrievalPayload,
    LongMemEvalPayload,
    NeuralEvalPayload,
    OrchestrationBaseline,
    ScalingCiPayload,
)
from src.figures import (  # noqa: E402
    plot_backend_comparison,
    plot_category_breakdown,
    plot_category_components,
    plot_bottleneck,
    plot_foundations_map,
    plot_gepa_evolution_loop,
    plot_gepa_trajectory,
    plot_injection_resistance,
    plot_longmemeval,
    plot_memory_lifecycle,
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
    plot_thalia_overview,
)
from src.figures.manifest import COMMITTED_FIGURES  # noqa: E402
from src.harness import build_run_fn  # noqa: E402
from src.provenance import write_artifact_manifest, write_figure_registry  # noqa: E402

_COMMITTED_PLOTTERS: dict[str, Callable[[dict[str, Any], Path], Path]] = {
    "neural_eval.json": lambda data, out: plot_backend_comparison(NeuralEvalPayload.from_json(data), out),
    "learned_retrieval.json": lambda data, out: plot_paraphrase_retrieval(LearnedRetrievalPayload.from_json(data), out),
    "injection_eval.json": lambda data, out: plot_injection_resistance(InjectionEvalPayload.from_json(data), out),
    "longmemeval_results.json": lambda data, out: plot_longmemeval(LongMemEvalPayload.from_json(data), out),
    "longmemeval_bottleneck.json": lambda data, out: plot_bottleneck(BottleneckPayload.from_json(data), out),
}


def _plot_if_committed(stem: str, data_file: str, fig_dir: Path) -> Path | None:
    """Load committed JSON when present and render the matching figure."""
    source = PROJECT_ROOT / "data" / data_file
    if not source.exists():
        return None
    plotter = _COMMITTED_PLOTTERS[data_file]
    return plotter(json.loads(source.read_text()), fig_dir / f"{stem}.png")


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
        plot_orchestration_value(OrchestrationBaseline.from_json(no_harness_baseline()), fig_dir / "orchestration_value.png"),
        plot_scaling_ci(ScalingCiPayload.from_json(large_dataset_eval()), fig_dir / "scaling_ci.png"),
        plot_category_components(category_component_breakdown(), fig_dir / "category_components.png"),
        plot_pipeline_flow(pipeline_evidence_flow(), fig_dir / "pipeline_flow.png"),
        plot_gepa_trajectory(gepa_component_trajectory(), fig_dir / "gepa_trajectory.png"),
        plot_thalia_overview(fig_dir / "thalia_overview.png"),
        plot_foundations_map(fig_dir / "foundations_map.png"),
        plot_memory_lifecycle(fig_dir / "memory_lifecycle.png"),
        plot_gepa_evolution_loop(fig_dir / "gepa_evolution_loop.png"),
    ]

    for spec in COMMITTED_FIGURES:
        assert spec.data_file is not None
        committed = _plot_if_committed(spec.stem, spec.data_file, fig_dir)
        if committed is not None:
            paths.append(committed)

    registry = write_figure_registry(paths)
    write_artifact_manifest(PROJECT_ROOT)
    paths.append(registry)

    for path in paths:
        print(str(path))
    return paths


if __name__ == "__main__":
    main()
