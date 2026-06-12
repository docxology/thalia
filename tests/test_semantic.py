"""Tests for the deterministic hashing-embedding semantic lane (Zero-Mock)."""

import numpy as np
import pytest
from src.retrieval.semantic import DEFAULT_DIM, SemanticIndex, cosine, embed

DOCS = [
    "the wifi password is bluefish42",
    "scheduling the dentist appointment",
    "a completely unrelated sentence about turtles",
]


class TestEmbed:
    def test_deterministic(self):
        assert np.array_equal(embed("hello world"), embed("hello world"))

    def test_unit_norm(self):
        v = embed("some text here")
        assert abs(np.linalg.norm(v) - 1.0) < 1e-9

    def test_empty_text_zero_vector(self):
        v = embed("")
        assert np.linalg.norm(v) == 0.0

    def test_dim_respected(self):
        assert embed("text", dim=64).shape == (64,)

    def test_dim_non_positive_raises(self):
        with pytest.raises(ValueError, match="dim must be positive"):
            embed("x", dim=0)

    def test_default_dim(self):
        assert embed("x").shape == (DEFAULT_DIM,)


class TestCosine:
    def test_identical_vectors_one(self):
        v = embed("hello")
        assert abs(cosine(v, v) - 1.0) < 1e-9

    def test_zero_vector_zero(self):
        assert cosine(embed(""), embed("hello")) == 0.0

    def test_morphological_overlap_scores_positive(self):
        # Shared sub-words give positive similarity.
        assert cosine(embed("scheduling"), embed("scheduled")) > 0.0


class TestSemanticIndex:
    def test_empty_documents_raises(self):
        with pytest.raises(ValueError, match="at least one document"):
            SemanticIndex([])

    def test_score_length_matches_corpus(self):
        idx = SemanticIndex(DOCS)
        assert len(idx.score("wifi password")) == len(DOCS)

    def test_top_k_orders_descending(self):
        idx = SemanticIndex(DOCS)
        result = idx.top_k("wifi password", k=3)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_relevant_doc_ranks_first(self):
        idx = SemanticIndex(DOCS)
        result = idx.top_k("wifi password bluefish", k=1)
        assert result[0][0] == 0

    def test_k_non_positive_raises(self):
        idx = SemanticIndex(DOCS)
        with pytest.raises(ValueError, match="k must be positive"):
            idx.top_k("x", k=-1)
