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
| [`backend_benchmark.py`](backend_benchmark.py) | Shared offline workload planning and schema-2 sequential backend × method × seeded-cohort execution, portable provenance, recomputing validator and atomic failure-preserving output |
| [`benchmark_analysis.py`](benchmark_analysis.py) | Success-only summaries, prompt exposure/vector groups, per-seed paired audit rows, complete seed-mean contrasts and descriptive cluster intervals without p-values |
| [`integrity_advantage.py`](integrity_advantage.py) | Native-unit endpoint screen for provenance, poisoning, retrieval, context, compiler, and neural comparisons with source/code hashes |
| [`provenance_p0.py`](provenance_p0.py) | Isolated P0 source-record protocol, immutable atomic condition rows, sealed blinded-packet/key evidence, expert adjudication, source-condition tables, strata-aware paired analysis, and explicit promotion; it never upgrades the legacy lexical proxy |
| [`scaling.py`](scaling.py) | Configurable seeded sample-size research audit, paired method comparisons, complete accounting; quick defaults and enlarged publication grids are recorded separately |
| [`longmemeval.py`](longmemeval.py) | Full-record benchmark validation, resumable neural evaluation, bottleneck analysis |
| [`quality.py`](quality.py) | Separate typed quality protocol, blinded expert-rater annotations/adjudication, Brier/ECE plus reliability/selective calibration, pilot summaries, reports, and fail-closed promotion; local LLM judging is non-promotable |
| [`quality_runner.py`](quality_runner.py) | External-volume raw-answer/evidence runner, six-condition matrix, blinded packets, and confidence probe |
| [`production_readiness.py`](production_readiness.py) | Independent operational acceptance schema and metrics for service-level readiness |

Sweeps default to the tight budget (`top_k=2`, `max_evidence=2`) unless `method_ablation(tight_budget=False)`.

Common backend API: `BenchmarkBackend(name, provider, model, lm,
generation_options={}, model_observation={})`;
`build_benchmark_backends(*, ollama_models=(), openrouter_models=(), timeout=30.0,
max_tokens=1024, allow_cloud=False, observe_models=False, num_ctx=None)` includes
extractive; positive `num_ctx` applies only to Ollama requests and metadata.
`BenchmarkMethod(name, kind, config)` is frozen: `kind="harness"` requires a
validated `HarnessConfig` with verification disabled; `kind="full_context"`
requires `config=None`. `build_benchmark_methods(names=("harness",), *,
config=None)` selects unique `harness`, `full_context`, `lexical_only`, `adaptive`;
custom named harness configs use `BenchmarkMethod` directly.
`run_backend_benchmark(backends, *, methods=None, per_category=10, seeds=(0,),
limit=None, allow_cloud=False, reference_method="full_context", n_boot=2000,
analysis_seed=0)` executes one completion attempt per cell, backend-outer with
methods rotated by example index and fresh harness resources per cell.
`build_benchmark_plan` takes the same selection/cohort/analysis arguments and
returns planned identities, exact schedule and counts without observations or
client calls. CLI `--plan` disables model probes and writes JSON only to stdout.
Schema 2 separates backend identities, method configs/fingerprints, observations,
summaries, category/stratum groups, and paired comparisons. Reference absent means
no comparisons; any incomplete pair suppresses the entire contrast estimate;
one represented seed has no interval. Multiple seeds use unweighted seed means
and descriptive cluster resampling, retaining small-cluster warnings. No p-values.
`validate_backend_benchmark(payload)` rebuilds the seeded plan, matrix/schedule,
scores, summaries/groups and paired analyses; schema 1 is rejected. It checks
recorded prompt hash syntax/count, positive/null character counts and agreement
within each backend-matched example/method. It never renders prompts or calls
any completion client: these checks establish consistency, not independently
authenticated inference or prompt length, and do not bind readers to current
prompt implementation bytes.
`summarize_prompt_exposure(rows, *, methods, example_ids, reference_method)` is
exported from `benchmark_analysis` only. Pass validated rows and ordered method/
example-ID sequences. It collapses backends by method/example, retaining captured
hashes even on failed attempts and ignoring empty failures. Requested/observed
case counts, distinct prompt counts, paired fingerprint differences and complete
vector groups describe recorded attempted text only. Missing prompts or an empty
plan never establish equivalence; an absent reference yields zero pairs and a
null difference count. Groups follow first complete-vector occurrence, not
unordered hash sets. Unique example IDs need not mean unique inputs, and repeated
inputs are not independent new content. These diagnostics do not authenticate
inference traffic or establish provider retention, equal code/compute/latency,
or independent method-quality evidence; they do not modify schema-2 reports.
`summarize_seed_pairs(rows, *, backends, methods, examples, reference_method)`
is another post-validation reader exported by `benchmark_analysis`, not the barrel. It
includes all represented seeds with requested/complete pair counts and raw
wins/ties/losses, in backend/method/sorted-seed order. Any failed pair suppresses
that seed's mean; no reference means no rows. These views neither add observations
nor rescue an incomplete whole contrast.
Producer inventory conservatively includes every Python file under the installed
`src` package, not repository/venv files or an executed-file trace. Recorded
portable paths and source checksums are checked structurally, not for equality
to the reader's checkout or authenticity. Dependency
versions are observed, with null for unavailable distributions.
`write_backend_benchmark(payload, path)` atomically writes complete reports or
returns an `.incomplete.json` sidecar, preserving last-good destination bytes.
Prompt characters are not billed tokens; latency is not throughput/cost. No live
observations or intervals are promoted as deterministic, expert-quality or
production results. See [`../../docs/backend_benchmark.md`](../../docs/backend_benchmark.md).
