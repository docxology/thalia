"""Maximal Marginal Relevance (MMR) re-ranking for evidence diversity.

After the lexical+semantic lanes are fused by RRF, the top windows can be
near-duplicates (the same fact phrased twice). MMR (Carbonell & Goldstein, 1998)
re-orders the candidates to trade relevance against novelty:

    MMR(i) = lambda * rel(i) - (1 - lambda) * max_{j in selected} sim(i, j)

where ``rel`` is the min-max-normalised fused score and ``sim`` is the cosine of
the deterministic hashing embeddings of the window texts. lambda=1 reduces to
pure relevance (the fusion order); lambda=0 maximises diversity. The selection is
greedy and fully deterministic (ties break on relevance, then ascending index).
"""

from __future__ import annotations

from ..signatures import RankedEvidence
from .semantic import cosine, embed


def mmr_rerank(
    ranked: list[RankedEvidence],
    lambda_: float = 0.7,
    k: int | None = None,
) -> list[RankedEvidence]:
    """Re-order ranked evidence by Maximal Marginal Relevance.

    Args:
        ranked: Evidence already scored by fusion (``.score`` is the relevance).
        lambda_: Relevance/diversity tradeoff in [0, 1] (1 = pure relevance).
        k: Number of items to select (defaults to all of ``ranked``).

    Returns:
        A re-ordered list of the same :class:`RankedEvidence` objects, length
        ``min(k, len(ranked))``.

    Raises:
        ValueError: If ``lambda_`` is outside [0, 1] or ``k`` is non-positive.
    """
    if not 0.0 <= lambda_ <= 1.0:
        raise ValueError(f"lambda_ must be in [0, 1], got {lambda_}")
    if k is not None and k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    if len(ranked) <= 1:
        return list(ranked)

    limit = len(ranked) if k is None else min(k, len(ranked))
    scores = [r.score for r in ranked]
    lo, hi = min(scores), max(scores)
    span = hi - lo
    rel = [(s - lo) / span if span > 0 else 1.0 for s in scores]
    embeds = [embed(r.window.text) for r in ranked]

    remaining = set(range(len(ranked)))
    # Seed with the most relevant item (ties -> lower index).
    first = max(remaining, key=lambda i: (rel[i], -i))
    selected = [first]
    remaining.discard(first)

    while remaining and len(selected) < limit:
        candidates = sorted(remaining)
        best_idx = candidates[0]
        best_key: tuple[float, float, int] | None = None
        for i in candidates:
            max_sim = max(cosine(embeds[i], embeds[j]) for j in selected)
            mmr = lambda_ * rel[i] - (1.0 - lambda_) * max_sim
            key = (mmr, rel[i], -i)
            if best_key is None or key > best_key:
                best_key = key
                best_idx = i
        selected.append(best_idx)
        remaining.discard(best_idx)

    return [ranked[i] for i in selected]


__all__ = ["mmr_rerank"]
