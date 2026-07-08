"""Single source of truth for manuscript figure stems and LaTeX labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FigureSpec:
    """One generated PNG referenced by the manuscript or dashboard."""

    stem: str
    label: str
    kind: Literal["eval", "diagram", "committed"]
    data_file: str | None = None


FIGURE_MANIFEST: tuple[FigureSpec, ...] = (
    FigureSpec("retriever_comparison", "fig:retriever_comparison", "eval"),
    FigureSpec("rrf_sensitivity", "fig:rrf_sensitivity", "eval"),
    FigureSpec("compiler_convergence", "fig:compiler_convergence", "eval"),
    FigureSpec("consolidation_curve", "fig:consolidation", "eval"),
    FigureSpec("category_breakdown", "fig:category_breakdown", "eval"),
    FigureSpec("evidence_funnel", "fig:evidence_funnel", "eval"),
    FigureSpec("noise_scaling", "fig:noise_scaling", "eval"),
    FigureSpec("mmr_tradeoff", "fig:mmr_tradeoff", "eval"),
    FigureSpec("method_ablation", "fig:method_ablation", "eval"),
    FigureSpec("orchestration_value", "fig:orchestration_value", "eval"),
    FigureSpec("scaling_ci", "fig:scaling_ci", "eval"),
    FigureSpec("category_components", "fig:category_components", "eval"),
    FigureSpec("pipeline_flow", "fig:pipeline_flow", "eval"),
    FigureSpec("gepa_trajectory", "fig:gepa_trajectory", "eval"),
    FigureSpec("thalia_overview", "fig:thalia_overview", "diagram"),
    FigureSpec("foundations_map", "fig:foundations_map", "diagram"),
    FigureSpec("memory_lifecycle", "fig:memory_lifecycle", "diagram"),
    FigureSpec("gepa_evolution_loop", "fig:gepa_evolution_loop", "diagram"),
    FigureSpec("backend_comparison", "fig:backend_comparison", "committed", "neural_eval.json"),
    FigureSpec("paraphrase_retrieval", "fig:paraphrase_retrieval", "committed", "learned_retrieval.json"),
    FigureSpec("injection_resistance", "fig:injection_resistance", "committed", "injection_eval.json"),
    FigureSpec("longmemeval", "fig:longmemeval", "committed", "longmemeval_results.json"),
    FigureSpec("bottleneck", "fig:bottleneck", "committed", "longmemeval_bottleneck.json"),
)

FIGURE_LABELS: dict[str, str] = {spec.stem: spec.label for spec in FIGURE_MANIFEST}

COMMITTED_FIGURES: tuple[FigureSpec, ...] = tuple(
    spec for spec in FIGURE_MANIFEST if spec.kind == "committed"
)

DIAGRAM_FIGURES: tuple[FigureSpec, ...] = tuple(
    spec for spec in FIGURE_MANIFEST if spec.kind == "diagram"
)

__all__ = [
    "FigureSpec",
    "FIGURE_MANIFEST",
    "FIGURE_LABELS",
    "COMMITTED_FIGURES",
    "DIAGRAM_FIGURES",
]
