"""Aggregate evaluation bundle for scripts and manuscript tokens."""

from __future__ import annotations

from ..compiler.metrics import EvalReport, evaluate
from ..config import HarnessConfig, default_config
from ..harness import build_run_fn
from ..signatures import TaskCategory
from .dataset import build_demo_dataset
from .experiments import (
    evidence_funnel,
    mmr_lambda_sweep,
    retriever_comparison,
    rrf_weight_sweep,
)


def run_full_eval(config: HarnessConfig | None = None) -> dict:
    """Run the full evaluation bundle and return a JSON-serialisable dict."""
    config = config or default_config()
    dataset = build_demo_dataset()
    report: EvalReport = evaluate(build_run_fn(config), dataset)
    comparison = retriever_comparison(dataset, config)

    by_category: dict[str, list[float]] = {}
    per = report.per_example
    for example, score in zip(dataset, per):
        cat = (example.task_category or TaskCategory.SINGLE_SESSION).value
        by_category.setdefault(cat, []).append(score)
    category_means = {cat: sum(v) / len(v) for cat, v in by_category.items()}

    return {
        "n_examples": report.n,
        "composite": report.composite,
        "accuracy": report.accuracy,
        "grounding": report.grounding,
        "efficiency": report.efficiency,
        "retriever_comparison": {
            "lexical": comparison.lexical,
            "semantic": comparison.semantic,
            "hybrid": comparison.hybrid,
            "best_mode": comparison.best_mode(),
        },
        "category_means": category_means,
        "rrf_weight_sweep": rrf_weight_sweep(dataset),
        "mmr_lambda_sweep": mmr_lambda_sweep(dataset),
        "evidence_funnel": evidence_funnel(dataset, config),
        "config": {
            "top_k": config.top_k,
            "max_windows": config.max_windows,
            "max_evidence": config.max_evidence,
            "rrf_k": config.rrf_k,
            "context_budget_tokens": config.context_budget_tokens,
            "rerank": config.rerank,
        },
    }


__all__ = ["run_full_eval"]
