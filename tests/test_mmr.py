"""Tests for MMR diversity re-ranking (Zero-Mock)."""

import pytest
from src.retrieval.mmr import mmr_rerank
from src.signatures import EvidenceWindow, RankedEvidence


def _ranked(pairs):
    return [RankedEvidence(window=EvidenceWindow(text=t, source_index=i), score=s) for i, (t, s) in enumerate(pairs)]


class TestValidation:
    def test_lambda_out_of_range_raises(self):
        with pytest.raises(ValueError, match=r"lambda_ must be in \[0, 1\]"):
            mmr_rerank(_ranked([("a", 1.0), ("b", 0.5)]), lambda_=1.5)

    def test_non_positive_k_raises(self):
        with pytest.raises(ValueError, match="k must be positive"):
            mmr_rerank(_ranked([("a", 1.0), ("b", 0.5)]), k=0)


class TestBehaviour:
    def test_empty_returns_empty(self):
        assert mmr_rerank([]) == []

    def test_single_item_unchanged(self):
        ranked = _ranked([("only", 1.0)])
        assert mmr_rerank(ranked) == ranked

    def test_lambda_one_preserves_relevance_order(self):
        ranked = _ranked([("alpha one", 0.9), ("beta two", 0.6), ("gamma three", 0.3)])
        out = mmr_rerank(ranked, lambda_=1.0)
        assert [r.window.source_index for r in out] == [0, 1, 2]

    def test_k_limits_length(self):
        ranked = _ranked([("a x", 0.9), ("b y", 0.6), ("c z", 0.3)])
        assert len(mmr_rerank(ranked, k=2)) == 2

    def test_all_items_returned_when_no_k(self):
        ranked = _ranked([("a", 0.9), ("b", 0.6), ("c", 0.3)])
        out = mmr_rerank(ranked, lambda_=0.5)
        assert sorted(r.window.source_index for r in out) == [0, 1, 2]

    def test_diversity_demotes_near_duplicate(self):
        # Items 0 and 1 are near-identical; item 2 is distinct. With strong
        # diversity weighting, the distinct item should outrank the duplicate.
        ranked = _ranked(
            [
                ("the wifi password is alpha", 0.90),
                ("the wifi password is alpha", 0.89),
                ("the dentist appointment is tuesday", 0.50),
            ]
        )
        out = mmr_rerank(ranked, lambda_=0.2)
        order = [r.window.source_index for r in out]
        assert order[0] == 0
        assert order.index(2) < order.index(1)

    def test_deterministic(self):
        ranked = _ranked([("a x", 0.9), ("b y", 0.6), ("c z", 0.3)])
        assert mmr_rerank(ranked, lambda_=0.5) == mmr_rerank(ranked, lambda_=0.5)
