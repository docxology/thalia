# `scripts/` — THALIA thin orchestrators

Scripts coordinate I/O and call `src/`; they contain no business logic. Each adds
the project root and `src/` to `sys.path`, writes artifacts under `output/`, and
prints output paths to stdout for manifest collection.

| Script | Produces |
|--------|----------|
| `00_preflight.py` | Imports the package, runs one harness turn, validates output shape, and reports core/DSPy/Ollama/model/benchmark/template status |
| `run_harness_eval.py` | `output/data/eval_results.json` (full eval, noise scaling, four-size/five-seed stratified audit) plus accounting JSON, deterministic events, and per-example ledger JSONL |
| `run_compiler.py` | `output/data/compile_result.json` (MIPRO + GEPA traces) |
| `run_pipeline.py` | `output/data/pipeline_result.json` (composable Pipeline trace with intermediates; refreshes its artifact manifest entry) |
| `generate_figures.py` | `output/figures/*.png` (26 total: 21 unconditional eval/diagram figures, including sample-size precision and statistical-effect audits, plus up to 5 committed-aggregate figures) |
| `build_dashboard.py` | `output/dashboard.html` (static diagnostics dashboard) |
| `z_generate_manuscript_variables.py` | `output/data/manuscript_variables.json` + token/cross-reference/numeric/claim-ledger source checks |
| `run_query.py` | Runs one query against the harness (CLI; `--json`, `--config`, `THALIA_*` env, flags) |
| `run_demo.py` | Demo artifacts (session restart-safe recall, compiler traces, provenance) |
| `run_dspy.py` | Real DSPy runtime: `dspy.Predict` + `BootstrapFewShot` + held-out lift (opt-in) |
| `run_neural_eval.py` | Real extractive-vs-neural token-F1 measurement (opt-in; needs Ollama) |
| `run_learned_retrieval.py` | Real surrogate-vs-learned embedding recall@1 (opt-in; needs Ollama) |
| `run_injection_probe.py` | Context-poisoning resistance + neural row (opt-in; needs Ollama for neural) |
| `run_longmemeval.py` | Real LongMemEval_S benchmark accuracy/grounding + CIs (opt-in; validates every record; `--neural-limit N`, `--checkpoint-path`, and `--output-path` support resumable isolated runs) |
| `run_longmemeval_bottleneck.py` | LongMemEval bottleneck localisation + adaptive fix (opt-in; needs data; exposes `--ranking-limit`, `--sweep-values`, `--neural-limit`, and `--recall-modes-limit`; preserves the last aggregate on live failure) |
| `run_research_campaign.py` | External-volume resumable v2 Gemma 100/250/500 + Hermes 100 campaign; incomplete reports are never promoted; scope changes require explicit opt-in |
| `run_bottleneck_campaign.py` | External-volume matched 100-question Gemma max-window/adaptive campaign plus separate ranking diagnostics |
| `run_seed_sensitivity.py` | Isolated ten-seed finite synthetic sensitivity aggregate |
| `run_compiler_generalization.py` | Isolated train/held-out generalization aggregate for the in-house compiler analogues |

Run from the standalone repository root, e.g.
`uv run --project . --extra dev python scripts/run_harness_eval.py`.

The canonical local order is `run_harness_eval.py`, `run_compiler.py`,
`run_seed_sensitivity.py`, `run_compiler_generalization.py`, `run_pipeline.py`,
`generate_figures.py`, `z_generate_manuscript_variables.py`,
`run_demo.py`, `build_dashboard.py`, then `validate_artifacts.py`. The dashboard
is last among generators because it refreshes the manifest after all required
outputs exist. The validator is intentionally fail-closed when any required
artifact, formalism claim anchor, or claim-ledger JSON value is missing or mutated.
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
