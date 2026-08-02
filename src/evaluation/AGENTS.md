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
| [`integrity_advantage.py`](integrity_advantage.py) | Native-unit endpoint screen for provenance, poisoning, retrieval, context, compiler, and neural comparisons with source/code hashes |
| [`provenance_p0.py`](provenance_p0.py) | Isolated P0 source-record protocol, immutable atomic condition rows, sealed blinded-packet/key evidence, expert adjudication, source-condition tables, strata-aware paired analysis, and explicit promotion; it never upgrades the legacy lexical proxy |
| [`scaling.py`](scaling.py) | Configurable seeded sample-size research audit, paired method comparisons, complete accounting; quick defaults and enlarged publication grids are recorded separately |
| [`longmemeval.py`](longmemeval.py) | Full-record benchmark validation, resumable neural evaluation, bottleneck analysis |
| [`quality.py`](quality.py) | Separate typed quality protocol, blinded expert-rater annotations/adjudication, Brier/ECE plus reliability/selective calibration, pilot summaries, reports, and fail-closed promotion; local LLM judging is non-promotable |
| [`quality_runner.py`](quality_runner.py) | External-volume raw-answer/evidence runner, six-condition matrix, blinded packets, and confidence probe |
| [`production_readiness.py`](production_readiness.py) | Independent operational acceptance schema and metrics for service-level readiness |

Sweeps default to the tight budget (`top_k=2`, `max_evidence=2`) unless `method_ablation(tight_budget=False)`.
