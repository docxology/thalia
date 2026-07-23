"""Deterministic harness experiments (retrieval, ablation, noise, schematic)."""

from __future__ import annotations

from dataclasses import dataclass

from ..compiler.gepa import GEPAOptimizer
from ..compiler.metrics import EvalExample, answer_score, evaluate, grounding_score, efficiency_score
from ..config import HarnessConfig, default_config
from ..harness import AutoHarness, build_run_fn
from ..signatures import TaskCategory
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
        with AutoHarness(config=config) as harness:
            out = harness.run(ex)
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


def pipeline_evidence_flow(
    dataset: list[EvalExample] | None = None,
    config: HarnessConfig | None = None,
) -> list[dict]:
    """Per-example evidence counts at each Pipeline stage.

    Runs every demo example through a full :class:`~src.pipeline.Pipeline`
    (with_all_stages) and records how many items survive each of the three
    narrowing stages:

    * **n_windows** — evidence windows emitted by the Inspector.
    * **n_ranked** — ranked evidence from the Retriever.
    * **n_cited** — citations from the Reasoner.

    Returns:
        A list of dicts, one per example, with keys:
        ``query``, ``task_category``, ``n_windows``, ``n_ranked``, ``n_cited``.
    """
    from ..pipeline import Pipeline

    dataset = dataset or build_demo_dataset()
    config = config or default_config()
    rows: list[dict] = []
    for ex in dataset:
        with Pipeline(config=config).with_all_stages() as pipe:
            pipe.run(query=ex.query, session_history=ex.session_history)
            intermediates = {name: ctx for name, ctx in pipe.intermediates}
        inspector_ctx = intermediates.get("inspector")
        retriever_ctx = intermediates.get("retriever")
        reasoner_ctx = intermediates.get("reasoner")
        rows.append(
            {
                "query": ex.query,
                "task_category": (ex.task_category or TaskCategory.SINGLE_SESSION).value,
                "n_windows": len(inspector_ctx.evidence_windows) if inspector_ctx is not None else 0,
                "n_ranked": len(retriever_ctx.ranked_evidence) if retriever_ctx is not None else 0,
                "n_cited": len(reasoner_ctx.evidence_citations) if reasoner_ctx is not None else 0,
            }
        )
    return rows


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


def category_component_breakdown(
    dataset: list[EvalExample] | None = None,
    config: HarnessConfig | None = None,
) -> dict[str, dict[str, float]]:
    """Per-category accuracy, grounding, and efficiency using the default config.

    Runs the default pipeline over the demo dataset (or a supplied dataset) and
    returns a mapping from each :class:`~src.signatures.TaskCategory` name to a
    dict with keys ``"accuracy"``, ``"grounding"``, and ``"efficiency"`` (each
    a float in 0..1), averaged over examples in that category.

    Returns:
        Dict mapping ``TaskCategory.value`` (e.g. ``"temporal"``) to a dict
        ``{"accuracy": float, "grounding": float, "efficiency": float}``.
    """
    dataset = dataset or build_demo_dataset()
    config = config or default_config()
    run_fn = build_run_fn(config)

    # Accumulate per-category component sums and counts
    acc_sum: dict[str, float] = {}
    grd_sum: dict[str, float] = {}
    eff_sum: dict[str, float] = {}
    counts: dict[str, int] = {}

    for example in dataset:
        cat = example.task_category.value if example.task_category is not None else "unknown"
        output = run_fn(example)
        a = answer_score(output, example)
        g = grounding_score(output, example)
        e = efficiency_score(output)
        acc_sum[cat] = acc_sum.get(cat, 0.0) + a
        grd_sum[cat] = grd_sum.get(cat, 0.0) + g
        eff_sum[cat] = eff_sum.get(cat, 0.0) + e
        counts[cat] = counts.get(cat, 0) + 1

    return {
        cat: {
            "accuracy": acc_sum[cat] / counts[cat],
            "grounding": grd_sum[cat] / counts[cat],
            "efficiency": eff_sum[cat] / counts[cat],
        }
        for cat in counts
    }


def gepa_component_trajectory(
    dataset: list[EvalExample] | None = None,
    seed_config: HarnessConfig | None = None,
    iterations: int = 8,
) -> list[dict]:
    """Run GEPA evolution and record per-component scores at each iteration.

    Runs :class:`~src.compiler.gepa.GEPAOptimizer` over the demo dataset and,
    at each iteration, evaluates the candidate config to obtain accuracy,
    grounding, and efficiency component scores (not just the composite).

    Args:
        dataset: Evaluation examples (defaults to :func:`build_demo_dataset`).
        seed_config: Starting config (defaults to :func:`default_config`).
        iterations: Number of reflective mutation rounds (default 8).

    Returns:
        A list of dicts — one per iteration (including iteration 0 for the seed
        config) — with keys:

        * ``iteration`` — 0-based index;
        * ``composite`` — mean composite metric;
        * ``accuracy`` — mean accuracy component;
        * ``grounding`` — mean grounding component;
        * ``efficiency`` — mean efficiency component;
        * ``weakest_component`` — the component with the lowest score at that
          step (matching :meth:`GEPAOptimizer.reflect` logic).
    """
    dataset = dataset or build_demo_dataset()
    current = seed_config or default_config()
    optimizer = GEPAOptimizer()

    # Evaluate seed config (iteration 0)
    current_report = evaluate(build_run_fn(current), dataset)
    records: list[dict] = []

    def _record(iteration: int, report) -> dict:
        weakest = min(
            ("accuracy", report.accuracy),
            ("grounding", report.grounding),
            ("efficiency", report.efficiency),
            key=lambda pair: pair[1],
        )[0]
        return {
            "iteration": iteration,
            "composite": report.composite,
            "accuracy": report.accuracy,
            "grounding": report.grounding,
            "efficiency": report.efficiency,
            "weakest_component": weakest,
        }

    records.append(_record(0, current_report))

    for i in range(iterations):
        candidate = optimizer.reflect(current, current_report)
        candidate_report = evaluate(build_run_fn(candidate), dataset)
        records.append(_record(i + 1, candidate_report))
        current, current_report = candidate, candidate_report

    return records


__all__ = [
    "RetrieverComparison",
    "retriever_comparison",
    "rrf_weight_sweep",
    "noise_scaling_experiment",
    "evidence_funnel",
    "pipeline_evidence_flow",
    "mmr_lambda_sweep",
    "method_ablation",
    "consolidation_simulation",
    "category_component_breakdown",
    "gepa_component_trajectory",
]
