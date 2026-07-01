"""Semantic retrieval: a deterministic hashing-embedding cosine lane.

The agentic-search study (Sen et al., 2026) shows dense retrieval covers
paraphrases the lexical lane misses, at the cost of admitting topical false
friends. A production deployment would back this lane with a learned embedding
model; for a reproducible, offline, zero-mock template we use a **deterministic
hashing embedding** over character n-grams. It is not a neural embedding, but it
provides genuine sub-word overlap (so paraphrases with shared morphology score
above unrelated text) and is bit-for-bit reproducible. Swap in any embedder that
returns a vector via the same :func:`embed` interface.
"""

from __future__ import annotations

import hashlib

import numpy as np

DEFAULT_DIM = 256
_NGRAM = 3

# Decimal places retained when comparing similarity scores for ranking. Genuine
# cosine differences are orders of magnitude larger than this; the rounding only
# collapses sub-1e-12 floating-point summation noise so cross-platform ordering is
# identical (see ``SemanticIndex.top_k``).
RANK_PRECISION = 12


def _char_ngrams(text: str, n: int = _NGRAM) -> list[str]:
    """Return padded character n-grams of ``text`` (whitespace-collapsed)."""
    cleaned = " ".join(text.lower().split())
    if not cleaned:
        return []
    padded = f"  {cleaned}  "
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


def embed(text: str, dim: int = DEFAULT_DIM) -> np.ndarray:
    """Embed ``text`` into a unit-norm vector via hashed character n-grams.

    Deterministic: identical input always yields an identical vector. The hash is
    SHA-1 of each n-gram, reduced modulo ``dim`` for the bucket and used to pick a
    sign, so collisions do not systematically inflate similarity.

    Args:
        text: Text to embed.
        dim: Embedding dimensionality (default 256).

    Returns:
        A float64 vector of length ``dim`` with L2 norm 1 (or all-zeros if empty).

    Raises:
        ValueError: If ``dim`` is not positive.
    """
    if dim <= 0:
        raise ValueError(f"dim must be positive, got {dim}")
    vec = np.zeros(dim, dtype=float)
    for gram in _char_ngrams(text):
        digest = hashlib.sha1(gram.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[bucket] += sign
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return vec
    return vec / norm


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two vectors (0.0 if either is the zero vector)."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class SemanticIndex:
    """Cosine-similarity index over hashing embeddings of a document corpus.

    Args:
        documents: Corpus of document strings.
        dim: Embedding dimensionality (default 256).

    Raises:
        ValueError: If ``documents`` is empty.
    """

    def __init__(self, documents: list[str], dim: int = DEFAULT_DIM) -> None:
        if not documents:
            raise ValueError("SemanticIndex requires at least one document")
        self.documents = documents
        self.dim = dim
        self._matrix = np.vstack([embed(doc, dim) for doc in documents])

    def score(self, query: str) -> list[float]:
        """Return cosine similarity of every document against ``query``."""
        q_vec = embed(query, self.dim)
        return [cosine(q_vec, row) for row in self._matrix]

    def top_k(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        """Return the top-k (doc_index, similarity) pairs, descending.

        Ties break on ascending document index. Non-positive similarities are
        dropped so unrelated text does not occupy a slot. The ordering key is
        rounded to :data:`RANK_PRECISION` decimal places so that similarities that
        are equal up to floating-point summation noise (which can differ across
        NumPy builds / CPU architectures) tie *exactly* and break deterministically
        on index — preserving bit-for-bit ranking across platforms.
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        scored = [(idx, s) for idx, s in enumerate(self.score(query)) if s > 0.0]
        scored.sort(key=lambda pair: (-round(pair[1], RANK_PRECISION), pair[0]))
        return scored[:k]


__all__ = ["embed", "cosine", "SemanticIndex", "DEFAULT_DIM", "RANK_PRECISION"]
