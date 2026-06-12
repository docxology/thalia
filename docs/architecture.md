# Architecture

ATLAS is five composable stages. Four run at request time (`AutoHarness`); the
fifth (Compiler) operates on the harness offline.

```text
session history + query
  ─► Stage 0  Inspector    grep/peek/partition → compact evidence windows
  ─► Stage 1  Retriever    BM25 + hashing-embedding → weighted RRF (+ optional MMR) → budget
  ─► Stage 2  Reasoner     CoT/ReAct routing (+ optional verify) → typed answer + citations
  ─► Stage 3  MemoryGate   always append raw episode; gated consolidation
  ─► HarnessOutput
  ╌► Stage 4  Compiler     (offline) MIPRO search + GEPA reflective evolution over HarnessConfig
```

## Module boundaries

- **`src/evaluation/`** — demo dataset, tight-budget experiments, `run_full_eval` bundle.
- **`src/routing.py`** — `classify_task` (orchestration-level task routing).
- **`src/signatures/`** — typed stage contracts (`stages.py`) and payload dataclasses (`payloads.py`).
- **`src/module.py`** — `Module`/`Prediction` and the `LMClient` protocol with the
  deterministic `ExtractiveLM` default. **The only model-calling code is the
  Reasoner.**
- **`src/retrieval/`** — `lexical` (BM25/grep), `semantic` (hashing-embedding
  surrogate), `fusion` (weighted RRF), `mmr` (diversity re-ranking).
- **`src/stages/`** — one module per runtime stage.
- **`src/memory/`** — append-only `episodic_store` and gated `consolidation`.
- **`src/compiler/`** — `metrics`, `mipro`, `gepa`.
- **Operability** — `config` (load/save/env), `llm` (real adapters), `harness`,
  `session` (persistence), `cli`, plus `evaluation`, `figures`, `dashboard`,
  `invariants`, `manuscript_variables`.

## Invariants the architecture preserves

1. Business logic lives in `src/`; scripts only orchestrate I/O.
2. The LM is behind a one-method protocol; the core is deterministic and offline.
3. Raw episodes are append-only and never overwritten.
4. Determinism: identical inputs reproduce identical outputs.

See [`methods.md`](methods.md) for the algorithms and `manuscript/08_reference_architecture.md`
for the full file map and design-principle table.
