# `scripts/` — ATLAS thin orchestrators

Scripts coordinate I/O and call `src/`; they contain no business logic. Each adds
the project root and `src/` to `sys.path`, writes artifacts under `output/`, and
prints output paths to stdout for manifest collection.

| Script | Produces |
|--------|----------|
| `00_preflight.py` | Imports the package, runs one harness turn, validates output shape |
| `run_harness_eval.py` | `output/data/eval_results.json` (full eval + noise scaling) |
| `run_compiler.py` | `output/data/compile_result.json` (MIPRO + GEPA traces) |
| `generate_figures.py` | `output/figures/*.png` (nine manuscript/dashboard figures) |
| `build_dashboard.py` | `output/dashboard.html` (static diagnostics dashboard) |
| `z_generate_manuscript_variables.py` | `output/data/manuscript_variables.json` + token-coverage check |
| `run_query.py` | Runs one query against the harness (CLI; `--json`, `--config`, `ATLAS_*` env, flags) |

Run from the repository root, e.g.
`uv run --project working/atlas python working/atlas/scripts/run_harness_eval.py`.

See [`CONVENTIONS.md`](CONVENTIONS.md) and [`AGENTS.md`](AGENTS.md).
