# `src/evaluation/` — Agent contract

Barrel package: `from src.evaluation import run_full_eval, build_demo_dataset, …`

| Module | Contents |
|--------|----------|
| [`dataset.py`](dataset.py) | `build_demo_dataset`, seeded large/research datasets, stable IDs, `with_noise` |
| [`budget.py`](budget.py) | `TIGHT_TOP_K`, `tight_eval_config`, `metric_sweep`, lane presets |
| [`experiments.py`](experiments.py) | `retriever_comparison`, sweeps, ablation, `consolidation_simulation` |
| [`bundle.py`](bundle.py) | `run_full_eval` — JSON bundle for scripts |
| [`accounting.py`](accounting.py) | Stable fingerprints, per-example/method ledger, deterministic JSONL events, runtime provenance |
| [`statistics.py`](statistics.py) | IID/stratified/cluster bootstrap, Wilson/exact paired tests, Holm correction, clustered effect sizes, sample planning |
| [`scaling.py`](scaling.py) | Four-size/five-seed research audit, paired method comparisons, complete accounting |
| [`longmemeval.py`](longmemeval.py) | Full-record benchmark validation, resumable neural evaluation, bottleneck analysis |

Sweeps default to the tight budget (`top_k=2`, `max_evidence=2`) unless `method_ablation(tight_budget=False)`.
