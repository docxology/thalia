# `src/` — ATLAS implementation

All business logic lives here. Pure, deterministic, offline-testable Python; the
only model-calling code is the Reasoner via the `LMClient` protocol.

## Packages

- **Top-level:** `signatures/` (framework, payloads, stage contracts), `module.py`
  (Module/LM layer), `config.py` (`HarnessConfig` + load/save/env), `llm.py`
  (real LM adapters), `harness.py` (`AutoHarness`), `session.py` (persistent
  multi-turn), `cli.py` (query CLI), `evaluation/` (dataset + experiments),
  `figures.py`, `manuscript_variables.py`.
- **`retrieval/`** — `lexical.py` (BM25 + grep), `semantic.py` (hashing-embedding
  cosine surrogate), `fusion.py` (weighted RRF).
- **`stages/`** — `inspector.py`, `retriever.py`, `reasoner.py`, `memory_gate.py`.
- **`memory/`** — `episodic_store.py` (SQLite + FTS5, append-only), `consolidation.py`.
- **`compiler/`** — `metrics.py`, `mipro.py`, `gepa.py`.

## Rules

- No `infrastructure.*` imports — the package is self-contained (numpy + stdlib).
- Full type hints and docstrings on public APIs.
- Deterministic: fixed structure, no unseeded RNG, no network.
- See [`AGENTS.md`](AGENTS.md) for the per-symbol contract and invariants.
