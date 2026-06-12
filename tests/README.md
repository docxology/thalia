# `tests/` — ATLAS test suite

Zero-Mock test suite, one file per `src/` module. All tests use real data, real
SQLite, and deterministic computation — no `unittest.mock`, no `MagicMock`.

## Running

```bash
uv run --project working/atlas pytest working/atlas/tests/ \
  --cov=working/atlas/src --cov-report=term-missing --cov-fail-under=90
```

`tests/conftest.py` forces a headless matplotlib backend and adds the project root
and `src/` to `sys.path`. Coverage measures `src/` only (config in `pyproject.toml`).

## Files

`test_signatures` · `test_module` · `test_lexical` · `test_semantic` ·
`test_fusion` · `test_inspector` · `test_retriever` · `test_reasoner` ·
`test_memory_gate` · `test_episodic_store` · `test_consolidation` ·
`test_metrics` · `test_mipro` · `test_gepa` · `test_config` · `test_harness` ·
`test_evaluation` · `test_figures` · `test_manuscript_variables`.

See [`AGENTS.md`](AGENTS.md) for the testing philosophy and patterns.
