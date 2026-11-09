# Testing philosophy

Correctness is a build-time property. Three layers enforce it; the deterministic
core is reproducible, while optional live-model adapters are explicitly model-dependent.

## 1. Zero-Mock tests

No `unittest.mock`, `MagicMock`, or `mocker.patch`. Tests use real computation:
real BM25/embeddings, a real SQLite `EpisodicStore`, real temp files for figures,
and **real in-process HTTP servers** for direct Ollama/OpenRouter adapters and
common benchmark provider behavior. Selecting a real fallback path by setting a
real attribute (e.g. `store.fts_available = False` to exercise `LIKE`) is allowed;
faking a call boundary is forbidden. Loopback behavior tests do not establish
live-provider quality or availability.

Coverage on `src/` is gated at 90% (`pyproject.toml`). Current counts and coverage
belong in finished machine reports, not an undated pass assertion. Exit code 0
alone is not proof — confirm collection and the coverage floor. Optional DSPy
classes skip without the SDK. Neural DSPy generation additionally requires
`THALIA_LIVE_TESTS=1` and server/model availability; collection never generates.

## 2. Executable invariants

`src/invariants.py` encodes structural properties as runnable checks
(`all_invariants()`); `tests/test_invariants.py` asserts every one passes. They are
also surfaced on the dashboard. Adding a method means adding its invariant.

## 3. Artifact integrity

`src.provenance.validate_artifact_manifest` is the refusal boundary for generated
outputs. It checks that every manifest entry is a safe relative path whose current
size and SHA-256 match the recorded values, and that the required paths declared in
`domain_profile.yaml` are present. Run `scripts/validate_artifacts.py` after the
last generator and before rendering; a green test suite alone does not certify
that a PDF or dashboard was built from the current JSON and figures. The same
validator checks `data/claim_ledger.yaml` structure, safe anchors, declared JSON
fields, and strict formalism claim-artifact resolution. Source-only manuscript
generation remains valid before `output/` exists; the release-time validator owns
the generated-artifact check.

The optional benchmark's `validate_backend_benchmark(payload)` is a separate
schema-2 consistency gate before writing or consumer use. It rebuilds all seeded
cohorts and verifies the exact backend × method × example matrix and schedule,
method configs, prompt/dataset/content identities, producer-inventory structure,
finite scores/times, recomputed token-F1, cell/group summaries and paired results.
Prompt agreement is within example/method across backends, not across methods.
Schema 1 is rejected; historical artifacts are preserved, never upgraded in place.

Negative controls must cover missing/duplicate cells, schedule/fingerprint drift,
altered summaries and paired contrasts, incomplete pairs suppressing both delta
and interval, a single seed suppressing interval, and visible small-seed warnings.
Real loopback server tests exercise genuine full-context requests, harness-selected
context, optional Ollama context options, and failures without mocks or live-model
claims. Honest incomplete diagnostics retain denominators and a sidecar rather
than replacing the last good destination. Checksums establish consistency, not
authenticity, expert quality, power, promotion or production readiness. See
[`backend_benchmark.md`](backend_benchmark.md).

## 4. Golden regression

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
4. Re-run the suite with coverage before declaring done. The repository also
   enforces `mypy src` and `ruff check src tests scripts` as static gates.

The model-quality lane has its own zero-mock contract. Tests use real
temporary files and real deterministic model adapters to exercise the pilot
partition, held-out exclusion, strict ordinal/binary labels, blinded packets,
paired condition completeness, answer/config/model/code provenance, confidence
parsing, calibration, inter-rater agreement, clustered paired statistics, failed
rows, threshold failures, certificate digests, and promotion refusal. The v2 live
campaign remains operational evidence and is not converted into quality labels.
