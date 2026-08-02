"""Held-out validation for the in-house MIPRO-/GEPA-style compilers."""

from __future__ import annotations

import hashlib
from typing import Any

from ..compiler.gepa import GEPAOptimizer
from ..compiler.metrics import EvalExample, evaluate
from ..compiler.mipro import MIPROCompiler
from ..config import default_config
from ..harness import build_run_fn
from .accounting import fingerprint_config, fingerprint_examples, fingerprint_files
from .dataset import build_research_dataset

DEFAULT_COMPILER_GENERALIZATION_SEEDS = (0, 1, 2, 3, 4)


def _split_dataset(examples: list[EvalExample], holdout_fraction: float) -> tuple[list[EvalExample], list[EvalExample]]:
    if not examples:
        raise ValueError("examples must be non-empty")
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must be in (0, 1)")
    by_stratum: dict[str, list[EvalExample]] = {}
    for example in examples:
        by_stratum.setdefault(example.stratum, []).append(example)
    train: list[EvalExample] = []
    holdout: list[EvalExample] = []
    for stratum, rows in sorted(by_stratum.items()):
        ordered = sorted(
            rows,
            key=lambda row: (
                hashlib.sha256(f"compiler-holdout\0{row.example_id}".encode("utf-8")).hexdigest(),
                row.example_id,
            ),
        )
        n_holdout = max(1, min(len(ordered) - 1, round(len(ordered) * holdout_fraction))) if len(ordered) > 1 else 0
        holdout.extend(ordered[:n_holdout])
        train.extend(ordered[n_holdout:])
    if not train or not holdout:
        raise ValueError("split must produce non-empty train and holdout sets")
    return train, holdout


def compiler_generalization_eval(
    *,
    per_category: int = 4,
    seeds: tuple[int, ...] = DEFAULT_COMPILER_GENERALIZATION_SEEDS,
    holdout_fraction: float = 0.25,
    gepa_iterations: int = 4,
) -> dict[str, Any]:
    """Compile on one stable split and evaluate every winner on held-out data."""
    if isinstance(per_category, bool) or not isinstance(per_category, int) or per_category < 2:
        raise ValueError("per_category must be an integer >= 2")
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be non-empty and unique")
    if isinstance(gepa_iterations, bool) or not isinstance(gepa_iterations, int) or gepa_iterations < 0:
        raise ValueError("gepa_iterations must be a non-negative integer")
    rows: list[dict[str, Any]] = []
    baseline_train_requested = 0
    baseline_train_evaluated = 0
    final_holdout_requested = 0
    final_holdout_evaluated = 0
    candidate_requested = 0
    candidate_evaluated = 0
    for seed in seeds:
        dataset = build_research_dataset(per_category=per_category, seed=seed)
        train, holdout = _split_dataset(dataset, holdout_fraction)
        baseline_train = evaluate(build_run_fn(default_config()), train)
        baseline_holdout = evaluate(build_run_fn(default_config()), holdout)
        mipro = MIPROCompiler(auto="heavy").compile(lambda config: build_run_fn(config), train)
        gepa = GEPAOptimizer().evolve(
            lambda config: build_run_fn(config),
            train,
            iterations=gepa_iterations,
        )
        mipro_holdout = evaluate(build_run_fn(mipro.best_config), holdout)
        gepa_holdout = evaluate(build_run_fn(gepa.best_config), holdout)
        # The final holdout scores are only part of the executed work: the
        # baseline is evaluated once on training data and each compiler also
        # evaluates every candidate on the training split.
        baseline_train_requested += len(train)
        baseline_train_evaluated += len(train)
        final_holdout_requested += len(holdout) * 3
        final_holdout_evaluated += len(holdout) * 3
        candidate_rows = (mipro.n_candidates + gepa.n_candidates) * len(train)
        candidate_requested += candidate_rows
        candidate_evaluated += candidate_rows
        rows.append(
            {
                "seed": seed,
                "n_total": len(dataset),
                "n_train": len(train),
                "n_holdout": len(holdout),
                "train_fingerprint": fingerprint_examples(train),
                "holdout_fingerprint": fingerprint_examples(holdout),
                "baseline": {
                    "train_composite": baseline_train.composite,
                    "holdout_composite": baseline_holdout.composite,
                },
                "mipro": {
                    "n_candidates": mipro.n_candidates,
                    "config_fingerprint": fingerprint_config(mipro.best_config),
                    "train_composite": mipro.best_score,
                    "holdout_composite": mipro_holdout.composite,
                    "holdout_delta": mipro_holdout.composite - baseline_holdout.composite,
                },
                "gepa": {
                    "n_candidates": gepa.n_candidates,
                    "config_fingerprint": fingerprint_config(gepa.best_config),
                    "train_composite": gepa.best_score,
                    "holdout_composite": gepa_holdout.composite,
                    "holdout_delta": gepa_holdout.composite - baseline_holdout.composite,
                },
            }
        )
    return {
        "schema_version": 1,
        "experiment": "compiler_held_out_generalization_v2",
        "evidence_tier": "finite_synthetic",
        "per_category": per_category,
        "seed_values": list(seeds),
        "n_seeds": len(seeds),
        "holdout_fraction": holdout_fraction,
        "gepa_iterations": gepa_iterations,
        "source_fingerprint": fingerprint_files([__file__]),
        "rows": rows,
        "summary": {
            method: {
                "mean_train_composite": sum(float(row[method]["train_composite"]) for row in rows) / len(rows),
                "mean_holdout_composite": sum(float(row[method]["holdout_composite"]) for row in rows) / len(rows),
                "mean_holdout_delta": (
                    sum(float(row[method].get("holdout_delta", 0.0)) for row in rows) / len(rows)
                ),
                "n_seeds": len(rows),
            }
            for method in ("baseline", "mipro", "gepa")
        },
        "sample_accounting": {
            "unit": "synthetic_example_compiler_evaluation",
            "n_requested": baseline_train_requested + final_holdout_requested + candidate_requested,
            "n_evaluated": baseline_train_evaluated + final_holdout_evaluated + candidate_evaluated,
            "n_failed": 0,
            "status": "complete",
            "components": {
                "baseline_train_evaluations": {
                    "n_requested": baseline_train_requested,
                    "n_evaluated": baseline_train_evaluated,
                },
                "final_holdout_method_evaluations": {
                    "n_requested": final_holdout_requested,
                    "n_evaluated": final_holdout_evaluated,
                },
                "compiler_candidate_train_evaluations": {
                    "n_requested": candidate_requested,
                    "n_evaluated": candidate_evaluated,
                },
            },
            "interpretation": "held-out finite generated-task validation; no population inference",
        },
    }


__all__ = ["DEFAULT_COMPILER_GENERALIZATION_SEEDS", "compiler_generalization_eval"]
