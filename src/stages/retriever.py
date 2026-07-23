"""Stage 1 — Retriever: lexical-first hybrid retrieval with RRF fusion.

Implements the agentic-search design principles (Sen et al., 2026): a lexical
(BM25) lane runs as the primary witness for literal cues, a semantic lane covers
paraphrases, and the two ranked lists are merged by weighted Reciprocal Rank
Fusion. Sparse context budgeting picks ``INLINE`` delivery when the selected
evidence fits the token budget and ``FILE_BASED`` overflow otherwise.
"""

from __future__ import annotations

from dataclasses import replace

from ..module import Module, Prediction, tokenize
from ..retrieval.expansion import expand_query
from ..retrieval.fusion import (
    DEFAULT_K,
    DEFAULT_LEXICAL_WEIGHT,
    DEFAULT_SEMANTIC_WEIGHT,
    ScoredChunk,
    rrf_fuse,
)
from ..retrieval.lexical import BM25Index
from ..retrieval.mmr import mmr_rerank
from ..retrieval.semantic import SemanticIndex
from ..signatures import (
    DeliveryMode,
    EvidenceWindow,
    RankedEvidence,
    RetrieverSignature,
    TaskCategory,
)

DEFAULT_TOP_K = 8
DEFAULT_CONTEXT_BUDGET_TOKENS = 2048

# Harness-conditioned lane weighting. Temporal / single-session questions reward
# literal lexical matches; preference / knowledge-update questions lean slightly
# more on paraphrase-tolerant semantic matching. Weights still favour lexical
# overall, matching the inline-delivery finding.
_CATEGORY_WEIGHTS: dict[TaskCategory, tuple[float, float]] = {
    TaskCategory.TEMPORAL: (0.75, 0.25),
    TaskCategory.SINGLE_SESSION: (0.70, 0.30),
    TaskCategory.MULTI_SESSION: (0.65, 0.35),
    TaskCategory.CODE: (0.70, 0.30),
    TaskCategory.PREFERENCE: (0.55, 0.45),
    TaskCategory.KNOWLEDGE_UPDATE: (0.55, 0.45),
}


def estimate_tokens(texts: list[str]) -> int:
    """Estimate the token footprint of ``texts`` (whitespace token proxy)."""
    return sum(len(tokenize(t)) for t in texts)


class Retriever(Module):
    """Stage 1 — rank Inspector windows into a budgeted, fused evidence list."""

    signature = RetrieverSignature

    def __init__(
        self,
        top_k: int = DEFAULT_TOP_K,
        k: int = DEFAULT_K,
        lexical_weight: float | None = None,
        semantic_weight: float | None = None,
        rerank: str = "rrf",
        mmr_lambda: float = 0.7,
        query_expansion: bool = False,
        expansion_terms: int = 5,
        recency_weight: float = 0.0,
    ) -> None:
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")
        if k < 0:
            raise ValueError(f"k must be non-negative, got {k}")
        if (lexical_weight is None) ^ (semantic_weight is None):
            raise ValueError("lexical_weight and semantic_weight must both be set or both None")
        if lexical_weight is not None and semantic_weight is not None and (lexical_weight < 0 or semantic_weight < 0):
            raise ValueError("lane weights must be non-negative")
        if lexical_weight == 0 and semantic_weight == 0:
            raise ValueError("at least one lane weight must be positive")
        if rerank not in ("rrf", "mmr"):
            raise ValueError(f"rerank must be 'rrf' or 'mmr', got {rerank!r}")
        if not 0.0 <= mmr_lambda <= 1.0:
            raise ValueError(f"mmr_lambda must be in [0, 1], got {mmr_lambda}")
        if expansion_terms <= 0:
            raise ValueError(f"expansion_terms must be positive, got {expansion_terms}")
        if not 0.0 <= recency_weight <= 1.0:
            raise ValueError(f"recency_weight must be in [0, 1], got {recency_weight}")
        self.top_k = top_k
        self.k = k
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight
        self.rerank = rerank
        self.mmr_lambda = mmr_lambda
        self.query_expansion = query_expansion
        self.expansion_terms = expansion_terms
        self.recency_weight = recency_weight

    def _apply_recency(self, ranked: list[RankedEvidence]) -> list[RankedEvidence]:
        """Add a recency bonus favouring later session turns, then re-sort.

        The bonus is scaled by the top fused score so it is commensurate with RRF
        magnitudes. Only non-negative (session) source indices receive it; recalled
        windows (negative indices) are left unchanged.
        """
        if self.recency_weight <= 0 or not ranked:
            return ranked
        positions = [r.window.source_index for r in ranked if r.window.source_index >= 0]
        max_idx = max(positions) if positions else 0
        if max_idx <= 0:
            return ranked
        max_score = max((r.score for r in ranked), default=0.0)
        adjusted = [
            replace(
                r,
                score=round(
                    r.score
                    + (
                        self.recency_weight * max_score * (r.window.source_index / max_idx)
                        if r.window.source_index >= 0
                        else 0.0
                    ),
                    8,
                ),
            )
            for r in ranked
        ]
        adjusted.sort(key=lambda r: (-r.score, r.window.source_index))
        return adjusted

    def _weights(self, task_category: TaskCategory) -> tuple[float, float]:
        """Resolve lane weights (explicit override beats category default)."""
        if self.lexical_weight is not None and self.semantic_weight is not None:
            return self.lexical_weight, self.semantic_weight
        return _CATEGORY_WEIGHTS.get(task_category, (DEFAULT_LEXICAL_WEIGHT, DEFAULT_SEMANTIC_WEIGHT))

    def forward(  # type: ignore[override]
        self,
        evidence_windows: list[EvidenceWindow],
        query: str,
        task_category: TaskCategory = TaskCategory.SINGLE_SESSION,
        context_budget_tokens: int = DEFAULT_CONTEXT_BUDGET_TOKENS,
    ) -> Prediction:
        """Rank and budget evidence windows for ``query``.

        Args:
            evidence_windows: Windows emitted by the Inspector.
            query: The current question.
            task_category: Detected task category (selects lane weights).
            context_budget_tokens: Inline token budget.

        Returns:
            A :class:`Prediction` with ``ranked_evidence`` (list[RankedEvidence])
            and ``delivery_mode`` (DeliveryMode).
        """
        self.signature.validate_inputs(
            evidence_windows=evidence_windows,
            query=query,
            task_category=task_category,
            context_budget_tokens=context_budget_tokens,
        )
        if not evidence_windows:
            return Prediction({"ranked_evidence": [], "delivery_mode": DeliveryMode.INLINE})

        texts = [w.text for w in evidence_windows]

        # Pseudo-relevance feedback: expand the query from its own top windows.
        if self.query_expansion:
            query = expand_query(query, texts, top_terms=self.expansion_terms)

        bm25 = BM25Index(texts)
        semantic = SemanticIndex(texts)

        lexical = [ScoredChunk(idx, score) for idx, score in bm25.top_k(query, len(texts))]
        dense = [ScoredChunk(idx, score) for idx, score in semantic.top_k(query, len(texts))]
        lex_w, sem_w = self._weights(task_category)
        fused = rrf_fuse(lexical, dense, k=self.k, lexical_weight=lex_w, semantic_weight=sem_w)

        all_ranked = [
            RankedEvidence(
                window=evidence_windows[chunk.id],
                score=round(chunk.fused_score, 8),
                lexical_rank=chunk.lexical_rank,
                semantic_rank=chunk.semantic_rank,
            )
            for chunk in fused
        ]

        # Recency bonus (favours later turns) before selection.
        all_ranked = self._apply_recency(all_ranked)

        # Select top_k: either fusion order, or MMR diversity re-ranking over the
        # full fused pool (so diversity is chosen from all candidates, not a slice).
        if self.rerank == "mmr":
            ranked = mmr_rerank(all_ranked, lambda_=self.mmr_lambda, k=self.top_k)
        else:
            ranked = all_ranked[: self.top_k]

        budget_used = estimate_tokens([r.window.text for r in ranked])
        delivery = DeliveryMode.INLINE if budget_used <= context_budget_tokens else DeliveryMode.FILE_BASED
        return Prediction({"ranked_evidence": ranked, "delivery_mode": delivery})


__all__ = ["Retriever", "estimate_tokens", "DEFAULT_TOP_K", "DEFAULT_CONTEXT_BUDGET_TOKENS"]
