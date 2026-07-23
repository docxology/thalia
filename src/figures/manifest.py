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
    FigureSpec("sample_size_precision", "fig:sample_size_precision", "eval"),
    FigureSpec("statistical_audit", "fig:statistical_audit", "eval"),
    FigureSpec("category_components", "fig:category_components", "eval"),
    FigureSpec("pipeline_flow", "fig:pipeline_flow", "eval"),
    FigureSpec("gepa_trajectory", "fig:gepa_trajectory", "eval"),
    FigureSpec("thalia_cover", "fig:thalia_cover", "diagram"),
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

# Presentation contract used by the manuscript variable generator. It is kept
# with the figure manifest so layout metadata has one executable source.
BACKEND_FIGURE_WIDTH_PERCENT = 75

# Short, renderer-independent descriptions accompany the long-form manuscript
# captions.  Keeping these beside the figure manifest makes the registry and the
# dashboard accessible even when the Markdown/PDF renderer is unavailable.
FIGURE_CAPTIONS: dict[str, str] = {
    "retriever_comparison": "Unit: composite per finite demo example (n generated from the six-example bundle). Deterministic clean-set means for BM25/grep, the hashing sub-word surrogate, and their hybrid under a slack budget; no uncertainty interval is intended, and the synthetic machinery diagnostic is not a population estimate.",
    "rrf_sensitivity": "Unit: composite per finite synthetic demo example; deterministic means over a lexical-weight sweep under a binding evidence budget. No inferential interval is intended; the zoomed axis shows a budget-specific diagnostic and does not imply learned-dense retrieval.",
    "compiler_convergence": "Unit: composite per finite synthetic demo example, plotted for each candidate configuration. Every candidate score and best-so-far trace comes from the bounded MIPRO-style search; no uncertainty interval or independent validation set is present, and no generalization claim follows.",
    "consolidation_curve": "Schematic only: no empirical unit, sample size, uncertainty interval, model, or benchmark. Illustrative mechanism contrast between forced consolidation and the dual-key episodic-first gate; it must not be read as an observed result.",
    "category_breakdown": "Unit: composite per finite synthetic demo example, summarized by task category. Category means use the headline accuracy, citation-support, and evidence-count estimands; no inferential interval is intended, and slices are diagnostic rather than population estimates.",
    "evidence_funnel": "Unit: evidence items per generated demo query. Means count raw session lines, Inspector windows, ranked evidence, and citations; no uncertainty interval is intended, model dependence is absent, and retention describes context flow rather than answer quality.",
    "noise_scaling": "Unit: composite per generated synthetic probe at each false-friend level. Deterministic lane means follow mechanical distractor addition under a fixed tight budget; no inferential interval is intended, the semantic curve is a hashing surrogate, and the result is local to this probe family.",
    "mmr_tradeoff": "Unit: composite per finite synthetic demo example at each MMR setting. Deterministic means under a tight budget expose selection trade-offs; no inferential interval or model-dependent claim is intended, and the zoomed scale is a compact diagnostic.",
    "method_ablation": "Unit: composite per finite synthetic demo example for each configuration. Bars compare individually enabled retrieval/memory methods and their combination; no inferential interval is intended, and differences are descriptive and budget-specific rather than causal estimates.",
    "orchestration_value": "Unit: weighted metric components per finite synthetic demo example for a naive full-context baseline versus the typed pipeline. Stacked heights reproduce the declared composite; no uncertainty interval, model-dependent claim, or population inference is intended.",
    "scaling_ci": "Unit: token-F1 per seeded synthetic example, summarized by category. Within-category percentile-bootstrap intervals describe generated-task dispersion; fixed-seed reproducibility does not turn templated examples into human-population evidence, and no live model is used.",
    "sample_size_precision": "Unit: composite per unique seeded synthetic example, paired across methods. Fixed-stratum descriptive intervals and seed-cluster paired deltas are shown; the ledger reports exact requested/completed/failure counts and the complete Holm family, with any small-cluster limitation explicit.",
    "statistical_audit": "Unit: paired composite delta per unique seeded synthetic example within each difficulty stratum. Whole-seed-cluster descriptive intervals and Holm-adjusted q-values are shown; annotations expose cluster count, finite sample accounting, and failures, with no population or causal interpretation.",
    "category_components": "Unit: weighted metric component per finite synthetic demo example, summarized by category. Stacks audit the declared accuracy, citation-support, and evidence-count terms; no separate inferential hypotheses, model comparison, or population claim is intended.",
    "pipeline_flow": "Unit: evidence-item count per finite synthetic demo example at Inspector, Retriever, and Reasoner boundaries. No uncertainty interval or model-dependent result is intended; the panel preserves individual paths hidden by mean funnel summaries.",
    "gepa_trajectory": "Unit: deterministic component score per bounded reflective-optimization iteration on the finite synthetic demo. Open markers identify the weakest component driving the next mutation; no uncertainty interval or generalization claim is intended.",
    "thalia_cover": "Schematic visual abstract (no empirical unit, sample size, uncertainty interval, or model comparison): THALIA's evidence path, typed stage contracts, append-only memory boundary, and compiler scope.",
    "thalia_overview": "Schematic architecture map (no empirical unit, sample size, uncertainty interval, or model dependence) from query/history through inspect, retrieve, reason, and gate; arrows represent typed data flow rather than opaque prompt calls.",
    "foundations_map": "Schematic traceability map (no empirical unit, sample size, or uncertainty interval) from cited foundations to THALIA stages; mappings indicate conceptual reuse, not empirical validation of the source systems.",
    "memory_lifecycle": "Schematic lifecycle (no empirical unit, sample size, uncertainty interval, or model comparison) showing the append-only episode and separate dual-key gate required before a derived MEMORY.md delta can be written.",
    "gepa_evolution_loop": "Schematic audit loop (no empirical unit, sample size, uncertainty interval, or external model dependence) for the in-house GEPA-style compiler analogue; every transition is bounded and recorded.",
    "backend_comparison": "Unit: token-F1 per paired example (n and model generated from the recorded neural aggregate). Deterministic extractive versus live neural backend under the same stage contract; intervals describe finite local observations, with generation options/model digest required and no bit-identical neural regression claim.",
    "paraphrase_retrieval": "Unit: binary recall@1 per paired synthetic paraphrase probe (n generated from the learned-retrieval aggregate). Wilson intervals and an exact paired binary comparison are shown; the learned model and hashing surrogate are distinct evidence tiers and model-dependent values are not deterministic regressions.",
    "injection_resistance": "Unit: binary poisoned/auditable outcome per generated attack probe (n generated from the injection aggregate). Exact case outcomes and Wilson intervals separate answer poisoning from source auditability; optional neural rows carry model provenance, and rates are not security guarantees.",
    "longmemeval": "Unit: answer accuracy or session-reachability proxy per retained external-benchmark question (extractive and neural n generated from the aggregate). Descriptive intervals are not a formal between-model test; session grounding upper-bounds line-level attribution, and neural values depend on recorded model provenance.",
    "bottleneck": "Unit: grounding or accuracy per retained external-benchmark question/configuration. The Inspector-window sweep and full-haystack ranking recall are local slice diagnostics with recorded model/benchmark provenance; descriptive changes localize observed loss without establishing a universal causal ranking claim.",
}

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
    "FIGURE_CAPTIONS",
    "BACKEND_FIGURE_WIDTH_PERCENT",
    "COMMITTED_FIGURES",
    "DIAGRAM_FIGURES",
]
