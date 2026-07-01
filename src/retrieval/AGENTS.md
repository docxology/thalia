# `src/retrieval/` — Agent contract

Barrel package: `from src.retrieval import BM25Index, SemanticIndex, rrf_fuse, …`

## Role

Hybrid retrieval lane: lexical-first (BM25), semantic (hashing-embedding
cosine), and RRF fusion. All components are deterministic, offline-testable, and
require no network calls. The learned Ollama lane (`learned.py`) is an optional
extension gated on a live model.

## Module map

| Module | Contents |
|--------|----------|
| [`lexical.py`](lexical.py) | `BM25Index` (Okapi BM25), `extract_key_phrases`, `grep`, `STOPWORDS` |
| [`semantic.py`](semantic.py) | `embed` (hashing n-gram), `cosine`, `SemanticIndex` |
| [`fusion.py`](fusion.py) | `rrf_fuse`, `ScoredChunk`, `FusedChunk`; RRF constants |
| [`mmr.py`](mmr.py) | `mmr_rerank` — Maximal Marginal Relevance diversity re-ranker |
| [`expansion.py`](expansion.py) | `expand_query` — RM3-style pseudo-relevance-feedback expansion |
| [`learned.py`](learned.py) | `LearnedSemanticIndex`, `embed_ollama`; paraphrase probes, `dense_rag_answer` |
| [`__init__.py`](__init__.py) | Barrel re-export of deterministic components (no `learned`) |

## Hybrid retrieval pipeline

```
Inspector windows
  │
  ├─► BM25Index.top_k(query)     → list[(idx, score)]  (lexical lane)
  ├─► SemanticIndex.top_k(query) → list[(idx, score)]  (semantic lane)
  │
  └─► rrf_fuse(lexical, semantic, k=60,
               lexical_weight=0.65, semantic_weight=0.35)
        → list[FusedChunk]  (sorted by fused_score desc, ties by ascending id)
```

Default lane weights reflect the agentic-search finding that lexical recall
dominates under inline delivery. Per-category overrides are applied by the
`Retriever` stage.

## Key invariants

- **Determinism**: `BM25Index.top_k` and `SemanticIndex.top_k` both round
  scores to 12 decimal places before sort; ties break on ascending document
  index. Results are bit-for-bit identical across platforms.
- **Semantic surrogate**: `embed` uses SHA-1-hashed character trigrams projected
  to a 256-dim unit vector — genuine sub-word overlap, not neural. Zero vectors
  (empty text) produce 0.0 cosine rather than NaN.
- **RRF deduplication**: `rrf_fuse` collapses duplicate ids within each lane to
  their first occurrence before scoring, so each id contributes exactly once.
- **MMR greedily selects**, seeding on the most-relevant item then maximising
  `λ·rel(i) − (1−λ)·max_sim(i, selected)`. `lambda_=1.0` degenerates to pure
  relevance order; `lambda_=0.0` maximises diversity.
- **Expansion is off by default**: `expand_query` is called only when
  `Retriever(query_expansion=True)`; it must not run in the deterministic hot
  path unless explicitly enabled.
- **No LM anywhere in this package**.

## Extension points

1. **Real embedder**: replace `SemanticIndex` with `LearnedSemanticIndex` from
   `learned.py`. Both expose identical `.score(query) -> list[float]` and
   `.top_k(query, k) -> list[(idx, score)]` interfaces; no other code changes.
2. **Learned lane**: `LearnedSemanticIndex(documents, model='nomic-embed-text')`
   calls a live Ollama `/api/embed` endpoint. Gated on `embed_model_available()`;
   never required by the deterministic core.
3. **Custom fusion weights**: pass `lexical_weight` / `semantic_weight` to
   `rrf_fuse` directly, or via `Retriever(lexical_weight=…, semantic_weight=…)`.

## Paraphrase probes (`learned.py`)

`PARAPHRASE_PROBES` — 4 (query, docs, gold_idx) tuples where query and gold
document share meaning but little surface morphology. Used by:
- `surrogate_recall_at_1()` — offline, deterministic.
- `learned_recall_at_1(model=…)` — requires live Ollama model.
- `paraphrase_retrieval_probe(model=…)` — returns a full comparison dict.

## `__all__` exports (barrel)

`BM25Index`, `grep`, `extract_key_phrases`, `SemanticIndex`, `embed`,
`rrf_fuse`, `ScoredChunk`, `mmr_rerank`, `expand_query`

(`learned.py` exports are not re-exported by the barrel; import directly from
`src.retrieval.learned` when needed.)
