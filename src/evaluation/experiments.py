"""Deterministic harness experiments (retrieval, ablation, noise, schematic)."""

from __future__ import annotations

from dataclasses import dataclass

from ..compiler.metrics import EvalExample, evaluate
from ..config import HarnessConfig, default_config
from ..harness import AutoHarness, build_run_fn
from ..stages.inspector import Inspector
from .budget import lexical_only, metric_sweep, semantic_only, tight_eval_config
from .dataset import build_demo_dataset, with_noise


@dataclass(frozen=True)
class RetrieverComparison:
    """Composite metric per retrieval mode."""

    lexical: float
    semantic: float
    hybrid: float

    def best_mode(self) -> str:
        """Return the name of the highest-scoring mode (ties -> lexical)."""
        modes = {"lexical": self.lexical, "hybrid": self.hybrid, "semantic": self.semantic}
        return max(modes, key=lambda m: (modes[m], m == "lexical"))


def retriever_comparison(
    dataset: list[EvalExample] | None = None,
    base: HarnessConfig | None = None,
) -> RetrieverComparison:
    """Compare lexical-only, semantic-only, and hybrid retrieval composites."""
    dataset = dataset or build_demo_dataset()
    base = base or default_config()
    lexical = evaluate(build_run_fn(lexical_only(base)), dataset).composite
    semantic = evaluate(build_run_fn(semantic_only(base)), dataset).composite
    hybrid = evaluate(build_run_fn(base), dataset).composite
    return RetrieverComparison(lexical=lexical, semantic=semantic, hybrid=hybrid)


def rrf_weight_sweep(
    dataset: list[EvalExample] | None = None,
    steps: int = 11,
    base: HarnessConfig | None = None,
) -> list[tuple[float, float]]:
    """Sweep lexical lane weight from 0 to 1; return (weight, composite) pairs."""
    dataset = dataset or build_demo_dataset()
    base = tight_eval_config(base)
    return metric_sweep(
        dataset,
        base,
        steps,
        build_config=lambda cfg, i, n: cfg.with_(
            lexical_weight=i / (n - 1),
            semantic_weight=1.0 - i / (n - 1),
        ),
        label=lambda i, n: round(i / (n - 1), 4),
    )


def noise_scaling_experiment(
    dataset: list[EvalExample] | None = None,
    levels: tuple[int, ...] = (0, 4, 8, 16, 32),
    base: HarnessConfig | None = None,
) -> dict[str, list[tuple[int, float]]]:
    """Measure each retrieval mode's composite as session noise scales."""
    if not levels or any(level < 0 for level in levels):
        raise ValueError("levels must be a non-empty tuple of non-negative ints")
    dataset = dataset or build_demo_dataset()
    base = tight_eval_config(base)
    configs = {
        "lexical": lexical_only(base),
        "semantic": semantic_only(base),
        "hybrid": base,
    }
    out: dict[str, list[tuple[int, float]]] = {mode: [] for mode in configs}
    for level in levels:
        noisy = [with_noise(ex, level) for ex in dataset]
        for mode, cfg in configs.items():
            out[mode].append((level, evaluate(build_run_fn(cfg), noisy).composite))
    return out


def evidence_funnel(
    dataset: list[EvalExample] | None = None,
    config: HarnessConfig | None = None,
) -> dict[str, float]:
    """Average per-stage evidence counts across the dataset."""
    dataset = dataset or build_demo_dataset()
    config = config or default_config()
    inspector = Inspector(
        max_windows=config.max_windows,
        partition_threshold=config.partition_threshold,
        partition_size=config.partition_size,
    )
    lines = windows = ranked = cited = 0.0
    for ex in dataset:
        n_lines = len([ln for ln in ex.session_history.splitlines() if ln.strip()])
        n_windows = len(inspector(session_history=ex.session_history, query=ex.query)["evidence_windows"])
        out = AutoHarness(config=config).run(ex)
        lines += n_lines
        windows += n_windows
        ranked += len(out.ranked_evidence)
        cited += len(out.evidence_citations)
    n = len(dataset)
    return {
        "session_lines": lines / n,
        "windows": windows / n,
        "ranked": ranked / n,
        "cited": cited / n,
    }


def mmr_lambda_sweep(
    dataset: list[EvalExample] | None = None,
    steps: int = 11,
    base: HarnessConfig | None = None,
) -> list[tuple[float, float]]:
    """Sweep MMR lambda; return (lambda, composite) pairs."""
    dataset = dataset or build_demo_dataset()
    base = tight_eval_config(base)
    return metric_sweep(
        dataset,
        base,
        steps,
        build_config=lambda cfg, i, n: cfg.with_(rerank="mmr", mmr_lambda=round(i / (n - 1), 4)),
        label=lambda i, n: round(i / (n - 1), 4),
    )


def method_ablation(
    dataset: list[EvalExample] | None = None,
    base: HarnessConfig | None = None,
    *,
    tight_budget: bool = True,
) -> dict[str, float]:
    """Composite metric for base pipeline and each added method."""
    dataset = dataset or build_demo_dataset()
    base = tight_eval_config(base) if tight_budget else (base or default_config())
    configs: dict[str, HarnessConfig] = {
        "base": base,
        "+expansion": base.with_(query_expansion=True),
        "+recency": base.with_(recency_weight=0.5),
        "+mmr": base.with_(rerank="mmr"),
        "all": base.with_(query_expansion=True, recency_weight=0.5, rerank="mmr"),
    }
    return {name: evaluate(build_run_fn(cfg), dataset).composite for name, cfg in configs.items()}


def consolidation_simulation(turns: int = 12) -> dict[str, list[float]]:
    """Schematic utility curves: forced consolidation vs. episodic-first."""
    if turns < 1:
        raise ValueError(f"turns must be >= 1, got {turns}")
    forced: list[float] = []
    episodic: list[float] = []
    peak = max(1, turns // 3)
    for t in range(turns):
        if t <= peak:
            forced.append(round(0.5 + 0.4 * (t / peak), 4))
        else:
            decay = (t - peak) / max(1, turns - peak)
            forced.append(round(0.9 - 0.6 * decay, 4))
        episodic.append(round(0.5 + 0.35 * (t / (turns - 1) if turns > 1 else 1.0), 4))
    return {"forced": forced, "episodic_first": episodic}


__all__ = [
    "RetrieverComparison",
    "retriever_comparison",
    "rrf_weight_sweep",
    "noise_scaling_experiment",
    "evidence_funnel",
    "mmr_lambda_sweep",
    "method_ablation",
    "consolidation_simulation",
]
