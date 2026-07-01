# `src/` — Agent contract

Public API surface and invariants for the THALIA implementation. Import via the
`src.` package prefix (e.g. `from src.harness import AutoHarness`).

## Routing

- `classify_task(query: str) -> TaskCategory` — deterministic keyword router in
  [`routing.py`](routing.py); used by [`harness.py`](harness.py) before stages run.

## Entry points

- `AutoHarness(config?, lm?, episodic_store?, memory_snapshot?)` —
  `.forward(query, session_history, session_ending=False) -> HarnessOutput`;
  `.run(example) -> HarnessOutput`.
- `build_run_fn(config, lm?) -> (example -> HarnessOutput)` — fresh harness per
  call; the contract the compilers rely on for order-independent evaluation.
- `AutoHarness(..., start_turn=N)` — resume turn IDs (used by `Session` on reopen).

## Operability contracts

- `Session(config?, lm?, db_path=':memory:', memory_path?)` — `.ask(query,
  extra_context='', session_ending=False) -> HarnessOutput`; `.turn_count`;
  `.close()`. File-backed, append-only, reconstructs transcript on reopen.
- `run_query(query, session_history='', config?, lm?) -> dict` — one-shot with
  Inspector diagnostics in `inspector_metadata`;
  `cli.main(argv) -> int` is the CLI entry; `resolve_config(args)` applies
  file < env < flag precedence.
- `load_config(path, apply_env=True)`, `save_config(config, path)`,
  `apply_env_overrides(config)` — `THALIA_*` env vars map to config fields.
- LM adapters: `CallableLM(fn)`, `OllamaLM(model?, host?, timeout?)` (raises
  `OllamaError`, never silent), both satisfy `LMClient`.

## Stage contracts

| Stage | Constructor | `forward` returns (`Prediction` keys) |
|-------|-------------|----------------------------------------|
| `Inspector(max_windows=15)` | — | `evidence_windows`, `metadata` (line count, selected indices, effective window budget, adaptive flag) |
| `Retriever(top_k=8, k=60, lexical_weight?, semantic_weight?)` | — | `ranked_evidence`, `delivery_mode` |
| `Reasoner(lm?, max_evidence=5)` | — | `reasoning_trace`, `answer`, `evidence_citations`, `requires_consolidation` |
| `MemoryGate(episodic_store?, memory_md='')` | — | `episodic_entry`, `consolidation_action`, `memory_delta` |

## Retrieval contracts

- `BM25Index(documents, k1=1.5, b=0.75).top_k(query, k) -> [(idx, score)]`
- `SemanticIndex(documents, dim=256).top_k(query, k) -> [(idx, score)]`
- `rrf_fuse(lexical, semantic, k=60, lexical_weight=0.65, semantic_weight=0.35) -> [FusedChunk]`

## Memory contracts

- `EpisodicStore(db_path=':memory:')` — `append` (raises on duplicate `turn_id`),
  `get`, `all`, `count`, `search`, `close`. Append-only.
- `decide_action(requires_consolidation, criteria, memory_exists) -> ConsolidationAction`
- `should_consolidate(flag, criteria) -> bool` — requires BOTH.

## Compiler contracts

- `MIPROCompiler(auto='light'|'medium'|'heavy').compile(build_fn, dataset, candidates?) -> CompileResult`
- `GEPAOptimizer().evolve(build_fn, dataset, seed_config?, iterations=8) -> CompileResult`
- `check_skill_constraints(text, max_bytes=15360) -> SkillConstraintReport`
- `harness_metric(output, example) -> float` in [0, 1]; `evaluate(run_fn, dataset) -> EvalReport`

## Invariants

Determinism; raw episodes never overwritten; LM only in the Reasoner; no
`infrastructure.*` imports; ≥ 90% coverage. Full rationale in the project-root
[`AGENTS.md`](../AGENTS.md).
