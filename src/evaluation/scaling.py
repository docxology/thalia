"""Scaling and variance evaluation on the seeded large dataset.

The 6-example demo set is a determinism showcase but supports no statistics. This
module runs the harness over the seeded :func:`build_large_dataset` (balanced, ~60
examples, bit-reproducible) and reports per-category accuracy with **bootstrap
confidence intervals** — real variance, still deterministic. The data is
realistic-but-synthetic, so this measures the machinery's scaling and dispersion,
not real-world accuracy.
"""

from __future__ import annotations

import random

from ..compiler.metrics import answer_score, harness_metric
from ..config import default_config
from ..harness import build_run_fn
from .dataset import build_large_dataset


def bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float, float]:
    """Return (mean, lo, hi) with a percentile bootstrap CI. Deterministic via seed.

    A single observation has no spread to resample, so its bootstrap interval is
    degenerate (zero width); we return the point for all three rather than implying
    precision. Callers report CIs only for samples well above this (n>=10 here), so
    the degenerate branch never fires in practice — it just refuses to fake a CI.
    """
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    point = sum(values) / n
    if n < 2:
        return point, point, point
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return sum(values) / n, lo, hi


def large_dataset_eval(per_category: int = 10, seed: int = 0, n_boot: int = 2000) -> dict:
    """Per-category accuracy and overall composite with bootstrap CIs on the large set."""
    dataset = build_large_dataset(per_category=per_category, seed=seed)
    run = build_run_fn(default_config())
    by_category: dict[str, list[float]] = {}
    composites: list[float] = []
    for example in dataset:
        out = run(example)
        by_category.setdefault(example.task_category.name.lower(), []).append(answer_score(out, example))
        composites.append(harness_metric(out, example))

    category_acc = {cat: bootstrap_ci(vals, n_boot=n_boot, seed=seed) for cat, vals in by_category.items()}
    comp_mean, comp_lo, comp_hi = bootstrap_ci(composites, n_boot=n_boot, seed=seed)
    return {
        "n": len(dataset),
        "per_category": per_category,
        "composite_mean": comp_mean,
        "composite_lo": comp_lo,
        "composite_hi": comp_hi,
        "category_accuracy": category_acc,  # name -> (mean, lo, hi)
    }


__all__ = ["bootstrap_ci", "large_dataset_eval"]
