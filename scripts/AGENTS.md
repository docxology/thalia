# `scripts/` — Agent contract

## Thin-orchestrator contract

Every script in this directory is a thin orchestrator: argparse, the shared
path bootstrap, I/O/serialisation, and delegated calls into `src/` entrypoints.
Business, data, plot, and analysis logic lives in `src/` (importable and
tested); if you are tempted to compute something here, it belongs in `src/`.

1. **No business logic.** Import from `src/`; scripts never implement
   algorithms, metrics, or parsing rules of their own.
2. **Identical path bootstrap.** Use the exact block from
   [CONVENTIONS.md](CONVENTIONS.md) (`PROJECT_ROOT` + `PROJECT_ROOT/src` +
   `PROJECT_ROOT.parent.parent`) before any `src.*` import, which carries
   `# noqa: E402`. Shell scripts pass the repo root to their embedded Python
   heredoc, which applies the same block (`get_longmemeval.sh`).
3. **`main()` does the work.** No module-level side effects: no work before the
   `if __name__ == "__main__":` guard other than the bootstrap and imports
   (e.g. `z_generate_manuscript_variables.py` resolves `TEMPLATE_ROOT` inside
   `main()`, never at import time).
4. **Print output paths.** Every produced artifact path is printed to stdout
   for manifest collection.
5. **Determinism.** Artifacts are byte-identical on repeated runs; JSON is
   serialised with `indent=2, sort_keys=True`.
6. **Fail loudly / fail closed.** Never silence `SystemExit` from coverage,
   crossref, or numeric-lint checks; `validate_artifacts.py` refuses missing,
   mutated, or unsafe manifest entries and runs after the final generator.

## Inventory (35 scripts; delegation map in [README.md](README.md))

| Role | Scripts | Gate |
|---|---|---|
| Deterministic generators + query CLI | `00_preflight.py`, `run_harness_eval.py`, `run_compiler.py`, `run_pipeline.py`, `run_seed_sensitivity.py`, `run_compiler_generalization.py`, `analyze_integrity_advantage.py`, `generate_figures.py`, `z_generate_manuscript_variables.py`, `run_demo.py`, `build_dashboard.py`, `run_query.py` | `dev` extra |
| Validators / frozen-protocol promoters (fail-closed) | `validate_artifacts.py`, `freeze_quality_protocol.py`, `analyze_quality.py`, `promote_quality_report.py`, `analyze_production_readiness.py`, `promote_production_readiness.py`, `freeze_provenance_p0.py`, `build_provenance_p0_packets.py`, `analyze_provenance_p0.py`, `promote_provenance_p0.py` | `dev` extra |
| Neural opt-in recorders / campaigns | `run_dspy.py`, `run_neural_eval.py`, `run_learned_retrieval.py`, `run_injection_probe.py`, `run_longmemeval.py`, `run_longmemeval_bottleneck.py`, `run_research_campaign.py`, `run_bottleneck_campaign.py`, `run_quality_campaign.py`, `run_production_readiness.py`, `run_openrouter.py` | `neural` extra + live model/network |
| External helpers | `get_longmemeval.sh` (benchmark download + validation), `render_pdf_external.py` (optional `../template` PDF) | bash / template project |

## Gotchas

- **`z_` scripts run late.** Manuscript hydration happens after figures; the
  token-coverage, crossref, bibliography, numeric-lint, and claim-ledger checks
  are fail-closed — never bypass them.
- **Template injection is optional.** Without `../template` on the path,
  `z_generate_manuscript_variables.py` prints a `[skip]` line and still writes
  `output/data/manuscript_variables.json`; source-only generation must work in
  a clean checkout.
- **External roots, never implicit promotion.** The campaign/quality/production
  runners write raw rows, checkpoints, and packets only to caller-selected
  external roots. Only the dedicated `promote_*` scripts create entries under
  `data/`, and only behind digest/threshold/acceptance gates. An incomplete or
  below-threshold run is never promoted implicitly.
- **`verification_summary.json` hygiene.** Refresh it via `run_demo.py` or
  `build_dashboard.py` only after a completed strict test/JUnit/coverage run;
  retain observed counts and percentages in that generated summary. They are
  volatile run observations, not fixed numeric manuscript-ledger entries.
- **Large external data.** `get_longmemeval.sh` downloads ~277 MB into
  `data/longmemeval/`; the benchmark is validated before its `.partial` file is
  moved into place and is never committed.
- **Zero-Mock.** No `unittest.mock`/`MagicMock` in scripts or tests; use real
  data, real SQLite, and real temp files.
- **Keep `scripts/` clean.** No `__pycache__/`, `.DS_Store`, or deprecated
  shims; remove a shim only after grep confirms zero callers.
