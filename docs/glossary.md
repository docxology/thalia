# Glossary

- **THALIA** — Agentic Typed-pipeline with Lexical And Structured stages.
- **Signature** — a declarative typed I/O contract for a stage (DSPy-style),
  `src/signatures/`.
- **Inspector** — Stage 0; RLM-style context narrowing (grep/peek/partition).
- **Retriever** — Stage 1; lexical+semantic lanes fused by RRF, optional MMR.
- **Reasoner** — Stage 2; one model completion over ranked evidence, with a
  deterministic ReAct-style read→integrate route for multi-hop/code/update
  categories and optional token-support verification. It does not expose hidden
  chain-of-thought.
- **Memory Gate** — Stage 3; episodic-first storage with gated consolidation.
- **Compiler** — Stage 4 (offline); MIPRO search + GEPA evolution over `HarnessConfig`.
- **BM25** — Okapi lexical relevance score (`k1=1.5`, `b=0.75`).
- **RRF** — Reciprocal Rank Fusion; merges ranked lists by `w/(k+rank+1)`.
- **MMR** — Maximal Marginal Relevance; relevance/diversity re-ranking via `mmr_lambda`.
- **PRF / query expansion** — pseudo-relevance feedback; augments the query with
  frequent terms from its own top windows (`query_expansion`).
- **Recency weighting** — a bonus favouring later session turns (`recency_weight`).
- **Memory recall** — read-only inference-time search of the episodic store +
  MEMORY.md, surfaced as evidence (`recall_memory`); recalled windows use negative
  source indices.
- **Method ablation** — composite metric for base + each added method + all combined.
- **Hashing embedding** — deterministic character-n-gram surrogate for the
  semantic lane (not a learned dense retriever).
- **Evidence window** — a compact, query-anchored slice of session history.
- **Episodic store** — append-only SQLite (+FTS5) record of raw turns; never overwritten.
- **Consolidation** — deriving a MEMORY.md delta from raw episodes, explicitly gated.
- **Delivery mode** — `inline` vs `file_based` (sparse context budgeting).
- **Composite metric** — `0.6·accuracy + 0.3·grounding + 0.1·efficiency`.
- **Invariant** — an executable structural property in `src/invariants.py`.
- **Generated token** — a `{{NAME}}` manuscript placeholder emitted by
  `src/manuscript_variables.py`.
- **ExtractiveLM / CallableLM / OllamaLM** — the deterministic default LM, a
  callable wrapper, and the real Ollama HTTP adapter.
- **Pipeline** — composable alternative to `AutoHarness` (`src/pipeline.py`);
  exposes the same four runtime stages as an ordered chain of `PipelineStep`
  objects. Callers choose which stages to include, insert custom steps anywhere in
  the chain, and read per-step intermediates via `pipeline.intermediates` after
  `run()`. Built with the same stage classes and config defaults as `AutoHarness`,
  so outputs are identical given identical inputs.
- **PipelineContext** — mutable state bag threaded through a `Pipeline` run; carries
  the query, session history, and all stage outputs (windows, ranked evidence,
  answer, citations, memory delta, etc.). Custom steps read and write this bag.
- **Context manager** — `Session` and `EpisodicStore` both implement
  `__enter__`/`__exit__` so a `with` block guarantees that the underlying SQLite
  connection is closed even if an exception is raised mid-session.
- **`to_yaml` / `from_yaml`** — instance / class methods on `HarnessConfig`
  (`src/config.py`) that own the YAML serialisation logic. `save_config` and
  `load_config` are thin orchestration wrappers that delegate to these methods.
- **`to_dict`** — method on `HarnessOutput` (`src/signatures/payloads.py`) that
  serialises a harness result to a plain dict; `cli.output_to_dict` delegates to it.
- **`py.typed`** — empty PEP 561 marker file at `src/py.typed`; tells type-checkers
  such as mypy and pyright that the package ships inline type annotations.
- **`__version__`** — the package version string (`"0.1.0"`) exported from
  `src/__init__.py`; importable as `from src import __version__`.
- **`turn_count`** — read-only property on `Session` returning the number of turns
  recorded in the underlying episodic store for the current session.
