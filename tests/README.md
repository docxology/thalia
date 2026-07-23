# `tests/` — THALIA test suite

Zero-Mock test suite, one file per `src/` module. All tests use real data, real
SQLite, and deterministic computation — no `unittest.mock`, no `MagicMock`.

## Running

```bash
uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing --cov-report=json:output/reports/coverage.json \
  --junitxml=output/reports/pytest.xml --cov-fail-under=90
```

`tests/conftest.py` forces a headless matplotlib backend and adds the project root
and `src/` to `sys.path`. Coverage measures `src/` only (config in `pyproject.toml`).

## Files

Core modules: `test_signatures` · `test_module` · `test_lexical` · `test_semantic` ·
`test_fusion` · `test_mmr` · `test_expansion` · `test_learned` · `test_inspector` ·
`test_retriever` · `test_reasoner` · `test_routing` · `test_memory_gate` ·
`test_episodic_store` · `test_consolidation` · `test_recall` · `test_metrics` ·
`test_mipro` · `test_gepa` · `test_config` · `test_config_io` · `test_harness` ·
`test_pipeline` · `test_session` · `test_evaluation` · `test_ablation` ·
`test_scaling` · `test_longmemeval` · `test_figures` · `test_manuscript_variables` ·
`test_manuscript_integrity` · `test_provenance` · `test_dashboard` ·
`test_dspy_runtime` · `test_llm` · `test_cli` · `test_determinism`.

Cross-cutting: `test_invariants` · `test_property_invariants` · `test_regression` ·
`test_fuzz` · `test_scripts_smoke`.

See [`AGENTS.md`](AGENTS.md) for the testing philosophy and patterns.
