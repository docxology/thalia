"""Weighted Reciprocal Rank Fusion (RRF) for the hybrid retrieval lane.

RRF (Cormack, Clarke & Buettcher, 2009) merges ranked lists without needing
calibrated scores. The agentic-search study weights the lexical lane higher than
the semantic lane under inline delivery; the defaults here (lexical 0.65,
semantic 0.35, k=60) reflect that finding.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

DEFAULT_K = 60
DEFAULT_LEXICAL_WEIGHT = 0.65
DEFAULT_SEMANTIC_WEIGHT = 0.35
RANK_PRECISION = 12


@dataclass(frozen=True)
class ScoredChunk:
    """A retrieved chunk with its lane score.

    Attributes:
        id: Stable identifier (document/window index).
        score: The lane-native score (BM25 or cosine); used only for ordering.
    """

    id: int
    score: float = 0.0


@dataclass(frozen=True)
class FusedChunk:
    """A chunk after RRF fusion.

    Attributes:
        id: Stable identifier.
        fused_score: Weighted RRF score (higher is better).
        lexical_rank: 0-based rank in the lexical lane (-1 if absent).
        semantic_rank: 0-based rank in the semantic lane (-1 if absent).
    """

    id: int
    fused_score: float
    lexical_rank: int = -1
    semantic_rank: int = -1


def _dedupe_first_occurrence(results: list[ScoredChunk]) -> list[ScoredChunk]:
    """Return ``results`` with only the first occurrence of each id, order preserved.

    A retrieval lane is a ranked list, so an id should appear once; if a lane ever
    emits a duplicate, keeping the first occurrence preserves the reported rank and
    prevents double-counting in RRF scoring.
    """
    seen: set[int] = set()
    deduped: list[ScoredChunk] = []
    for chunk in results:
        if chunk.id in seen:
            continue
        seen.add(chunk.id)
        deduped.append(chunk)
    return deduped


def rrf_fuse(
    lexical_results: list[ScoredChunk],
    semantic_results: list[ScoredChunk],
    k: int = DEFAULT_K,
    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
) -> list[FusedChunk]:
    """Fuse two ranked lists into one via weighted RRF.

    The contribution of a chunk at 0-based rank ``r`` in a lane of weight ``w`` is
    ``w / (k + r + 1)``. Contributions across lanes are summed.

    Args:
        lexical_results: Lexical lane chunks in rank order (best first).
        semantic_results: Semantic lane chunks in rank order (best first).
        k: RRF damping constant (default 60).
        lexical_weight: Weight for the lexical lane (default 0.65).
        semantic_weight: Weight for the semantic lane (default 0.35).

    Returns:
        Fused chunks sorted by descending fused score; ties break on ascending id.

    Raises:
        ValueError: If ``k`` is negative or either weight is negative.
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    if lexical_weight < 0 or semantic_weight < 0:
        raise ValueError("lane weights must be non-negative")

    # A lane is a ranked list; each id may appear at most once. Collapse any
    # duplicate id to its first (best) occurrence BEFORE scoring so a repeated id
    # contributes to the fused score exactly once, consistent with the single rank
    # reported for it. Without this, a duplicate would add a second contribution at
    # its later rank while ``lex_rank``/``sem_rank`` still report the first rank.
    lexical_results = _dedupe_first_occurrence(lexical_results)
    semantic_results = _dedupe_first_occurrence(semantic_results)

    scores: dict[int, float] = defaultdict(float)
    lex_rank: dict[int, int] = {}
    sem_rank: dict[int, int] = {}

    for rank, chunk in enumerate(lexical_results):
        scores[chunk.id] += lexical_weight / (k + rank + 1)
        lex_rank.setdefault(chunk.id, rank)
    for rank, chunk in enumerate(semantic_results):
        scores[chunk.id] += semantic_weight / (k + rank + 1)
        sem_rank.setdefault(chunk.id, rank)

    fused = [
        FusedChunk(
            id=chunk_id,
            fused_score=score,
            lexical_rank=lex_rank.get(chunk_id, -1),
            semantic_rank=sem_rank.get(chunk_id, -1),
        )
        for chunk_id, score in scores.items()
    ]
    # Round only the ordering key: the reported score remains the exact summed
    # float, while sub-1e-12 platform noise cannot change a tie's id ordering.
    fused.sort(key=lambda c: (-round(c.fused_score, RANK_PRECISION), c.id))
    return fused


__all__ = [
    "ScoredChunk",
    "FusedChunk",
    "rrf_fuse",
    "DEFAULT_K",
    "DEFAULT_LEXICAL_WEIGHT",
    "DEFAULT_SEMANTIC_WEIGHT",
    "RANK_PRECISION",
]
