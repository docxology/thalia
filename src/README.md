# `src/` — THALIA implementation

All business logic lives here. Pure, deterministic, offline-testable Python; the
only model-calling code is the Reasoner via the `LMClient` protocol.

## Packages

- **Top-level:** `signatures/` (framework, payloads, stage contracts), `module.py`
  (Module/Predict/LM layer + `tokenize`), `config.py` (`HarnessConfig` + load/save/env
  + `to_yaml`/`from_yaml`), `llm.py` (real LM adapters), `harness.py` (`AutoHarness`),
  `pipeline.py` (composable `Pipeline` with intermediates + custom steps),
  `session.py` (persistent multi-turn, context-manager safe), `cli.py` (query CLI),
  `evaluation/` (dataset + experiments + `schemas.py`), `figures/` (plots, diagrams,
  manifest), `dspy_runtime/` (gated DSPy adapters), `manuscript_variables.py`.
- **`retrieval/`** — `lexical.py` (BM25 + grep), `semantic.py` (hashing-embedding
  cosine surrogate), `fusion.py` (weighted RRF), `mmr.py` (diversity re-ranking),
  `expansion.py` (PRF query expansion).
- **`stages/`** — `inspector.py`, `retriever.py`, `reasoner.py`, `memory_gate.py`.
- **`memory/`** — `episodic_store.py` (SQLite + FTS5, append-only, context-manager
  safe), `consolidation.py`.
- **`compiler/`** — `metrics.py`, `mipro.py`, `gepa.py`.

## Rules

- No `infrastructure.*` imports — the package is self-contained (numpy + stdlib).
- Full type hints and docstrings on public APIs; `py.typed` marker for PEP 561.
- `__version__` is exported at the top level (`from src import __version__`).
- Deterministic: fixed structure, no unseeded RNG, no network.
- See [`AGENTS.md`](AGENTS.md) for the per-symbol contract and invariants.
