"""Pre-registered deterministic sensitivity evaluations.

These evaluations are a distinct ten-seed sensitivity lane alongside the
publication-size sample audit; neither replaces the other.
They deliberately report finite generated-task dispersion and retain the seed as
the cluster unit; the output is machinery evidence, not a population estimate.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..compiler.metrics import EvalExample, answer_score, grounding_score, harness_metric
from ..config import HarnessConfig, default_config
from ..harness import build_run_fn
from ..signatures import TaskCategory
from .accounting import fingerprint_examples, fingerprint_files
from .budget import lexical_only, semantic_only
from .dataset import build_research_dataset
from .statistics import clustered_bootstrap_mean, clustered_paired_comparison

DEFAULT_SEED_SENSITIVITY_SEEDS = tuple(range(10))


def _validate_seeds(seeds: Iterable[int]) -> tuple[int, ...]:
    values = tuple(seeds)
    if not values or len(set(values)) != len(values):
        raise ValueError("seeds must be non-empty and unique")
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in values):
        raise ValueError("seeds must contain integers")
    return values


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def seed_sensitivity_eval(
    *,
    per_category: int = 10,
    seeds: tuple[int, ...] = DEFAULT_SEED_SENSITIVITY_SEEDS,
    n_boot: int = 2000,
) -> dict[str, Any]:
    """Evaluate three retrieval policies over the pre-registered ten seeds.

    Each policy sees exactly the same generated examples for a seed.  Aggregates
    include per-seed cluster means and paired comparisons so the sensitivity
    design remains a distinct, auditable analysis.
    """
    if isinstance(per_category, bool) or not isinstance(per_category, int) or per_category <= 0:
        raise ValueError("per_category must be a positive integer")
    if isinstance(n_boot, bool) or not isinstance(n_boot, int) or n_boot <= 0:
        raise ValueError("n_boot must be a positive integer")
    seed_values = _validate_seeds(seeds)
    configs: dict[str, HarnessConfig] = {
        "hybrid": default_config(),
        "lexical": lexical_only(default_config()),
        "semantic": semantic_only(default_config()),
    }
    rows: list[dict[str, object]] = []
    method_example_values: dict[str, dict[int, list[float]]] = {method: {} for method in configs}
    paired_values: dict[str, dict[str, dict[int, list[float]]]] = {
        "hybrid_vs_lexical": {"hybrid": {}, "lexical": {}},
        "hybrid_vs_semantic": {"hybrid": {}, "semantic": {}},
    }
    all_examples: list[EvalExample] = []
    n_requested = 0
    n_failed = 0

    for seed in seed_values:
        dataset = build_research_dataset(per_category=per_category, seed=seed)
        all_examples.extend(dataset)
        n_requested += len(dataset) * len(configs)
        per_method: dict[str, dict[str, float]] = {}
        for method, config in configs.items():
            values: dict[str, list[float]] = {"composite": [], "accuracy": [], "grounding": []}
            run = build_run_fn(config)
            for example in dataset:
                try:
                    output = run(example)
                except Exception:
                    n_failed += 1
                    continue
                values["composite"].append(harness_metric(output, example))
                values["accuracy"].append(answer_score(output, example))
                values["grounding"].append(grounding_score(output, example))
            if len(values["composite"]) != len(dataset):
                raise RuntimeError(f"seed {seed} method {method} is incomplete")
            method_example_values[method][seed] = values["composite"]
            per_method[method] = {name: _mean(metric_values) for name, metric_values in values.items()}
            rows.append(
                {
                    "seed": seed,
                    "method": method,
                    "n_requested": len(dataset),
                    "n_evaluated": len(values["composite"]),
                    "n_failed": len(dataset) - len(values["composite"]),
                    "metrics": per_method[method],
                    "status": "complete" if len(values["composite"]) == len(dataset) else "partial",
                    "categories": sorted({(example.task_category or TaskCategory.SINGLE_SESSION).value for example in dataset}),
                }
            )
        for comparison, right in (("hybrid_vs_lexical", "lexical"), ("hybrid_vs_semantic", "semantic")):
            paired_values[comparison]["hybrid"][seed] = method_example_values["hybrid"][seed]
            paired_values[comparison][right][seed] = method_example_values[right][seed]

    cluster_statistics: dict[str, dict[str, object]] = {}
    for method, by_seed in method_example_values.items():
        cluster_statistics[method] = clustered_bootstrap_mean(
            by_seed,
            resamples=n_boot,
            seed=100 + len(method),
            confidence=0.95,
            unit="seed_cluster",
        ).to_dict()

    paired_comparisons: dict[str, dict[str, object]] = {}
    for index, (name, pair) in enumerate(paired_values.items()):
        paired_comparisons[name] = clustered_paired_comparison(
            pair["hybrid"],
            pair[name.rsplit("_vs_", 1)[1]],
            resamples=n_boot,
            permutations=n_boot,
            bootstrap_seed=300 + index,
            permutation_seed=400 + index,
            confidence=0.95,
        ).to_dict()

    return {
        "schema_version": 1,
        "experiment": "deterministic_seed_sensitivity_v2",
        "evidence_tier": "finite_synthetic",
        "headline_replacement": False,
        "per_category": per_category,
        "seed_values": list(seed_values),
        "n_seeds": len(seed_values),
        "n_unique_examples": len(all_examples),
        "dataset_fingerprint": fingerprint_examples(all_examples),
        "source_fingerprint": fingerprint_files(
            [
                __file__,
                build_research_dataset.__code__.co_filename,
            ]
        ),
        "n_boot": n_boot,
        "cluster_statistics": cluster_statistics,
        "paired_comparisons": paired_comparisons,
        "rows": rows,
        "sample_accounting": {
            "unit": "synthetic_example_method_evaluation",
            "n_requested": n_requested,
            "n_evaluated": n_requested - n_failed,
            "n_failed": n_failed,
            "status": "complete" if n_failed == 0 else "partial",
            "cluster_unit": "seed",
            "small_cluster_warning": len(seed_values) < 10,
        },
    }


__all__ = ["DEFAULT_SEED_SENSITIVITY_SEEDS", "seed_sensitivity_eval"]
