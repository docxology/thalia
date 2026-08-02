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
    FigureSpec("metric_construct_audit", "fig:metric_construct_audit", "eval"),
    FigureSpec("pipeline_flow", "fig:pipeline_flow", "eval"),
    FigureSpec("gepa_trajectory", "fig:gepa_trajectory", "eval"),
    FigureSpec("thalia_cover", "fig:thalia_cover", "diagram"),
    FigureSpec("thalia_overview", "fig:thalia_overview", "diagram"),
    FigureSpec("evidence_tier_map", "fig:evidence_tier_map", "diagram"),
    FigureSpec("foundations_map", "fig:foundations_map", "diagram"),
    FigureSpec("quality_protocol", "fig:quality_protocol", "diagram"),
    FigureSpec("memory_lifecycle", "fig:memory_lifecycle", "diagram"),
    FigureSpec("gepa_evolution_loop", "fig:gepa_evolution_loop", "diagram"),
    FigureSpec("backend_comparison", "fig:backend_comparison", "committed", "neural_eval.json"),
    FigureSpec("paraphrase_retrieval", "fig:paraphrase_retrieval", "committed", "learned_retrieval.json"),
    FigureSpec("injection_resistance", "fig:injection_resistance", "committed", "injection_eval.json"),
    FigureSpec("integrity_advantage_audit", "fig:integrity_advantage_audit", "committed", "integrity_advantage.json"),
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
    "retriever_comparison": "Unit: composite per example in the six-example synthetic bundle. Bars show deterministic clean-set means for BM25/grep, the hashing sub-word surrogate, and their hybrid under a slack budget. Scope: a finite machinery diagnostic; interval estimation and target-population inference require a separate design.",
    "rrf_sensitivity": "Unit: composite per synthetic demo example. Points show deterministic means across the lexical-weight sweep under a binding evidence budget. Scope: a budget-specific fusion diagnostic; the hashing lane supplies the semantic representation and the sweep carries no interval or population estimand.",
    "compiler_convergence": "Unit: composite per synthetic demo example at each candidate configuration. The candidate and best-so-far traces come from the bounded MIPRO-style search. Scope: a finite search trace; held-out validation and generalization are separate analyses.",
    "consolidation_curve": "Schematic mechanism with no empirical observation unit, sample size, uncertainty interval, model run, or benchmark. The curves illustrate the proposed distinction between forced consolidation and the dual-key episodic-first gate. Quantitative interpretation requires a measured memory study.",
    "category_breakdown": "Unit: composite per synthetic demo example, summarized by task category. Category means combine answer token-F1, citation-support, and evidence-count efficiency. Scope: finite diagnostic slices; target-population inference requires a broader sampling design.",
    "evidence_funnel": "Unit: evidence items per generated demo query. Means count raw session lines, Inspector windows, ranked evidence, and citations. Retention describes context flow; answer quality and attribution require their own estimands.",
    "noise_scaling": "Unit: composite per generated synthetic probe at each false-friend level. Deterministic lane means follow mechanical distractor addition under a fixed tight budget. The semantic curve is a hashing surrogate, and the result is local to this probe family.",
    "mmr_tradeoff": "Unit: composite per synthetic demo example at each MMR setting. Deterministic means under a tight budget expose the selection trade-off. The zoomed scale makes the finite diagnostic visible; interval and model-dependent interpretations belong to separate studies.",
    "method_ablation": "Unit: composite per synthetic demo example for each configuration. Bars show individually enabled retrieval or memory methods and their combination under a tight budget. The contrasts are descriptive and budget-specific; causal effects require an intervention design.",
    "orchestration_value": "Unit: weighted metric components per synthetic demo example for the naive full-context baseline and the typed pipeline. Stacked heights reproduce the declared composite. Scope: a deterministic finite comparison; model-dependent and population interpretations require additional evidence.",
    "scaling_ci": "Unit: token-F1 per seeded synthetic example, summarized by category. Within-category percentile-bootstrap intervals describe dispersion in the generated task family. Fixed-seed reproducibility and live-model transfer are separate claims.",
    "sample_size_precision": "Unit: composite per unique seeded synthetic example, paired across methods. Fixed-stratum descriptive intervals and seed-cluster paired deltas are shown. The ledger exposes requested, completed, and failed rows plus the complete Holm family; the small-cluster limitation is explicit.",
    "statistical_audit": "Unit: paired composite delta per unique seeded synthetic example within each difficulty stratum. Whole-seed-cluster descriptive intervals and Holm-adjusted p-values are shown with delta labels, cluster count, finite-sample accounting, and failures. The x-axis is zoomed to the observed interval range around zero. Scope: an audit of the recorded synthetic experiment; answer quality is a separate estimand.",
    "category_components": "Unit: weighted metric component per synthetic demo example, summarized by category. Stacks audit the declared answer, citation-support, and evidence-count terms. Hypothesis testing, model comparison, and population inference require separate designs.",
    "metric_construct_audit": "Unit: mean diagnostic score per synthetic demo example within task category. The heatmap places answer token-F1, the blended citation-support proxy, source-index precision, source-index recall, session reachability, and evidence-count efficiency on a common 0–1 scale. Scope: a finite construct audit; source-index measures do not establish sentence-level entailment or answer quality.",
    "pipeline_flow": "Unit: evidence-item count per synthetic demo example at Inspector, Retriever, and Reasoner boundaries. The panel preserves individual evidence paths and exposes the gaps hidden by mean funnel summaries. It carries no uncertainty or model-quality estimand.",
    "gepa_trajectory": "Unit: deterministic component score per bounded reflective-optimization iteration on the synthetic demo. Open markers identify the weakest component selected for the next mutation. Held-out improvement and generalization require a separate validation run.",
    "thalia_cover": "Schematic visual abstract with no empirical unit, sample size, uncertainty interval, or model comparison. It maps THALIA's evidence path, typed stage contracts, append-only memory boundary, and compiler scope.",
    "thalia_overview": "Schematic architecture map with no empirical unit, sample size, uncertainty interval, or model dependence. It traces query and history through inspection, retrieval, reasoning, and memory gating; arrows indicate typed data flow.",
    "evidence_tier_map": "Schematic claim-ceiling map with no empirical unit, sample size, uncertainty interval, or model comparison. It maps each retained evidence tier to the claim it can support and the stronger interpretation it cannot support without a separate acceptance record. This is a design and release boundary, not an empirical result.",
    "foundations_map": "Schematic traceability map with no empirical unit, sample size, or uncertainty interval. It maps cited foundations to THALIA stages; each mapping records conceptual reuse and leaves source-system validation to the cited evidence.",
    "quality_protocol": "Planned protocol schematic. Two models cross three answer/evidence conditions, then pass through an exploratory pilot, rubric freeze, randomized condition-neutral packets, 0/1/2 answer-dimension labels, atomic-claim support labels, two blinded expert-rater passes, adjudication, and a fail-closed certificate gate. The local-LLM implementation is an engineering diagnostic. The pilot is excluded from the confirmatory estimand, and production readiness has an independent gate.",
    "memory_lifecycle": "Schematic lifecycle with no empirical unit, sample size, uncertainty interval, or model comparison. A raw episode is appended first; the dual-key gate then controls whether a derived MEMORY.md delta is written.",
    "gepa_evolution_loop": "Schematic audit loop with no empirical unit, sample size, uncertainty interval, or external model dependence. The in-house GEPA-style compiler analogue evaluates, records, reflects, and mutates within a bounded configuration surface.",
    "backend_comparison": "Unit: token-F1 per paired example, with n and model metadata read from the recorded neural aggregate. The extractive and live neural backends share the stage contract; intervals summarize finite local observations, and generation options plus model digest are retained. This panel describes backend behavior; adjudicated quality requires the separate expert protocol.",
    "paraphrase_retrieval": "Unit: binary recall@1 per paired synthetic paraphrase probe, with n read from the learned-retrieval aggregate. Wilson intervals and an exact two-sided McNemar comparison are shown. The learned model and hashing surrogate form separate evidence tiers, and model-dependent values carry their recorded provenance.",
    "injection_resistance": "Unit: binary poisoned and lexical cited-excerpt/source-exposure-proxy outcomes per finite generated probe, with n read from the injection aggregate. Exact case outcomes and Wilson intervals display answer poisoning alongside whether a cited excerpt lexically contains the supplied gold value. The overlay is not source-record recovery or claim-level auditability; optional neural rows carry model provenance.",
    "integrity_advantage_audit": "Unit: endpoint-specific effects. Binary probe effects use direction-normalized paired rate differences; continuous panels retain composite, token-F1, and context-policy units. Filled markers show recorded intervals; open markers show point-only aggregates. The lower panel retains each binary condition's Wilson interval and its data-source denominator. Exact paired tests, clustered compiler summaries, and raw plus exploratory Holm screening values are reported in the source JSON. Rows are not pooled; the legacy injection auditability row is a lexical cited-excerpt/source-exposure proxy, not true-source recovery or claim-level auditability.",
    "longmemeval": "Unit: three separate outcomes per retained external-benchmark question: answer token-F1, citation-support proxy, and, when recorded, session reachability. Descriptive percentile-bootstrap intervals summarize each retained backend slice. Session reachability is an exposure upper bound, citation overlap measures support, and neural values depend on recorded model provenance; adjudicated quality requires a separate study.",
    "bottleneck": "Unit: separate session reachability, citation-support proxy, and neural answer token-F1 outcomes per retained benchmark question and configuration. Small multiples preserve construct separation. The Inspector-window sweep and full-haystack ranking recall are local diagnostics with recorded model and benchmark provenance; causal ranking claims require a dedicated intervention design.",
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
