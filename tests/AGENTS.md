# `tests/` — Agent contract

## Testing philosophy

- **Zero-Mock (absolute).** Never use `unittest.mock`, `MagicMock`, or
  `mocker.patch`. Use real numerical examples, real `EpisodicStore` SQLite, and
  `tmp_path` for figure files. Selecting a real code path by setting a real
  attribute (e.g. `store.fts_available = False` to exercise the LIKE fallback) is
  *not* a mock — it chooses a real branch. Faking a call boundary is forbidden.
- **Determinism.** Assert exact values where computation is exact; assert bounds
  for timing/efficiency. No unseeded randomness.
- **One file per module.** Mirror `src/` structure; cover validation/error
  branches (each `raise`) and the happy path.
- **Coverage ≥ 90% on `src/`** (gate in `pyproject.toml`). Exit code 0 alone is not
  proof — confirm tests collected > 0 and coverage met.

## When adding a stage or module

1. Add `tests/test_<module>.py` covering: construction validation, the happy path,
   every documented `raise`, and at least one determinism/idempotence assertion.
2. Keep the LM deterministic (`ExtractiveLM`) unless explicitly testing an adapter.
3. Re-run the full suite with coverage before declaring done.

## Known environment-dependent branches

`episodic_store.py` lines 23–24 (FTS5-unavailable probe) only execute on a SQLite
build without FTS5; the FTS5 path is covered on builds that have it, and the LIKE
fallback is covered via the `fts_available` toggle. The `to_dspy_signature` body in
`gepa.py` is `pragma: no cover` in principle (only reachable with `dspy` installed),
but since the DSPy bridge is an explicit `dev`/`neural` extra, `test_gepa.py::
TestRealDspyBridge` runs with that extra and skips cleanly in a deterministic-
core-only environment.
`src/dspy_runtime/` (package) follows the same split: its pure adapter helpers are
unit-tested unconditionally in `test_dspy_runtime.py`, and the gated `dspy` glue
(real `dspy.Predict` + real `BootstrapFewShot` optimizer) runs with the explicit
extra while remaining outside the deterministic-core prerequisite.
