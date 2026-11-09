# Architecture

THALIA is five composable stages. Four run at request time (`AutoHarness`); the
fifth (Compiler) operates on the harness offline.

```text
session history + query
  ─► Stage 0  Inspector    grep/peek/partition → compact evidence windows
  ─► Stage 1  Retriever    BM25 + hashing-embedding → weighted RRF → budget
  ─► Stage 2  Reasoner     routed selection → typed answer + citations
  ─► Stage 3  MemoryGate   always append raw episode; gated consolidation
  ─► HarnessOutput
  ╌► Stage 4  Compiler     offline MIPRO search + GEPA evolution
```

## Module boundaries

- **`src/evaluation/`** — demo dataset, tight-budget experiments, `run_full_eval` bundle.
- **`src/routing.py`** — `classify_task` (orchestration-level task routing).
- **`src/signatures/`** — typed stage contracts (`stages.py`) and payload dataclasses (`payloads.py`).
- **`src/module.py`** — `Module`/`Prediction` and the `LMClient` protocol with the
  deterministic `ExtractiveLM` default. In the runtime harness, the Reasoner owns
  model calls. Optional DSPy diagnostics are a separate full-context path.
- **`src/retrieval/`** — `lexical` (BM25/grep), `semantic` (hashing-embedding
  surrogate), `fusion` (weighted RRF), `mmr` (diversity re-ranking).
- **`src/stages/`** — one module per runtime stage.
- **`src/memory/`** — append-only `episodic_store` and gated `consolidation`.
- **`src/compiler/`** — `metrics`, `mipro`, `gepa`.
- **`src/pipeline.py`** — `Pipeline`/`PipelineStep`/`PipelineContext`: the same four
  runtime stages as `AutoHarness` exposed as a composable, inspectable chain.
  Callers can omit stages, insert custom steps using `PipelineContext.extras`,
  and inspect per-step snapshots via `pipeline.intermediates` after `run()`.
  Built-in state and extras mappings are copied; opaque extras values remain
  caller-owned shared references. Output construction is not an additional step.
- **Operability** — `config` (load/save/env), `llm` (real adapters), `harness`,
  `session` (persistence), `cli`, plus `evaluation`, `figures`, `dashboard`,
  `invariants`, `manuscript_variables`, and `formalism_traceability` (the
  machine-checked bridge from equations to code, tests, and artifacts).
- **`src/py.typed`** — PEP 561 marker; downstream type-checkers treat the package as
  typed without additional configuration.
- **`src/evaluation/backend_benchmark.py`** — optional schema-2 backend × method
  × example orchestration. `BenchmarkMethod` separates context selection from
  `BenchmarkBackend` identity. Harness arms use fresh context-managed state;
  `full_context` directly calls the real LM with the same typed Reasoner
  renderer/query and every history line, bypassing Inspector/Retriever.
  Methods do not share selected context, and submission is not a provider
  retention guarantee. One completion attempt, no retries/benchmark cache.
  Method fingerprints, execution schedule, portable producer provenance,
  cell/category/stratum summaries and paired seed-mean contrasts are validated
  before offline dashboard/manuscript consumption. Schema 1 is rejected rather
  than adapted; historical cohorts stay unchanged. See
  [`backend_benchmark.md`](backend_benchmark.md) and the declared
  [`local_method_study.md`](local_method_study.md).

## Invariants the architecture preserves

1. Business logic lives in `src/`; scripts only orchestrate I/O.
2. The LM is behind a one-method protocol; the core is deterministic and offline.
3. Raw episodes are append-only and never overwritten.
4. Determinism: identical inputs reproduce identical outputs.
5. Resource safety: `Session` and `EpisodicStore` implement `__enter__`/`__exit__`
   so connections are released even when callers exit via exception.

See [`methods.md`](methods.md) for the algorithms and `docs/manuscript/08_reference_architecture.md`
for the full file map and design-principle table.
