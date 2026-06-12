# Testing philosophy

Correctness is a build-time property. Three layers enforce it; all are deterministic.

## 1. Zero-Mock tests

No `unittest.mock`, `MagicMock`, or `mocker.patch`. Tests use real computation:
real BM25/embeddings, a real SQLite `EpisodicStore`, real temp files for figures,
and a **real in-process HTTP server** for the Ollama adapter. Selecting a real
fallback path by setting a real attribute (e.g. `store.fts_available = False` to
exercise the `LIKE` branch) is allowed — it chooses a real branch. Faking a call
boundary is forbidden.

Coverage on `src/` is gated at 90% (`pyproject.toml`); the live suite runs well
above it. Exit code 0 alone is not proof — confirm tests collected > 0 and the
coverage floor met.

## 2. Executable invariants

`src/invariants.py` encodes structural properties as runnable checks
(`all_invariants()`); `tests/test_invariants.py` asserts every one passes. They are
also surfaced on the dashboard. Adding a method means adding its invariant.

## 3. Golden regression

`tests/test_regression.py` pins headline metrics and published manuscript tokens to
golden values within a tight tolerance, and asserts `run_full_eval()` /
`generate_variables()` are byte-identical across runs. Unintended metric drift
flips a golden assertion red before it can reach the manuscript.

## When adding code

1. Add `tests/test_<module>.py` covering construction
   validation, the happy path, every documented `raise`, and a determinism check.
2. Keep the LM deterministic (`ExtractiveLM`) unless explicitly testing an adapter
   (then use `CallableLM` or the real HTTP-server fixture).
3. If you added a structural guarantee, encode it in `src/invariants.py`.
4. Re-run the suite with coverage before declaring done. Add Ruff or mypy only
   when a project-local config introduces those gates.
