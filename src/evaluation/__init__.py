"""Deterministic evaluation dataset and harness experiments."""

from .ablation import (
    composite_weight_sensitivity,
    injection_resistance,
    memory_recall_ablation,
    no_harness_baseline,
)
from .budget import TIGHT_MAX_EVIDENCE, TIGHT_TOP_K
from .bundle import run_full_eval
from .dataset import build_demo_dataset, build_large_dataset, with_noise
from .scaling import bootstrap_ci, large_dataset_eval
from .experiments import (
    RetrieverComparison,
    consolidation_simulation,
    evidence_funnel,
    method_ablation,
    mmr_lambda_sweep,
    noise_scaling_experiment,
    retriever_comparison,
    rrf_weight_sweep,
)

__all__ = [
    "TIGHT_TOP_K",
    "TIGHT_MAX_EVIDENCE",
    "build_demo_dataset",
    "build_large_dataset",
    "with_noise",
    "bootstrap_ci",
    "large_dataset_eval",
    "RetrieverComparison",
    "retriever_comparison",
    "rrf_weight_sweep",
    "mmr_lambda_sweep",
    "evidence_funnel",
    "method_ablation",
    "noise_scaling_experiment",
    "consolidation_simulation",
    "run_full_eval",
    "no_harness_baseline",
    "composite_weight_sensitivity",
    "memory_recall_ablation",
    "injection_resistance",
]
