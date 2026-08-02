# Contributing to THALIA

THALIA is a research-grade, source-bound software and manuscript project. Pull
requests should preserve both the executable contracts and the distinction
between implemented diagnostics and promoted scientific claims.

## Development setup

Use Python 3.10 or newer and `uv`:

```bash
uv sync --project . --extra dev
```

Run the authoritative checks before opening a pull request:

```bash
PYTHONWARNINGS=error::ResourceWarning uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing --cov-fail-under=90
uv run --project . --extra dev mypy src
uv run --project . --extra dev ruff check src tests scripts
uv run --project . --extra dev python -m compileall -q src scripts
uv lock --check
uv build
```

For manuscript or evaluation changes, also regenerate the affected artifacts,
run `scripts/validate_artifacts.py`, and render the PDF/HTML last. Do not
hand-edit generated tokens, figures, dashboards, or reports as a substitute
for fixing their producer.

## Project contracts

- Business logic belongs in `src/`; scripts are thin I/O orchestrators.
- The deterministic core has no network, wall-clock branching, or unseeded
  randomness, and keeps model calls behind the `LMClient` protocol.
- Tests use real data, temporary files, SQLite, and in-process services; do not
  add `unittest.mock`, `MagicMock`, or boundary mocks.
- Raw episodic records are append-only. Derived consolidation must remain gated
  and auditable.
- Preserve negative controls, failed gates, uncertainty statements, and
  conditional claims. A passing implementation test is not evidence of a
  population-level scientific or production guarantee.
- Keep credentials, private raw answers, external-volume data, and unlicensed
  benchmark content out of Git. Generated `output/` is intentionally ignored.

## Pull-request checklist

- [ ] The change is scoped and the relevant source/tests/docs are included.
- [ ] Tests, coverage, lint, typing, compilation, and packaging checks pass.
- [ ] New claims have a source, estimand, uncertainty statement, and explicit
      evidence tier.
- [ ] Figures are data-driven, legible, captioned, and regenerated from their
      registered producer.
- [ ] Manuscript tokens and rendered outputs were validated when applicable.
- [ ] No secrets, private data, generated local state, or unrelated worktree
      files are included.
