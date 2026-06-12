# Glossary

- **ATLAS** — Agentic Typed-pipeline with Lexical And Structured stages.
- **Signature** — a declarative typed I/O contract for a stage (DSPy-style),
  `src/signatures/`.
- **Inspector** — Stage 0; RLM-style context narrowing (grep/peek/partition).
- **Retriever** — Stage 1; lexical+semantic lanes fused by RRF, optional MMR.
- **Reasoner** — Stage 2; typed reasoning (CoT/ReAct), optional verification.
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
