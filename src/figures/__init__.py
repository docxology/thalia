"""Figure generators for the THALIA manuscript (matplotlib, headless).

Public API is re-exported from :mod:`src.figures.plots` (data-driven figures) and
:mod:`src.figures.diagrams` (architectural schematics). Figure manifest and labels
live in :mod:`src.figures.manifest`.
"""

from __future__ import annotations

from ..figure_style import EXPORT_DPI, PALETTE, zoomed_ylim as _zoomed_ylim
from .diagrams import (
    plot_foundations_map,
    plot_gepa_evolution_loop,
    plot_memory_lifecycle,
    plot_quality_protocol,
    plot_thalia_cover,
    plot_thalia_overview,
)
from .manifest import COMMITTED_FIGURES, DIAGRAM_FIGURES, FIGURE_LABELS, FIGURE_MANIFEST, FigureSpec
from .plots import (
    plot_backend_comparison,
    plot_bottleneck,
    plot_category_breakdown,
    plot_category_components,
    plot_compiler_convergence,
    plot_consolidation_curve,
    plot_evidence_funnel,
    plot_gepa_trajectory,
    plot_injection_resistance,
    plot_integrity_advantage,
    plot_longmemeval,
    plot_metric_construct_audit,
    plot_method_ablation,
    plot_mmr_tradeoff,
    plot_noise_scaling,
    plot_orchestration_value,
    plot_paraphrase_retrieval,
    plot_pipeline_flow,
    plot_retriever_comparison,
    plot_rrf_weight_sensitivity,
    plot_scaling_ci,
    plot_sample_size_precision,
    plot_statistical_audit,
)

__all__ = [
    "PALETTE",
    "EXPORT_DPI",
    "FIGURE_MANIFEST",
    "FIGURE_LABELS",
    "FigureSpec",
    "COMMITTED_FIGURES",
    "DIAGRAM_FIGURES",
    "plot_backend_comparison",
    "plot_category_components",
    "plot_injection_resistance",
    "plot_integrity_advantage",
    "plot_longmemeval",
    "plot_metric_construct_audit",
    "plot_bottleneck",
    "plot_scaling_ci",
    "plot_sample_size_precision",
    "plot_statistical_audit",
    "plot_orchestration_value",
    "plot_paraphrase_retrieval",
    "plot_retriever_comparison",
    "plot_rrf_weight_sensitivity",
    "plot_compiler_convergence",
    "plot_consolidation_curve",
    "plot_category_breakdown",
    "plot_evidence_funnel",
    "plot_pipeline_flow",
    "plot_noise_scaling",
    "plot_mmr_tradeoff",
    "plot_method_ablation",
    "plot_gepa_trajectory",
    "plot_thalia_cover",
    "plot_thalia_overview",
    "plot_foundations_map",
    "plot_quality_protocol",
    "plot_memory_lifecycle",
    "plot_gepa_evolution_loop",
    "_zoomed_ylim",
]
