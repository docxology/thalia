"""Tests for lexical retrieval: BM25, grep, key-phrase extraction (Zero-Mock)."""

import re

import pytest
from src.retrieval.lexical import BM25Index, extract_key_phrases, grep

DOCS = [
    "the wifi password is bluefish42",
    "the guest network name is homenet",
    "my email password is hunter2",
    "the cat sat on the mat",
]


class TestBM25Init:
    def test_empty_documents_raises(self):
        with pytest.raises(ValueError, match="at least one document"):
            BM25Index([])

    def test_negative_k1_raises(self):
        with pytest.raises(ValueError, match="k1 must be non-negative"):
            BM25Index(DOCS, k1=-1.0)

    def test_b_out_of_range_raises(self):
        with pytest.raises(ValueError, match="b must be in"):
            BM25Index(DOCS, b=1.5)

    def test_avgdl_computed(self):
        idx = BM25Index(DOCS)
        assert idx.avgdl > 0


class TestBM25Score:
    def test_relevant_doc_scores_highest(self):
        idx = BM25Index(DOCS)
        scores = idx.score("wifi password")
        assert scores[0] == max(scores)

    def test_unmatched_query_all_zero(self):
        idx = BM25Index(DOCS)
        assert idx.score("zzzz nonexistent") == [0.0, 0.0, 0.0, 0.0]


class TestBM25TopK:
    def test_top_k_orders_descending(self):
        idx = BM25Index(DOCS)
        result = idx.top_k("password", k=3)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_zero_score_docs_excluded(self):
        idx = BM25Index(DOCS)
        result = idx.top_k("wifi", k=10)
        # Only the wifi doc matches; others excluded.
        assert [i for i, _ in result] == [0]

    def test_k_non_positive_raises(self):
        idx = BM25Index(DOCS)
        with pytest.raises(ValueError, match="k must be positive"):
            idx.top_k("x", k=0)

    def test_ties_break_on_index(self):
        # Two identical docs -> equal scores -> ascending index order.
        idx = BM25Index(["alpha beta", "alpha beta", "gamma"])
        result = idx.top_k("alpha", k=2)
        assert [i for i, _ in result] == [0, 1]


class TestExtractKeyPhrases:
    def test_removes_stopwords(self):
        phrases = extract_key_phrases("what is the wifi password")
        assert "the" not in phrases and "is" not in phrases
        assert "wifi" in phrases and "password" in phrases

    def test_dedupes_preserving_order(self):
        assert extract_key_phrases("alpha alpha beta") == ["alpha", "beta"]

    def test_caps_at_max_phrases(self):
        phrases = extract_key_phrases("one two three four five", max_phrases=2)
        assert len(phrases) == 2

    def test_drops_single_char_tokens(self):
        assert "x" not in extract_key_phrases("x marks the spot")


class TestGrep:
    def test_matches_any_pattern(self):
        assert grep(DOCS, ["wifi", "email"]) == [0, 2]

    def test_empty_patterns_returns_empty(self):
        assert grep(DOCS, []) == []
        assert grep(DOCS, [""]) == []

    def test_case_insensitive_default(self):
        assert grep(["WiFi here"], ["wifi"]) == [0]

    def test_case_sensitive(self):
        assert grep(["WiFi here"], ["wifi"], ignore_case=False) == []

    def test_dedupes_indices(self):
        # Both patterns match doc 0; result has it once.
        assert grep(["wifi password"], ["wifi", "password"]) == [0]

    def test_invalid_regex_raises(self):
        with pytest.raises(re.error):
            grep(DOCS, ["[unclosed"])
