# `scripts/` — Agent contract

## Thin orchestrator rules

1. **No business logic.** Import from `src/`; handle only I/O, path setup, and
   serialisation. If you are tempted to compute something here, it belongs in `src/`.
2. **Path setup.** Each script defines
   `PROJECT_ROOT = Path(__file__).resolve().parent.parent` and inserts
   `PROJECT_ROOT`, `PROJECT_ROOT/src`, and the repo root onto `sys.path` before
   importing `src.*`.
3. **Print output paths.** Every produced artifact path is printed to stdout for
   manifest collection.
4. **Determinism.** Scripts must produce byte-identical artifacts on repeated runs
   (JSON serialised with `sort_keys=True`).
5. **Fail loudly.** `z_generate_manuscript_variables.py` raises `SystemExit` if the
   manuscript uses a token the generator does not emit — never silence it.
6. **Validate after generation.** Run `validate_artifacts.py` after the final
   generator; it refuses missing, mutated, or unsafe manifest entries.

## Outputs (all under `output/`, gitignored / regeneratable)

- `data/eval_results.json`, `data/compile_result.json`, `data/seed_sensitivity.json`,
  `data/compiler_generalization.json`, `data/manuscript_variables.json`
- `data/demo_result.json`, `reports/verification_summary.json`,
  `figures/figure_registry.json`, `reports/artifact_manifest.json`,
  `reports/evaluation_accounting.json`, `reports/evaluation_events.jsonl`,
  `reports/evaluation_ledger.jsonl`
- `figures/retriever_comparison.png`, `figures/rrf_sensitivity.png`,
  `figures/compiler_convergence.png`, `figures/consolidation_curve.png`,
  `figures/category_breakdown.png`, `figures/evidence_funnel.png`,
  `figures/noise_scaling.png`, `figures/mmr_tradeoff.png`,
  `figures/method_ablation.png`
- `dashboard.html`

The live v2 campaign scripts write raw rows and atomic checkpoints only to the
external `/Volumes/blue/data/thalia_campaigns` root. They never promote an
incomplete report into the repository's `data/` layer; promotion requires
complete accounting plus benchmark, model, generation, cohort, code, and config
provenance.

The model-quality scripts use a separate external root,
`/Volumes/blue/data/thalia_quality`. `run_quality_campaign.py` writes raw answer
and evidence packets, observations, blinded annotation templates, and runtime
metadata; `analyze_quality.py` writes an external report; and only
`promote_quality_report.py` may create `data/quality_results.json`. Confirmation
requires a frozen protocol with pilot-review provenance. A complete or
below-threshold quality run is never promoted implicitly, and no production
readiness claim may be inferred from its certificate.

`analyze_production_readiness.py` consumes service observations and explicit
control evidence for latency, cost/throughput, retries/failures, privacy/data
handling, model pinning, rollback, monitoring, drift, and red-team coverage. Its
report is operational evidence only; it must not be used to promote or label a
model-quality result.
`promote_production_readiness.py` additionally requires an explicit acceptance
record bound to the readiness certificate before writing committed operational
evidence.
