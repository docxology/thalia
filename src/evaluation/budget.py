"""Shared tight-budget helpers for decisive retrieval experiments."""

from __future__ import annotations

from collections.abc import Callable

from ..compiler.metrics import EvalExample, evaluate
from ..config import HarnessConfig, default_config
from ..harness import build_run_fn

TIGHT_TOP_K = 2
TIGHT_MAX_EVIDENCE = 2


def tight_eval_config(base: HarnessConfig | None = None) -> HarnessConfig:
    """Tight retrieval budget where lane/method choice is decisive."""
    parent = base or default_config()
    return parent.with_(top_k=TIGHT_TOP_K, max_evidence=TIGHT_MAX_EVIDENCE)


def metric_sweep(
    dataset: list[EvalExample],
    base: HarnessConfig,
    steps: int,
    build_config: Callable[[HarnessConfig, int, int], HarnessConfig],
    label: Callable[[int, int], float],
) -> list[tuple[float, float]]:
    """Run ``evaluate`` over evenly spaced config variants."""
    if steps < 2:
        raise ValueError(f"steps must be >= 2, got {steps}")
    results: list[tuple[float, float]] = []
    for i in range(steps):
        key = label(i, steps)
        cfg = build_config(base, i, steps)
        results.append((key, evaluate(build_run_fn(cfg), dataset).composite))
    return results


def lexical_only(base: HarnessConfig) -> HarnessConfig:
    return base.with_(lexical_weight=1.0, semantic_weight=0.0)


def semantic_only(base: HarnessConfig) -> HarnessConfig:
    return base.with_(lexical_weight=0.0, semantic_weight=1.0)


__all__ = [
    "TIGHT_TOP_K",
    "TIGHT_MAX_EVIDENCE",
    "tight_eval_config",
    "metric_sweep",
    "lexical_only",
    "semantic_only",
]
