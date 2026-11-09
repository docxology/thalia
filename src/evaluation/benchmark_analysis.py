"""Pure, descriptive accounting for finite within-backend method observations.

Seed means, not individual synthetic examples, are the resampling units. These
intervals do not establish population power, significance, or expert quality.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Sequence

from .statistics import _quantile, clustered_bootstrap_mean

ANALYSIS_UNIT = "seed_mean_paired_token_f1_delta"


def summarize_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Account for every requested cell, with success-only descriptive means."""
    successes = [row for row in rows if row["status"] == "complete"]
    latencies = sorted(row["latency_seconds"] for row in successes)
    return {
        "status": "complete" if len(successes) == len(rows) else "incomplete",
        "n_requested": len(rows),
        "n_completed": len(successes),
        "n_failed": len(rows) - len(successes),
        "mean_token_f1": mean(row["token_f1"] for row in successes) if successes else None,
        "mean_latency_seconds": mean(latencies) if successes else None,
        "p50_latency_seconds": _quantile(latencies, 0.5) if successes else None,
        "p95_latency_seconds": _quantile(latencies, 0.95) if successes else None,
        "mean_prompt_characters": mean(row["prompt_characters"] for row in successes) if successes else None,
    }


def summarize_prompt_exposure(
    rows: Sequence[dict[str, Any]], *, methods: Sequence[str],
    example_ids: Sequence[str], reference_method: str,
) -> list[dict[str, Any]]:
    """Describe recorded attempted prompts from already validated benchmark rows.

    Backends share one prompt per method/example; failed attempts with a captured
    fingerprint still count, while empty failed rows cannot erase that capture.
    Groups require complete, identical vectors in the supplied example order.
    They describe this cohort's recorded text, not equivalent computation,
    latency, quality, provider retention, or authenticated inference traffic.
    """
    captured: dict[tuple[str, str], str] = {}
    for row in rows:
        fingerprints = row["prompt_fingerprints"]
        if fingerprints:
            captured.setdefault((row["method"], row["example_id"]), fingerprints[0])

    reference = (
        tuple(captured.get((reference_method, example_id)) for example_id in example_ids)
        if reference_method in methods else None
    )
    groups: dict[tuple[str | None, ...], int] = {}
    summaries = []
    for method in methods:
        vector = tuple(captured.get((method, example_id)) for example_id in example_ids)
        observed = [fingerprint for fingerprint in vector if fingerprint is not None]
        paired = (
            [(candidate, baseline) for candidate, baseline in zip(vector, reference)
             if candidate is not None and baseline is not None]
            if reference is not None else []
        )
        group = None
        if vector and len(observed) == len(vector):
            group = groups.setdefault(vector, len(groups) + 1)
        summaries.append({
            "method": method,
            "n_requested_cases": len(example_ids),
            "n_observed_cases": len(observed),
            "n_unique_prompts": len(set(observed)),
            "n_compared_to_reference": len(paired),
            "n_different_from_reference": (
                sum(candidate != baseline for candidate, baseline in paired)
                if reference is not None else None
            ),
            "prompt_group": group,
        })
    return summaries


def summarize_seed_pairs(
    rows: Sequence[dict[str, Any]], *, backends: Sequence[str], methods: Sequence[str],
    examples: Sequence[dict[str, Any]], reference_method: str,
) -> list[dict[str, Any]]:
    """Audit paired scores per represented seed from already validated rows.

    Backend and non-reference method order follow the selections; seeds are
    sorted numerically, including seeds with no surviving pairs. Wins, ties and
    losses describe complete raw pairs only. Any failed pair suppresses that
    seed's mean, not its counts. These diagnostics neither resample nor replace
    the report's complete-contrast, equally weighted seed-mean estimate.
    """
    if reference_method not in methods:
        return []
    matrix = {(row["backend"], row["method"], row["example_id"]): row for row in rows}
    by_seed: dict[int, list[dict[str, Any]]] = {}
    for example in examples:
        by_seed.setdefault(example["seed"], []).append(example)
    summaries = []
    for backend in backends:
        for method in methods:
            if method == reference_method:
                continue
            for seed, planned in sorted(by_seed.items()):
                deltas = []
                for example in planned:
                    candidate = matrix[(backend, method, example["example_id"])]
                    reference = matrix[(backend, reference_method, example["example_id"])]
                    if candidate["status"] == "complete" and reference["status"] == "complete":
                        deltas.append(candidate["token_f1"] - reference["token_f1"])
                complete = len(deltas) == len(planned)
                summaries.append({
                    "backend": backend, "method": method, "reference_method": reference_method,
                    "seed": seed, "status": "complete" if complete else "incomplete",
                    "n_requested_pairs": len(planned), "n_complete_pairs": len(deltas),
                    "wins": sum(delta > 0 for delta in deltas),
                    "ties": sum(delta == 0 for delta in deltas),
                    "losses": sum(delta < 0 for delta in deltas),
                    "mean_delta": mean(deltas) if complete else None,
                })
    return summaries


def analyze_benchmark_rows(
    rows: Sequence[dict[str, Any]], *, backends: Sequence[str], methods: Sequence[str],
    examples: Sequence[dict[str, Any]], reference_method: str, n_boot: int,
    analysis_seed: int,
) -> dict[str, Any]:
    """Rebuild summaries, grouped accounting and complete-pair seed contrasts.

    One missing pair suppresses the complete contrast, not its failure counts.
    Wins/ties/losses describe the available complete raw pairs even in that case.
    """
    matrix = {(row["backend"], row["method"], row["example_id"]): row for row in rows}
    summaries = []
    groups: dict[str, list[dict[str, Any]]] = {"category": [], "stratum": []}
    comparisons = []
    for backend in backends:
        for method in methods:
            selected = [matrix[(backend, method, example["example_id"])] for example in examples]
            summaries.append({"backend": backend, "method": method, **summarize_rows(selected)})
            for field in groups:
                for value in sorted({example[field] for example in examples}):
                    grouped = [row for row in selected if row[field] == value]
                    groups[field].append({"backend": backend, "method": method, field: value, **summarize_rows(grouped)})
            if method == reference_method or reference_method not in methods:
                continue
            deltas: list[float] = []
            by_seed: dict[int, list[float]] = {}
            for example in examples:
                candidate = matrix[(backend, method, example["example_id"])]
                reference = matrix[(backend, reference_method, example["example_id"])]
                if candidate["status"] != "complete" or reference["status"] != "complete":
                    continue
                delta = candidate["token_f1"] - reference["token_f1"]
                deltas.append(delta)
                by_seed.setdefault(example["seed"], []).append(delta)
            complete = len(deltas) == len(examples)
            seed_means = {seed: [mean(values)] for seed, values in sorted(by_seed.items())}
            interval = None
            if complete and len(seed_means) >= 2:
                interval = clustered_bootstrap_mean(
                    seed_means, resamples=n_boot, seed=analysis_seed,
                    confidence=0.95, unit=ANALYSIS_UNIT,
                ).to_dict()
            comparisons.append({
                "backend": backend, "method": method, "reference_method": reference_method,
                "status": "complete" if complete else "incomplete",
                "n_requested_pairs": len(examples), "n_complete_pairs": len(deltas),
                "n_seed_clusters": len(seed_means),
                "wins": sum(delta > 0 for delta in deltas),
                "ties": sum(delta == 0 for delta in deltas),
                "losses": sum(delta < 0 for delta in deltas),
                "mean_delta": mean(values[0] for values in seed_means.values()) if complete else None,
                "interval": interval,
            })
    return {"summaries": summaries, "groups": groups, "comparisons": comparisons}


__all__ = [
    "ANALYSIS_UNIT", "summarize_rows", "summarize_prompt_exposure",
    "summarize_seed_pairs", "analyze_benchmark_rows",
]
