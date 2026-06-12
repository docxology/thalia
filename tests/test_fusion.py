"""Tests for weighted Reciprocal Rank Fusion (Zero-Mock)."""

import pytest
from src.retrieval.fusion import (
    DEFAULT_K,
    DEFAULT_LEXICAL_WEIGHT,
    DEFAULT_SEMANTIC_WEIGHT,
    FusedChunk,
    ScoredChunk,
    rrf_fuse,
)


def _ids(chunks):
    return [c.id for c in chunks]


class TestRRFValidation:
    def test_negative_k_raises(self):
        with pytest.raises(ValueError, match="k must be non-negative"):
            rrf_fuse([], [], k=-1)

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="weights must be non-negative"):
            rrf_fuse([], [], lexical_weight=-0.1)


class TestRRFFusion:
    def test_empty_inputs(self):
        assert rrf_fuse([], []) == []

    def test_single_lane_ordering_preserved(self):
        lex = [ScoredChunk(5), ScoredChunk(2), ScoredChunk(9)]
        fused = rrf_fuse(lex, [])
        assert _ids(fused) == [5, 2, 9]

    def test_ranks_recorded(self):
        lex = [ScoredChunk(1), ScoredChunk(2)]
        sem = [ScoredChunk(2), ScoredChunk(3)]
        fused = {c.id: c for c in rrf_fuse(lex, sem)}
        assert fused[1].lexical_rank == 0 and fused[1].semantic_rank == -1
        assert fused[2].lexical_rank == 1 and fused[2].semantic_rank == 0
        assert fused[3].lexical_rank == -1 and fused[3].semantic_rank == 1

    def test_agreement_boosts_score(self):
        # A chunk top-ranked in both lanes beats chunks in only one.
        lex = [ScoredChunk(1), ScoredChunk(2)]
        sem = [ScoredChunk(1), ScoredChunk(3)]
        fused = rrf_fuse(lex, sem)
        assert fused[0].id == 1

    def test_weights_change_winner(self):
        lex = [ScoredChunk(10)]  # only lexical
        sem = [ScoredChunk(20)]  # only semantic
        lex_heavy = rrf_fuse(lex, sem, lexical_weight=0.9, semantic_weight=0.1)
        sem_heavy = rrf_fuse(lex, sem, lexical_weight=0.1, semantic_weight=0.9)
        assert lex_heavy[0].id == 10
        assert sem_heavy[0].id == 20

    def test_score_formula(self):
        fused = rrf_fuse([ScoredChunk(7)], [], k=60, lexical_weight=0.65)
        assert abs(fused[0].fused_score - 0.65 / 61) < 1e-12

    def test_ties_break_on_id(self):
        # Symmetric single-element lanes with equal weights -> tie -> id order.
        fused = rrf_fuse([ScoredChunk(3)], [ScoredChunk(1)], lexical_weight=0.5, semantic_weight=0.5)
        assert _ids(fused) == [1, 3]


class TestDataclasses:
    def test_scored_chunk_default_score(self):
        assert ScoredChunk(1).score == 0.0

    def test_fused_chunk_defaults(self):
        c = FusedChunk(id=1, fused_score=0.5)
        assert c.lexical_rank == -1 and c.semantic_rank == -1

    def test_defaults_exported(self):
        assert DEFAULT_K == 60
        assert DEFAULT_LEXICAL_WEIGHT + DEFAULT_SEMANTIC_WEIGHT == 1.0
