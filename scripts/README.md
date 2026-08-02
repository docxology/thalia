# `scripts/` — THALIA thin orchestrators

Scripts coordinate I/O and call `src/`; they contain no business logic. Each adds
the project root and `src/` to `sys.path`, writes artifacts under `output/`, and
prints output paths to stdout for manifest collection.

| Script | Produces |
|--------|----------|
| `00_preflight.py` | Imports the package, runs one harness turn, validates output shape, and reports core/DSPy/Ollama/model/benchmark/template status |
| `run_harness_eval.py` | `output/data/eval_results.json` (full eval, noise scaling, and a configurable seeded stratified audit; the default four-size/five-seed grid is a smoke run) plus accounting JSON, deterministic events, and per-example ledger JSONL |
| `run_compiler.py` | `output/data/compile_result.json` (MIPRO + GEPA traces) |
| `run_pipeline.py` | `output/data/pipeline_result.json` (composable Pipeline trace with intermediates; refreshes its artifact manifest entry) |
| `generate_figures.py` | `output/figures/*.png` (30 total: 24 unconditional eval/diagram figures, including the claim-ceiling map and planned quality protocol, plus 6 committed-aggregate figures) |
| `build_dashboard.py` | `output/dashboard.html` (static diagnostics dashboard) |
| `z_generate_manuscript_variables.py` | `output/data/manuscript_variables.json` + token/cross-reference/numeric/claim-ledger source checks |
| `run_query.py` | Runs one query against the harness (CLI; `--json`, `--config`, `THALIA_*` env, flags) |
| `run_demo.py` | Demo artifacts (session restart-safe recall, compiler traces, provenance) |
| `run_dspy.py` | Real DSPy runtime: `dspy.Predict` + `BootstrapFewShot` + held-out lift (opt-in) |
| `run_neural_eval.py` | Real extractive-vs-neural token-F1 measurement (opt-in; needs Ollama) |
| `run_learned_retrieval.py` | Real surrogate-vs-learned embedding recall@1 (opt-in; needs Ollama) |
| `run_injection_probe.py` | Context-poisoning probe with poisoned-answer and lexical cited-excerpt/source-exposure-proxy rows (opt-in; needs Ollama for neural) |
| `run_longmemeval.py` | Real LongMemEval_S answer token-F1/citation-support/session-reachability + CIs (opt-in; validates every record; `--neural-limit N`, `--checkpoint-path`, and `--output-path` support resumable isolated runs) |
| `run_longmemeval_bottleneck.py` | LongMemEval bottleneck localisation + adaptive fix (opt-in; needs data; exposes `--ranking-limit`, `--sweep-values`, `--neural-limit`, and `--recall-modes-limit`; preserves the last aggregate on live failure) |
| `run_research_campaign.py` | External-volume resumable v2 Gemma 100/250/500 + Hermes 100 campaign; incomplete reports are never promoted; scope changes require explicit opt-in |
| `run_bottleneck_campaign.py` | External-volume matched 100-question Gemma max-window/adaptive campaign plus separate ranking diagnostics |
| `run_quality_campaign.py` | External-volume model-quality runner for the pilot or frozen confirmatory phase; emits raw observations, blinded judge packets, and provenance metadata |
| `analyze_quality.py` | Validates double annotation/adjudication and writes a fail-closed quality report with agreement, Brier/ECE calibration, reliability/selective metrics, paired comparisons, and thresholds |
| `freeze_quality_protocol.py` | Records the post-pilot rubric, primary estimand, thresholds, and pilot-report provenance before confirmation |
| `promote_quality_report.py` | Explicitly promotes only a digest-valid, threshold-passing quality certificate into committed evidence |
| `analyze_production_readiness.py` | Aggregates service observations and operational control evidence into an independent readiness report |
| `promote_production_readiness.py` | Explicitly promotes only an accepted, digest-valid operational readiness certificate |
| `run_seed_sensitivity.py` | Isolated ten-seed finite synthetic sensitivity aggregate |
| `run_compiler_generalization.py` | Isolated train/held-out generalization aggregate for the in-house compiler analogues; supports explicit seed lists for the larger publication audit |
| `analyze_integrity_advantage.py` | Endpoint-level integrity comparison report with paired statistics, provenance hashes, and native-unit promotion status |
| `freeze_provenance_p0.py` | Freezes a reviewed P0 source-record/adjudication protocol with a canonical digest; it requires owner-declared safety margins and rerun admission criteria |
| `build_provenance_p0_packets.py` | Builds keyed-order/rekeyed expert packets, a separate internal blind key, and a sealed blinding manifest from immutable external raw rows |
| `analyze_provenance_p0.py` | Validates external P0 row/run-receipt/packet/key/label ledgers, frozen rubric and atomic evidence, expert labels, factorial source-condition tables, paired strata-aware statistics, and promotion gates without promoting |
| `promote_provenance_p0.py` | Explicitly promotes only an accepted, evidence-rebuilt and revalidated, promotion-eligible P0 certificate |

Run from the standalone repository root, e.g.
`uv run --project . --extra dev python scripts/run_harness_eval.py`.

For the source-bound publication refresh, use the recorded enlarged grids rather
than the quick smoke defaults:

```bash
uv run --project . --extra dev python scripts/run_harness_eval.py \
  --per-category-values 25 50 100 250 \
  --seeds 0 1 2 3 4 5 6 7 8 9 \
  --n-boot 2000
uv run --project . --extra dev python scripts/run_compiler_generalization.py \
  --per-category 10 \
  --seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 \
  --gepa-iterations 4
```

Both aggregates record their exact size and seed grids in JSON; no result
counts should be copied manually into manuscript prose.

The canonical local order is `run_harness_eval.py`, `run_compiler.py`,
`run_seed_sensitivity.py`, `run_compiler_generalization.py`,
`analyze_integrity_advantage.py`, `run_pipeline.py`, `generate_figures.py`,
`z_generate_manuscript_variables.py`,
`run_demo.py`, `build_dashboard.py`, then `validate_artifacts.py`. The dashboard
is last among generators because it refreshes the manifest after all required
outputs exist. The validator is intentionally fail-closed when any required
artifact, formalism claim anchor, or claim-ledger JSON value is missing or mutated.
After a completed strict test/JUnit/coverage run, run `run_demo.py` (or
`build_dashboard.py`) once to refresh `verification_summary.json` from those
finished machine reports. Reconcile the `test-count` and `test-coverage`
generated-metric entries in `data/claim_ledger.yaml` only from that refreshed
summary, never from an incomplete or failing run, before the final validator
and rerun.
PDF render/validate commands belong to the
external template checkout and are optional for this standalone project. The
standalone adapter keeps the same boundary without manual symlink setup:

```bash
uv run --project ../template python scripts/render_pdf_external.py --validate
```

It fails closed if `../template` is absent or an existing template project path
would be overwritten, and removes only its temporary exact link on exit. The
template may report missing optional output directories as a non-fatal external
warning; the generated PDF and THALIA-local artifact checks remain independently
inspectable.

See [`CONVENTIONS.md`](CONVENTIONS.md) and [`AGENTS.md`](AGENTS.md).
