# `scripts/` — THALIA thin orchestrators

Scripts coordinate I/O and call `src/`; they contain no business logic. Each adds
the project root and `src/` to `sys.path`, writes artifacts under `output/`, and
prints output paths to stdout for manifest collection.

| Script | Produces |
|--------|----------|
| `00_preflight.py` | Imports the package, runs one harness turn, validates output shape, probes Ollama |
| `run_harness_eval.py` | `output/data/eval_results.json` (full eval + noise scaling) |
| `run_compiler.py` | `output/data/compile_result.json` (MIPRO + GEPA traces) |
| `run_pipeline.py` | `output/data/pipeline_result.json` (composable Pipeline trace with intermediates) |
| `generate_figures.py` | `output/figures/*.png` (nine manuscript/dashboard figures) |
| `build_dashboard.py` | `output/dashboard.html` (static diagnostics dashboard) |
| `z_generate_manuscript_variables.py` | `output/data/manuscript_variables.json` + token-coverage check |
| `run_query.py` | Runs one query against the harness (CLI; `--json`, `--config`, `THALIA_*` env, flags) |
| `run_demo.py` | Demo artifacts (session restart-safe recall, compiler traces, provenance) |
| `run_dspy.py` | Real DSPy runtime: `dspy.Predict` + `BootstrapFewShot` + held-out lift (opt-in) |
| `run_neural_eval.py` | Real extractive-vs-neural token-F1 measurement (opt-in; needs Ollama) |
| `run_learned_retrieval.py` | Real surrogate-vs-learned embedding recall@1 (opt-in; needs Ollama) |
| `run_injection_probe.py` | Context-poisoning resistance + neural row (opt-in; needs Ollama for neural) |
| `run_longmemeval.py` | Real LongMemEval_S benchmark accuracy/grounding + CIs (opt-in; needs data) |
| `run_longmemeval_bottleneck.py` | LongMemEval bottleneck localisation + adaptive fix (opt-in; needs data) |

Run from the repository root, e.g.
`uv run --project working/thalia python working/thalia/scripts/run_harness_eval.py`.

See [`CONVENTIONS.md`](CONVENTIONS.md) and [`AGENTS.md`](AGENTS.md).
