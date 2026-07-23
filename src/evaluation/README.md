# `src/evaluation/` — THALIA evaluation package

Offline, deterministic evaluation of the harness plus explicitly gated live
benchmark/campaign tooling: dataset construction, accounting, statistics,
retriever/method experiments, compiler generalization, and JSON result bundles.
Barrel package — import from the package root:
`from src.evaluation import run_full_eval, build_demo_dataset, …`.

## Modules

| Module | Purpose |
|--------|---------|
| [`dataset.py`](dataset.py) | `build_demo_dataset`, `with_noise` — synthetic eval corpus |
| [`budget.py`](budget.py) | `TIGHT_TOP_K`, `tight_eval_config`, `metric_sweep`, lane presets |
| [`experiments.py`](experiments.py) | `retriever_comparison`, sweeps, ablation, `consolidation_simulation` |
| [`bundle.py`](bundle.py) | `run_full_eval` — JSON bundle consumed by `scripts/` |
| [`accounting.py`](accounting.py) | Stable fingerprints, per-row ledgers, event streams, and failure accounting |
| [`statistics.py`](statistics.py) | Stratified/cluster bootstrap, Wilson intervals, paired tests, Holm correction, and planning |
| [`scaling.py`](scaling.py) | Seeded research audit, paired comparisons, and complete accounting |
| [`longmemeval.py`](longmemeval.py) | Validated LongMemEval loader, resumable neural evaluation, and bottleneck analysis |
| [`campaign.py`](campaign.py) | Nested cohort selection, atomic checkpoints, typed reports, and safe promotion |
| [`generalization.py`](generalization.py) | Pre-registered finite seed-sensitivity report |
| [`compiler_generalization.py`](compiler_generalization.py) | Train/held-out validation for the in-house compiler analogues |

Sweeps default to the tight budget (`top_k=2`, `max_evidence=2`) unless
`method_ablation(tight_budget=False)`.

## See Also

- [`AGENTS.md`](AGENTS.md) — agent contract for this package
- [`../README.md`](../README.md) — `src/` implementation overview
- [`../../docs/README.md`](../../docs/README.md) — project docs
