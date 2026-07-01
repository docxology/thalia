# `src/evaluation/` — THALIA evaluation package

Offline, deterministic evaluation of the harness: demo-dataset construction,
budget presets, retriever/method experiments, and a JSON result bundle for the
analysis scripts. Barrel package — import from the package root:
`from src.evaluation import run_full_eval, build_demo_dataset, …`.

## Modules

| Module | Purpose |
|--------|---------|
| [`dataset.py`](dataset.py) | `build_demo_dataset`, `with_noise` — synthetic eval corpus |
| [`budget.py`](budget.py) | `TIGHT_TOP_K`, `tight_eval_config`, `metric_sweep`, lane presets |
| [`experiments.py`](experiments.py) | `retriever_comparison`, sweeps, ablation, `consolidation_simulation` |
| [`bundle.py`](bundle.py) | `run_full_eval` — JSON bundle consumed by `scripts/` |

Sweeps default to the tight budget (`top_k=2`, `max_evidence=2`) unless
`method_ablation(tight_budget=False)`.

## See Also

- [`AGENTS.md`](AGENTS.md) — agent contract for this package
- [`../README.md`](../README.md) — `src/` implementation overview
- [`../../docs/README.md`](../../docs/README.md) — project docs
