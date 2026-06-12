"""Hybrid retrieval lane for the ATLAS harness.

Three deterministic, offline-testable components implement the
"lexical-first, hybrid by default" finding of Sen et al. (2026):

* :mod:`src.retrieval.lexical` — BM25 (Okapi) scoring plus grep/regex anchoring.
* :mod:`src.retrieval.semantic` — a deterministic hashing-embedding cosine lane.
* :mod:`src.retrieval.fusion` — weighted Reciprocal Rank Fusion (RRF).
* :mod:`src.retrieval.mmr` — Maximal Marginal Relevance diversity re-ranking.
* :mod:`src.retrieval.expansion` — pseudo-relevance-feedback query expansion.
"""

from .expansion import expand_query
from .fusion import ScoredChunk, rrf_fuse
from .lexical import BM25Index, extract_key_phrases, grep
from .mmr import mmr_rerank
from .semantic import SemanticIndex, embed

__all__ = [
    "BM25Index",
    "grep",
    "extract_key_phrases",
    "SemanticIndex",
    "embed",
    "rrf_fuse",
    "ScoredChunk",
    "mmr_rerank",
    "expand_query",
]
