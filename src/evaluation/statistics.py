"""Reproducible statistical summaries and evaluation accounting.

The deterministic THALIA experiments are synthetic or locally replayable, but a
point estimate alone is not evidence of precision.  This module keeps the
statistical layer dependency-free and explicit:

* percentile bootstrap intervals for continuous metrics;
* fixed-size within-stratum and cluster-resampling bootstrap intervals;
* Wilson intervals for binary/rate metrics;
* exact paired binary (McNemar) comparisons;
* paired bootstrap deltas and deterministic sign-flip permutation tests;
* paired standardized effect sizes;
* named complete-family Holm correction; and
* iid and design-effect-adjusted sample-size planners for a requested half-width.

Every randomized procedure takes an explicit seed.  Returned records carry the
sample size, confidence level, seed, resample count, and method so a figure or
aggregate cannot lose its statistical provenance.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_Z_VALUES = {
    0.80: 1.2815515655446004,
    0.90: 1.6448536269514722,
    0.95: 1.959963984540054,
    0.99: 2.5758293035489004,
}
_SMALL_CLUSTER_THRESHOLD = 10


@dataclass(frozen=True)
class StatisticalEstimate:
    """An estimate with explicit uncertainty and computation provenance."""

    estimate: float
    low: float
    high: float
    n: int
    confidence: float
    method: str
    seed: int
    resamples: int
    standard_deviation: float
    standard_error: float
    median: float
    estimand: str = "mean"
    unit: str = "observation"
    strata: tuple[str, ...] = ()
    cluster_count: int = 0
    resample_provenance: str = "iid_observation_bootstrap"
    interval_interpretation: str = "descriptive_resampling_interval"
    small_cluster_warning: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-ready record."""
        return {
            "estimate": self.estimate,
            "low": self.low,
            "high": self.high,
            "n": self.n,
            "confidence": self.confidence,
            "method": self.method,
            "seed": self.seed,
            "resamples": self.resamples,
            "standard_deviation": self.standard_deviation,
            "standard_error": self.standard_error,
            "median": self.median,
            "estimand": self.estimand,
            "unit": self.unit,
            "strata": list(self.strata),
            "cluster_count": self.cluster_count,
            "resample_provenance": self.resample_provenance,
            "interval_interpretation": self.interval_interpretation,
            "small_cluster_warning": self.small_cluster_warning,
        }


@dataclass(frozen=True)
class PairedComparison:
    """Uncertainty-aware comparison of two methods on the same examples."""

    n: int
    mean_delta: float
    low: float
    high: float
    p_value: float
    effect_size: float | None
    confidence: float
    bootstrap_seed: int
    permutation_seed: int
    resamples: int
    permutations: int
    estimand: str = "mean_paired_delta"
    unit: str = "paired_observation"
    cluster_count: int = 0
    comparison_family: str = ""
    inferential_status: str = "paired_randomization_summary"
    small_cluster_warning: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-ready record."""
        return {
            "n": self.n,
            "mean_delta": self.mean_delta,
            "low": self.low,
            "high": self.high,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "confidence": self.confidence,
            "bootstrap_seed": self.bootstrap_seed,
            "permutation_seed": self.permutation_seed,
            "resamples": self.resamples,
            "permutations": self.permutations,
            "estimand": self.estimand,
            "unit": self.unit,
            "cluster_count": self.cluster_count,
            "comparison_family": self.comparison_family,
            "inferential_status": self.inferential_status,
            "small_cluster_warning": self.small_cluster_warning,
        }


@dataclass(frozen=True)
class BinaryRateEstimate:
    """A binary success rate with Wilson uncertainty and explicit unit metadata."""

    successes: int
    trials: int
    rate: float
    low: float
    high: float
    confidence: float
    method: str = "wilson_score"
    estimand: str = "success_probability"
    unit: str = "binary_observation"

    def to_dict(self) -> dict[str, object]:
        return {
            "successes": self.successes,
            "trials": self.trials,
            "rate": self.rate,
            "low": self.low,
            "high": self.high,
            "confidence": self.confidence,
            "method": self.method,
            "estimand": self.estimand,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class PairedBinaryComparison:
    """Exact paired binary comparison (McNemar's discordant pairs)."""

    n: int
    left_success_right_failure: int
    left_failure_right_success: int
    delta: float
    p_value: float
    method: str = "exact_mcnemar_binomial"

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "left_success_right_failure": self.left_success_right_failure,
            "left_failure_right_success": self.left_failure_right_success,
            "delta": self.delta,
            "p_value": self.p_value,
            "method": self.method,
        }


def _values(values: Iterable[float], *, name: str = "values") -> list[float]:
    """Materialize and validate a finite non-empty sample."""
    result = [float(value) for value in values]
    if not result:
        raise ValueError(f"{name} must be non-empty")
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _binary_values(values: Iterable[bool | int], *, name: str) -> list[bool]:
    """Materialize strict binary observations without truthiness coercion."""
    result: list[bool] = []
    for value in values:
        if isinstance(value, bool):
            result.append(value)
        elif isinstance(value, int) and value in (0, 1):
            result.append(bool(value))
        else:
            raise ValueError(f"{name} must contain only binary bool or integer 0/1 values")
    if not result:
        raise ValueError(f"{name} must be non-empty")
    return result


def _grouped_values(values_by_group: Mapping[Any, Iterable[float]], *, label: str) -> dict[str, list[float]]:
    """Normalize grouping keys while rejecting collisions such as ``1``/``'1'``."""
    normalized: dict[str, list[float]] = {}
    for key, values in values_by_group.items():
        name = str(key)
        if name in normalized:
            raise ValueError(f"{label} keys collide after string normalization: {name!r}")
        normalized[name] = _values(values, name=f"{label} {key}")
    if not normalized:
        raise ValueError(f"values_by_{label} must be non-empty")
    return normalized


def _validate_confidence(confidence: float) -> None:
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")


def _z_value(confidence: float) -> float:
    """Return a standard-normal critical value without a scipy dependency."""
    _validate_confidence(confidence)
    if confidence in _Z_VALUES:
        return _Z_VALUES[confidence]
    # A compact Acklam-style approximation for the upper-tail quantile.
    p = (1.0 + confidence) / 2.0
    if p < 0.5:
        p = 1.0 - p
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    numerator = ((2.515517 + 0.802853 * t) + 0.010328 * t * t)
    denominator = 1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t**3
    return t - numerator / denominator


def _quantile(sorted_values: Sequence[float], probability: float) -> float:
    """Linearly interpolate an empirical quantile."""
    if not sorted_values:
        raise ValueError("sorted_values must be non-empty")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower]))


def _sample_sd(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def bootstrap_mean(
    values: Iterable[float],
    *,
    resamples: int = 5000,
    seed: int = 0,
    confidence: float = 0.95,
) -> StatisticalEstimate:
    """Estimate a mean and percentile bootstrap confidence interval."""
    sample = _values(values)
    if resamples <= 0:
        raise ValueError(f"resamples must be positive, got {resamples}")
    _validate_confidence(confidence)
    n = len(sample)
    estimate = sum(sample) / n
    sd = _sample_sd(sample)
    if n == 1:
        low = high = estimate
        median = estimate
    else:
        rng = random.Random(seed)
        means = []
        for _ in range(resamples):
            means.append(sum(sample[rng.randrange(n)] for _ in range(n)) / n)
        means.sort()
        alpha = 1.0 - confidence
        low = _quantile(means, alpha / 2.0)
        high = _quantile(means, 1.0 - alpha / 2.0)
        ordered = sorted(sample)
        median = _quantile(ordered, 0.5)
    return StatisticalEstimate(
        estimate=estimate,
        low=low,
        high=high,
        n=n,
        confidence=confidence,
        method="percentile_bootstrap_mean",
        seed=seed,
        resamples=0 if n == 1 else resamples,
        standard_deviation=sd,
        standard_error=sd / math.sqrt(n),
        median=median,
    )


def stratified_bootstrap_mean(
    values_by_stratum: Mapping[str, Iterable[float]],
    *,
    resamples: int = 5000,
    seed: int = 0,
    confidence: float = 0.95,
    unit: str = "observation",
) -> StatisticalEstimate:
    """Bootstrap a weighted overall mean while resampling within each stratum.

    Every stratum retains its observed sample size.  This is the appropriate
    default for the balanced research audit and avoids allowing a large stratum to
    disappear merely because of a resampling draw.
    """
    strata = _grouped_values(values_by_stratum, label="stratum")
    if resamples <= 0:
        raise ValueError(f"resamples must be positive, got {resamples}")
    _validate_confidence(confidence)
    flattened = [value for values in strata.values() for value in values]
    estimate = sum(flattened) / len(flattened)
    if len(flattened) == 1:
        low = high = median = estimate
        used_resamples = 0
    else:
        rng = random.Random(seed)
        means: list[float] = []
        for _ in range(resamples):
            draw = [values[rng.randrange(len(values))] for values in strata.values() for _ in values]
            means.append(sum(draw) / len(draw))
        means.sort()
        alpha = 1.0 - confidence
        low = _quantile(means, alpha / 2.0)
        high = _quantile(means, 1.0 - alpha / 2.0)
        median = _quantile(sorted(flattened), 0.5)
        used_resamples = resamples
    sd = _sample_sd(flattened)
    return StatisticalEstimate(
        estimate=estimate,
        low=low,
        high=high,
        n=len(flattened),
        confidence=confidence,
        method="stratified_percentile_bootstrap_mean",
        seed=seed,
        resamples=used_resamples,
        standard_deviation=sd,
        standard_error=sd / math.sqrt(len(flattened)),
        median=median,
        unit=unit,
        strata=tuple(sorted(strata)),
        resample_provenance="within_stratum_resampling_fixed_stratum_sizes",
    )


def clustered_bootstrap_mean(
    values_by_cluster: Mapping[Any, Iterable[float]],
    *,
    resamples: int = 5000,
    seed: int = 0,
    confidence: float = 0.95,
    unit: str = "observation",
) -> StatisticalEstimate:
    """Bootstrap clusters, retaining all observations in each selected cluster."""
    clusters = _grouped_values(values_by_cluster, label="cluster")
    if resamples <= 0:
        raise ValueError(f"resamples must be positive, got {resamples}")
    _validate_confidence(confidence)
    flattened = [value for values in clusters.values() for value in values]
    estimate = sum(flattened) / len(flattened)
    if len(clusters) == 1:
        low = high = median = estimate
        used_resamples = 0
    else:
        keys = tuple(sorted(clusters))
        rng = random.Random(seed)
        means: list[float] = []
        for _ in range(resamples):
            selected = [keys[rng.randrange(len(keys))] for _ in keys]
            draw = [value for key in selected for value in clusters[key]]
            means.append(sum(draw) / len(draw))
        means.sort()
        alpha = 1.0 - confidence
        low = _quantile(means, alpha / 2.0)
        high = _quantile(means, 1.0 - alpha / 2.0)
        median = _quantile(sorted(flattened), 0.5)
        used_resamples = resamples
    sd = _sample_sd(flattened)
    return StatisticalEstimate(
        estimate=estimate,
        low=low,
        high=high,
        n=len(flattened),
        confidence=confidence,
        method="cluster_percentile_bootstrap_mean",
        seed=seed,
        resamples=used_resamples,
        standard_deviation=sd,
        standard_error=sd / math.sqrt(len(flattened)),
        median=median,
        unit=unit,
        cluster_count=len(clusters),
        resample_provenance="cluster_resampling_within_cluster_observations_preserved",
        interval_interpretation="descriptive_cluster_resampling_interval",
        small_cluster_warning=len(clusters) < _SMALL_CLUSTER_THRESHOLD,
    )


def wilson_interval(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Return ``(rate, low, high)`` using the Wilson score interval."""
    if isinstance(trials, bool) or not isinstance(trials, int):
        raise ValueError(f"trials must be an integer, got {trials!r}")
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise ValueError(f"successes must be an integer, got {successes!r}")
    if trials <= 0:
        raise ValueError(f"trials must be positive, got {trials}")
    if not 0 <= successes <= trials:
        raise ValueError(f"successes must be between 0 and trials, got {successes}/{trials}")
    z = _z_value(confidence)
    rate = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (rate + z * z / (2.0 * trials)) / denominator
    radius = z * math.sqrt(rate * (1.0 - rate) / trials + z * z / (4.0 * trials * trials)) / denominator
    return rate, max(0.0, centre - radius), min(1.0, centre + radius)


def binary_rate(successes: int, trials: int, *, confidence: float = 0.95, unit: str = "binary_observation") -> BinaryRateEstimate:
    """Return a named binary-rate summary instead of an anonymous tuple."""
    rate, low, high = wilson_interval(successes, trials, confidence=confidence)
    return BinaryRateEstimate(successes, trials, rate, low, high, confidence, unit=unit)


def exact_paired_binary(left: Iterable[bool | int], right: Iterable[bool | int]) -> PairedBinaryComparison:
    """Run the exact two-sided McNemar test without SciPy.

    The p-value conditions on discordant pairs and is the exact binomial tail under
    the null that both methods have equal success probability.
    """
    left_values = _binary_values(left, name="left")
    right_values = _binary_values(right, name="right")
    if not left_values or len(left_values) != len(right_values):
        raise ValueError("left and right must be non-empty and equal length")
    b = sum(a and not c for a, c in zip(left_values, right_values))
    c = sum((not a) and c for a, c in zip(left_values, right_values))
    discordant = b + c
    if discordant == 0:
        p_value = 1.0
    else:
        lower = sum(math.comb(discordant, k) for k in range(0, min(b, c) + 1))
        upper = sum(math.comb(discordant, k) for k in range(max(b, c), discordant + 1))
        p_value = min(1.0, 2.0 * min(lower, upper) / (2.0**discordant))
    delta = sum(left_values) / len(left_values) - sum(right_values) / len(right_values)
    return PairedBinaryComparison(len(left_values), b, c, delta, p_value)


def paired_bootstrap_delta(
    left: Iterable[float],
    right: Iterable[float],
    *,
    resamples: int = 5000,
    seed: int = 0,
    confidence: float = 0.95,
) -> StatisticalEstimate:
    """Estimate ``mean(left - right)`` with a paired bootstrap interval."""
    left_values = _values(left, name="left")
    right_values = _values(right, name="right")
    if len(left_values) != len(right_values):
        raise ValueError("left and right must have equal length")
    return bootstrap_mean(
        [a - b for a, b in zip(left_values, right_values)],
        resamples=resamples,
        seed=seed,
        confidence=confidence,
    )


def paired_permutation_p_value(
    left: Iterable[float],
    right: Iterable[float],
    *,
    permutations: int = 5000,
    seed: int = 0,
) -> float:
    """Return a two-sided paired sign-flip permutation p-value.

    For samples up to 12 pairs, enumerate every sign assignment exactly.  Larger
    samples use seeded Monte Carlo sign flips with the conservative +1 correction.
    """
    left_values = _values(left, name="left")
    right_values = _values(right, name="right")
    if len(left_values) != len(right_values):
        raise ValueError("left and right must have equal length")
    if permutations <= 0:
        raise ValueError(f"permutations must be positive, got {permutations}")
    deltas = [a - b for a, b in zip(left_values, right_values)]
    observed = abs(sum(deltas) / len(deltas))
    if not any(deltas):
        return 1.0
    if len(deltas) <= 12:
        total = 1 << len(deltas)
        at_least = 0
        for mask in range(total):
            signed = sum(delta if mask & (1 << i) else -delta for i, delta in enumerate(deltas)) / len(deltas)
            at_least += int(abs(signed) >= observed - 1e-15)
        return at_least / total
    rng = random.Random(seed)
    at_least = 0
    for _ in range(permutations):
        signed = sum(delta if rng.getrandbits(1) else -delta for delta in deltas) / len(deltas)
        at_least += int(abs(signed) >= observed - 1e-15)
    return (at_least + 1) / (permutations + 1)


def paired_comparison(
    left: Iterable[float],
    right: Iterable[float],
    *,
    resamples: int = 5000,
    permutations: int = 5000,
    bootstrap_seed: int = 0,
    permutation_seed: int = 1,
    confidence: float = 0.95,
) -> PairedComparison:
    """Return paired delta, CI, p-value, and standardized effect size."""
    left_values = _values(left, name="left")
    right_values = _values(right, name="right")
    if len(left_values) != len(right_values):
        raise ValueError("left and right must have equal length")
    estimate = paired_bootstrap_delta(
        left_values,
        right_values,
        resamples=resamples,
        seed=bootstrap_seed,
        confidence=confidence,
    )
    deltas = [a - b for a, b in zip(left_values, right_values)]
    sd = _sample_sd(deltas)
    # A zero-variance paired difference has no finite standardized denominator.
    # Preserve that fact as null rather than serializing a non-standard Infinity.
    effect = estimate.estimate / sd if sd else (0.0 if estimate.estimate == 0.0 else None)
    return PairedComparison(
        n=len(deltas),
        mean_delta=estimate.estimate,
        low=estimate.low,
        high=estimate.high,
        p_value=paired_permutation_p_value(
            left_values,
            right_values,
            permutations=permutations,
            seed=permutation_seed,
        ),
        effect_size=effect,
        confidence=confidence,
        bootstrap_seed=bootstrap_seed,
        permutation_seed=permutation_seed,
        resamples=resamples,
        permutations=permutations,
    )


def clustered_paired_comparison(
    left_by_cluster: Mapping[Any, Iterable[float]],
    right_by_cluster: Mapping[Any, Iterable[float]],
    *,
    resamples: int = 5000,
    permutations: int = 5000,
    bootstrap_seed: int = 0,
    permutation_seed: int = 1,
    confidence: float = 0.95,
) -> PairedComparison:
    """Compare paired methods while treating clusters as the resampling unit.

    Observations remain paired within each cluster.  The confidence interval resamples
    whole clusters, while the permutation test sign-flips cluster-level means.  The
    reported point estimate is observation-weighted (matching the ordinary paired
    estimand); the standardized effect size is computed from cluster-level deltas so
    repeated observations in a single cluster cannot manufacture precision.
    """
    left = _grouped_values(left_by_cluster, label="cluster")
    right = _grouped_values(right_by_cluster, label="cluster")
    if set(left) != set(right):
        raise ValueError("left and right must contain the same cluster keys")
    keys = tuple(sorted(left))
    differences: dict[str, list[float]] = {}
    cluster_left_means: list[float] = []
    cluster_right_means: list[float] = []
    for key in keys:
        if len(left[key]) != len(right[key]):
            raise ValueError(f"left and right cluster {key!r} must have equal length")
        differences[key] = [a - b for a, b in zip(left[key], right[key])]
        cluster_left_means.append(sum(left[key]) / len(left[key]))
        cluster_right_means.append(sum(right[key]) / len(right[key]))
    estimate = clustered_bootstrap_mean(
        differences,
        resamples=resamples,
        seed=bootstrap_seed,
        confidence=confidence,
        unit="paired_observation",
    )
    cluster_deltas = [a - b for a, b in zip(cluster_left_means, cluster_right_means)]
    cluster_sd = _sample_sd(cluster_deltas)
    effect = estimate.estimate / cluster_sd if cluster_sd else (0.0 if estimate.estimate == 0.0 else None)
    return PairedComparison(
        n=sum(len(values) for values in left.values()),
        mean_delta=estimate.estimate,
        low=estimate.low,
        high=estimate.high,
        p_value=paired_permutation_p_value(
            cluster_left_means,
            cluster_right_means,
            permutations=permutations,
            seed=permutation_seed,
        ),
        effect_size=effect,
        confidence=confidence,
        bootstrap_seed=bootstrap_seed,
        permutation_seed=permutation_seed,
        resamples=estimate.resamples,
        permutations=permutations,
        estimand="mean_paired_delta_observation_weighted",
        unit="paired_observation",
        cluster_count=len(keys),
        comparison_family="clustered_paired_comparison",
        inferential_status="descriptive_cluster_randomization_summary",
        small_cluster_warning=len(keys) < _SMALL_CLUSTER_THRESHOLD,
    )


def holm_bonferroni(p_values: Iterable[float]) -> tuple[float, ...]:
    """Adjust p-values for multiple comparisons using Holm's step-down method."""
    values = [float(value) for value in p_values]
    if not all(0.0 <= value <= 1.0 and math.isfinite(value) for value in values):
        raise ValueError("p_values must be finite values in [0, 1]")
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    adjusted = [0.0] * len(values)
    running = 0.0
    for rank, (index, value) in enumerate(indexed):
        running = max(running, min(1.0, value * (len(values) - rank)))
        adjusted[index] = running
    return tuple(adjusted)


def holm_named(p_values: Mapping[str, float]) -> dict[str, float]:
    """Apply Holm correction once to a named, complete comparison family."""
    names = list(p_values)
    adjusted = holm_bonferroni(p_values.values())
    return {name: adjusted[index] for index, name in enumerate(names)}


def sample_size_for_precision(
    standard_deviation: float,
    *,
    half_width: float = 0.03,
    confidence: float = 0.95,
) -> int:
    """Plan the approximate iid sample size for a mean CI half-width."""
    if not math.isfinite(standard_deviation) or standard_deviation < 0:
        raise ValueError("standard_deviation must be finite and non-negative")
    if not math.isfinite(half_width) or half_width <= 0:
        raise ValueError("half_width must be finite and positive")
    return max(1, math.ceil((_z_value(confidence) * standard_deviation / half_width) ** 2))


def sample_size_for_cluster_precision(
    standard_deviation: float,
    *,
    half_width: float = 0.03,
    confidence: float = 0.95,
    design_effect: float = 1.0,
) -> int:
    """Plan observations with an explicit cluster design effect."""
    if not math.isfinite(design_effect) or design_effect < 1:
        raise ValueError("design_effect must be finite and at least one")
    return math.ceil(sample_size_for_precision(standard_deviation, half_width=half_width, confidence=confidence) * design_effect)


def write_accounting_artifacts(
    result: dict,
    report_path: str | Path,
    log_path: str | Path,
) -> tuple[Path, Path]:
    """Write deterministic accounting JSON and JSONL event records."""
    report = Path(report_path)
    log = Path(log_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    accounting = result.get("accounting", {})
    temporary_report = report.with_name(f".{report.name}.tmp")
    temporary_report.write_text(json.dumps(accounting, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_report.replace(report)
    # v2 callers provide a deterministic event stream.  Keep the v1 fallback so
    # older report fixtures remain readable and migration is non-breaking.
    records = result.get("events")
    if records is None:
        records = [{"event": "sample_evaluation", **row} for row in accounting.get("runs", [])]
    temporary_log = log.with_name(f".{log.name}.tmp")
    temporary_log.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")
    temporary_log.replace(log)
    return report, log


__all__ = [
    "StatisticalEstimate",
    "PairedComparison",
    "BinaryRateEstimate",
    "PairedBinaryComparison",
    "bootstrap_mean",
    "stratified_bootstrap_mean",
    "clustered_bootstrap_mean",
    "wilson_interval",
    "binary_rate",
    "exact_paired_binary",
    "paired_bootstrap_delta",
    "paired_permutation_p_value",
    "paired_comparison",
    "clustered_paired_comparison",
    "holm_bonferroni",
    "holm_named",
    "sample_size_for_precision",
    "sample_size_for_cluster_precision",
    "write_accounting_artifacts",
]
