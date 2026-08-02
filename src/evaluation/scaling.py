"""Scaling, precision, and sample-size evaluation on seeded datasets.

The six-example demo set is a determinism showcase but supports no statistics. This
module runs the harness over seeded, balanced datasets and reports per-category
accuracy with **descriptive bootstrap intervals** — real variance, still
deterministic. The data is realistic-but-synthetic, so this measures the
machinery's scaling and dispersion, not real-world accuracy.
"""

from __future__ import annotations

from typing import cast

from ..compiler.metrics import answer_score, efficiency_score, grounding_score, harness_metric
from ..config import HarnessConfig, default_config
from ..compiler.metrics import EvalExample
from ..harness import AutoHarness, build_run_fn
from ..signatures import TaskCategory
from .budget import lexical_only, semantic_only, tight_eval_config
from .accounting import (
    deterministic_events,
    fingerprint_config,
    fingerprint_examples,
    fingerprint_files,
    ledger_row,
    runtime_provenance,
)
from .dataset import build_large_dataset, build_research_dataset
from .statistics import (
    bootstrap_mean,
    clustered_bootstrap_mean,
    clustered_paired_comparison,
    holm_named,
    sample_size_for_precision,
    stratified_bootstrap_mean,
)

DEFAULT_SAMPLE_SIZE_VALUES = (10, 25, 50, 100)
DEFAULT_SAMPLE_SIZE_SEEDS = (0, 1, 2, 3, 4)


def bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float, float]:
    """Return (mean, lo, hi) with a descriptive percentile bootstrap interval.
    Deterministic via seed.

    A single observation has no spread to resample, so its bootstrap interval is
    degenerate (zero width); we return the point for all three rather than implying
    precision. Callers report CIs only for samples well above this (n>=10 here), so
    the degenerate branch never fires in practice — it just refuses to fake an
    uncertainty claim.
    """
    if not values:
        return 0.0, 0.0, 0.0
    if n_boot <= 0:
        raise ValueError(f"n_boot must be positive, got {n_boot}")
    estimate = bootstrap_mean(
        values,
        resamples=n_boot,
        seed=seed,
        confidence=1.0 - alpha,
    )
    return estimate.estimate, estimate.low, estimate.high


def large_dataset_eval(per_category: int = 50, seed: int = 0, n_boot: int = 2000) -> dict:
    """Per-category accuracy and overall composite with bootstrap intervals on the large set."""
    dataset = build_large_dataset(per_category=per_category, seed=seed)
    run = build_run_fn(default_config())
    by_category: dict[str, list[float]] = {}
    composites: list[float] = []
    for example in dataset:
        out = run(example)
        category = example.task_category or TaskCategory.SINGLE_SESSION
        by_category.setdefault(category.name.lower(), []).append(answer_score(out, example))
        composites.append(harness_metric(out, example))

    category_estimates = {
        cat: bootstrap_mean(vals, resamples=n_boot, seed=seed, confidence=0.95)
        for cat, vals in by_category.items()
    }
    category_acc = {
        cat: (estimate.estimate, estimate.low, estimate.high)
        for cat, estimate in category_estimates.items()
    }
    composite_estimate = bootstrap_mean(composites, resamples=n_boot, seed=seed, confidence=0.95)
    accuracy_values = [value for values in by_category.values() for value in values]
    accuracy_estimate = bootstrap_mean(accuracy_values, resamples=n_boot, seed=seed, confidence=0.95)
    return {
        "n": len(dataset),
        "per_category": per_category,
        "seed": seed,
        "confidence": composite_estimate.confidence,
        "n_boot": n_boot,
        "composite_mean": composite_estimate.estimate,
        "composite_lo": composite_estimate.low,
        "composite_hi": composite_estimate.high,
        "accuracy_mean": accuracy_estimate.estimate,
        "accuracy_lo": accuracy_estimate.low,
        "accuracy_hi": accuracy_estimate.high,
        "composite_statistics": composite_estimate.to_dict(),
        "accuracy_statistics": accuracy_estimate.to_dict(),
        "category_accuracy": category_acc,  # name -> (mean, lo, hi)
        "category_statistics": {cat: estimate.to_dict() for cat, estimate in category_estimates.items()},
        "sample_accounting": {
            "dataset": "seeded_synthetic",
            "synthetic": True,
            "seed_values": [seed],
            "categories": sorted(by_category),
            "n_requested": len(dataset),
            "n_evaluated": len(composites),
            "n_failed": 0,
        },
    }


def _metric_vectors(
    dataset: list[EvalExample],
    config: HarnessConfig,
    *,
    method: str,
    config_fingerprint: str,
    dataset_fingerprint: str,
    sequence_start: int = 1,
) -> tuple[dict[str, list[float]], list[dict]]:
    """Evaluate one config once and retain paired component vectors."""
    vectors: dict[str, list[float]] = {"composite": [], "accuracy": [], "grounding": [], "efficiency": []}
    ledger: list[dict] = []
    with AutoHarness(config=config) as harness:
        for sequence, example in enumerate(dataset, start=sequence_start):
            try:
                output = harness.run(example)
                metrics = {
                    "accuracy": answer_score(output, example),
                    "grounding": grounding_score(output, example),
                    "efficiency": efficiency_score(output),
                    "composite": harness_metric(output, example),
                }
                for metric, value in metrics.items():
                    vectors[metric].append(value)
                ledger.append(ledger_row(
                    sequence=sequence, example=example, method=method, metrics=metrics,
                    status="complete", config_fingerprint=config_fingerprint,
                    dataset_fingerprint=dataset_fingerprint,
                ))
            except Exception as exc:  # pragma: no cover - guarded failure path
                ledger.append(ledger_row(
                    sequence=sequence, example=example, method=method, metrics=None,
                    status="failed", error=exc, config_fingerprint=config_fingerprint,
                    dataset_fingerprint=dataset_fingerprint,
                ))
    return vectors, ledger


def sample_size_scaling_eval(
    per_category_values: tuple[int, ...] = DEFAULT_SAMPLE_SIZE_VALUES,
    seeds: tuple[int, ...] = DEFAULT_SAMPLE_SIZE_SEEDS,
    n_boot: int = 2000,
    *,
    include_ledger: bool = False,
) -> dict:
    """Measure precision as seeded sample size grows, with paired method tests.

    Each row evaluates lexical-only, surrogate-semantic-only, and hybrid retrieval
    on the *same examples*.  The row aggregates independent seeded datasets and
    reports stratum- and seed-cluster-aware descriptive intervals, paired deltas,
    sign-flip randomization p-values, Holm-adjusted p-values for the complete comparison
    family, and complete sample accounting.
    ``per_category_values`` is per seed; total evaluated examples are multiplied
    by the number of categories and seeds.
    """
    if not per_category_values or any(value <= 0 for value in per_category_values):
        raise ValueError("per_category_values must be a non-empty tuple of positive integers")
    if tuple(sorted(set(per_category_values))) != per_category_values:
        raise ValueError("per_category_values must be strictly increasing")
    if not seeds:
        raise ValueError("seeds must be non-empty")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")
    if n_boot <= 0:
        raise ValueError(f"n_boot must be positive, got {n_boot}")

    # The slack default budget makes all lanes tie on many synthetic examples.
    # Use the documented tight budget here so the paired method comparison tests
    # the retrieval decision rather than only reproducing an easy upper bound.
    base = tight_eval_config()
    configs = {
        "hybrid": base,
        "lexical": lexical_only(base),
        "semantic": semantic_only(base),
    }
    rows: list[dict] = []
    accounting_runs: list[dict] = []
    ledger: list[dict] = []
    family_p_values: dict[str, float] = {}
    family_name = "sample_size_scaling_all_rows_methods_and_strata"
    category_count = len(TaskCategory)

    for per_category in per_category_values:
        aggregate: dict[str, dict[str, list[float]]] = {
            method: {metric: [] for metric in ("composite", "accuracy", "grounding", "efficiency")}
            for method in configs
        }
        for seed in seeds:
            from dataclasses import replace

            dataset = [
                replace(example, example_id=f"n{per_category}-{example.example_id}")
                for example in build_research_dataset(per_category=per_category, seed=seed)
            ]
            dataset_fingerprint = fingerprint_examples(dataset)
            seed_vectors: dict[str, dict[str, list[float]]] = {}
            seed_ledger: list[dict] = []
            sequence_cursor = len(ledger) + 1
            for method, config in configs.items():
                vectors, method_ledger = _metric_vectors(
                    dataset,
                    config,
                    method=method,
                    config_fingerprint=fingerprint_config(config),
                    dataset_fingerprint=dataset_fingerprint,
                    sequence_start=sequence_cursor,
                )
                seed_vectors[method] = vectors
                seed_ledger.extend(method_ledger)
                sequence_cursor += len(method_ledger)
            ledger.extend(seed_ledger)
            for method, vectors in seed_vectors.items():
                for metric, values in vectors.items():
                    aggregate[method][metric].extend(values)
            n_failed = sum(row["status"] != "complete" for row in seed_ledger)
            accounting_runs.append(
                {
                    "experiment": "sample_size_scaling",
                    "per_category": per_category,
                    "seed": seed,
                    "n_requested": len(dataset),
                    "n_requested_method_evaluations": len(dataset) * len(configs),
                    "n_evaluated": len(dataset) * len(configs) - n_failed,
                    "n_failed": n_failed,
                    "n_completed_examples": len(dataset) if n_failed == 0 else None,
                    "methods": list(configs),
                    "status": "complete" if n_failed == 0 else "partial",
                }
            )

        method_seeds = {"hybrid": per_category + 1000, "lexical": per_category + 1100, "semantic": per_category + 1200}
        method_statistics: dict[str, dict] = {}
        cluster_statistics: dict[str, dict] = {}
        stratum_statistics: dict[str, dict[str, dict]] = {}
        completed_values: dict[str, dict[str, tuple[str, str, float]]] = {}
        # Reconstruct the metadata views from ledger rows rather than assuming every
        # method succeeded. This keeps partial/failure accounting usable if a future
        # evaluator encounters an exception for one example.
        from dataclasses import replace

        example_by_id = {
            f"n{per_category}-{example.example_id}": replace(
                example, example_id=f"n{per_category}-{example.example_id}"
            )
            for seed in seeds
            for example in build_research_dataset(per_category=per_category, seed=seed)
        }
        for method, method_values in aggregate.items():
            strata: dict[str, list[float]] = {}
            clusters: dict[str | int, list[float]] = {}
            completed_rows = [
                row for row in ledger
                if row["method"] == method
                and row["status"] == "complete"
                and row["example_id"] in example_by_id
            ]
            if len(completed_rows) != len(method_values["composite"]):
                raise RuntimeError(f"ledger/metric count mismatch for {method} at per_category={per_category}")
            method_values_by_id: dict[str, tuple[str, str, float]] = {}
            for row, value in zip(completed_rows, method_values["composite"]):
                example = example_by_id[row["example_id"]]
                strata.setdefault(example.stratum, []).append(value)
                clusters.setdefault(str(example.seed), []).append(value)
                method_values_by_id[str(row["example_id"])] = (
                    str(row.get("seed")),
                    str(row.get("stratum", example.stratum)),
                    float(value),
                )
            completed_values[method] = method_values_by_id
            method_statistics[method] = stratified_bootstrap_mean(
                strata, resamples=n_boot, seed=method_seeds[method], confidence=0.95,
                unit="unique_eval_example",
            ).to_dict()
            cluster_statistics[method] = clustered_bootstrap_mean(
                clusters, resamples=n_boot, seed=method_seeds[method] + 500,
                confidence=0.95, unit="seed_cluster",
            ).to_dict()
            stratum_statistics[method] = {
                stratum: bootstrap_mean(values_for_stratum, resamples=n_boot, seed=method_seeds[method] + index, confidence=0.95).to_dict()
                for index, (stratum, values_for_stratum) in enumerate(sorted(strata.items()))
            }
        def clustered_pair(baseline: str, *, stratum: str | None = None, seed_offset: int) -> dict[str, object]:
            """Build aligned method vectors, dropping only incomplete pairs."""
            shared_ids = sorted(set(completed_values["hybrid"]) & set(completed_values[baseline]))
            left_by_cluster: dict[str, list[float]] = {}
            right_by_cluster: dict[str, list[float]] = {}
            for example_id in shared_ids:
                left_seed, left_stratum, left_value = completed_values["hybrid"][example_id]
                right_seed, right_stratum, right_value = completed_values[baseline][example_id]
                if left_seed != right_seed or left_stratum != right_stratum:
                    raise RuntimeError(f"paired metadata mismatch for {example_id}")
                if stratum is not None and left_stratum != stratum:
                    continue
                left_by_cluster.setdefault(left_seed, []).append(left_value)
                right_by_cluster.setdefault(right_seed, []).append(right_value)
            if not left_by_cluster:
                return {
                    "status": "unavailable",
                    "reason": "no_complete_pairs",
                    "n": 0,
                    "comparison_family": family_name,
                }
            return clustered_paired_comparison(
                left_by_cluster,
                right_by_cluster,
                resamples=n_boot,
                permutations=n_boot,
                bootstrap_seed=per_category + seed_offset,
                permutation_seed=per_category + seed_offset + 1000,
                confidence=0.95,
            ).to_dict()

        comparisons: dict[str, dict[str, object]] = {}
        stratum_paired_comparisons: dict[str, dict[str, dict[str, object]]] = {}
        stratum_names = sorted({stratum for values in stratum_statistics.values() for stratum in values})
        for baseline, offset, key in (
            ("lexical", 2000, "hybrid_vs_lexical"),
            ("semantic", 4000, "hybrid_vs_semantic"),
        ):
            comparisons[key] = clustered_pair(baseline, seed_offset=offset)
            if "p_value" in comparisons[key]:
                family_p_values[f"n{per_category}:overall:{key}"] = cast(float, comparisons[key]["p_value"])
            stratum_paired_comparisons[key] = {}
            for index, stratum in enumerate(stratum_names):
                comparison = clustered_pair(
                    baseline,
                    stratum=stratum,
                    seed_offset=offset + 100 + index,
                )
                stratum_paired_comparisons[key][stratum] = comparison
                if "p_value" in comparison:
                    family_p_values[f"n{per_category}:stratum:{stratum}:{key}"] = cast(float, comparison["p_value"])

        hybrid_stats = method_statistics["hybrid"]
        sd = float(hybrid_stats["standard_deviation"])
        rows.append(
            {
                "per_category": per_category,
                "n_per_seed": per_category * category_count,
                "n_total": per_category * category_count * len(seeds),
                "n_seeds": len(seeds),
                "methods": method_statistics,
                "cluster_statistics": cluster_statistics,
                "stratum_statistics": stratum_statistics,
                "paired_comparisons": comparisons,
                "stratum_paired_comparisons": stratum_paired_comparisons,
                "comparison_family": family_name,
                "precision_plan": {
                    "target_half_width": 0.03,
                    "estimated_n_for_target": sample_size_for_precision(sd, half_width=0.03),
                    "source_standard_deviation": sd,
                    "estimand": "mean_composite",
                    "unit": "unique_eval_example",
                    "strata": sorted({example.stratum for seed in seeds for example in build_research_dataset(per_category=per_category, seed=seed)}),
                    "cluster_count": len(seeds),
                    "interpretation": "precision heuristic; not a power calculation",
                },
            }
        )

    adjusted_family = holm_named(family_p_values)
    for row in rows:
        for key, comparison in row["paired_comparisons"].items():
            family_key = f"n{row['per_category']}:overall:{key}"
            if family_key in adjusted_family:
                comparison["holm_adjusted_p_value"] = adjusted_family[family_key]
            comparison["comparison_family"] = family_name
        for comparison_key, by_stratum in row["stratum_paired_comparisons"].items():
            for stratum, comparison in by_stratum.items():
                family_key = f"n{row['per_category']}:stratum:{stratum}:{comparison_key}"
                if family_key in adjusted_family:
                    comparison["holm_adjusted_p_value"] = adjusted_family[family_key]
                comparison["comparison_family"] = family_name

    n_requested = sum(run["n_requested"] for run in accounting_runs)
    failure_by_method: dict[str, int] = {}
    for row in ledger:
        if row["status"] != "complete":
            method = str(row["method"])
            failure_by_method[method] = failure_by_method.get(method, 0) + 1
    content_by_example = {
        str(row["example_id"]): str(row["content_fingerprint"])
        for row in ledger
        if row.get("content_fingerprint")
    }
    content_fingerprints = set(content_by_example.values())
    from dataclasses import replace

    all_examples = [
        replace(example, example_id=f"n{per_category}-{example.example_id}")
        for per_category in per_category_values
        for seed in seeds
        for example in build_research_dataset(per_category=per_category, seed=seed)
    ]
    dataset_fingerprint = fingerprint_examples(all_examples)
    source_fingerprint = fingerprint_files([
        __file__,
        __file__.replace("scaling.py", "dataset.py"),
        __file__.replace("scaling.py", "statistics.py"),
    ])
    result = {
        "experiment": "seeded_sample_size_scaling",
        "dataset": "stratified_seeded_synthetic_research",
        "categories": category_count,
        "per_category_values": list(per_category_values),
        "seed_values": list(seeds),
        "confidence": 0.95,
        "n_boot": n_boot,
        "config": base.to_dict(),
        "dataset_fingerprint": dataset_fingerprint,
        "source_fingerprint": source_fingerprint,
        "comparison_family": {
            "name": family_name,
            "size": len(family_p_values),
            "correction": "holm_step_down",
        },
        "analysis_contract": {
            "primary_estimand": "mean_composite_over_finite_generated_examples",
            "observation_unit": "unique_eval_example",
            "comparison_unit": "paired_example_within_seed_cluster",
            "primary_comparisons": ["hybrid_vs_lexical", "hybrid_vs_semantic"],
            "strata": sorted({row["stratum"] for row in ledger}),
            "clusters": [str(seed) for seed in seeds],
            "cluster_count": len(seeds),
            "interval_interpretation": "descriptive_cluster_resampling_interval",
            "small_cluster_warning": len(seeds) < 10,
            "missing_data": "failed rows remain in requested denominators; comparisons use complete pairs",
            "multiple_comparison_scope": family_name,
            "synthetic_scope": "finite generated task family; not a population estimate",
        },
        "rows": rows,
        "accounting": {
            "schema_version": 2,
            "experiment": "seeded_sample_size_scaling",
            "unit": "unique_eval_example",
            "synthetic": True,
            "categories": category_count,
            "per_category_values": list(per_category_values),
            "seed_values": list(seeds),
            "n_requested": n_requested,
            "n_requested_examples": n_requested,
            "n_requested_method_evaluations": n_requested * len(configs),
            "n_evaluated": sum(run["n_evaluated"] for run in accounting_runs),
            "n_completed_method_evaluations": sum(run["n_evaluated"] for run in accounting_runs),
            "n_failed": sum(run["n_failed"] for run in accounting_runs),
            "failure_by_method": failure_by_method,
            "n_method_evaluations": n_requested * len(configs),
            "n_unique_examples": len({row["example_id"] for row in ledger}),
            "n_unique_content_fingerprints": len(content_fingerprints),
            "n_reused_content_examples": len(content_by_example) - len(content_fingerprints),
            "dataset_fingerprint": dataset_fingerprint,
            "source_fingerprint": source_fingerprint,
            "estimand": "mean_composite",
            "strata": sorted({row["stratum"] for row in ledger}),
            "cluster_count": len(seeds),
            "small_cluster_warning": len(seeds) < 10,
            "runtime_provenance": runtime_provenance(),
            "runs": accounting_runs,
        },
    }
    if include_ledger:
        result["ledger"] = ledger
        result["events"] = deterministic_events(
            ledger,
            experiment="seeded_sample_size_scaling",
            dataset_fingerprint=dataset_fingerprint,
            config_fingerprint=fingerprint_config(base),
            run_id=f"scaling-{dataset_fingerprint[:16]}",
        )
    return result


__all__ = [
    "DEFAULT_SAMPLE_SIZE_SEEDS",
    "DEFAULT_SAMPLE_SIZE_VALUES",
    "bootstrap_ci",
    "large_dataset_eval",
    "sample_size_scaling_eval",
]
