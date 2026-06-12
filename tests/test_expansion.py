"""Tests for pseudo-relevance-feedback query expansion (Zero-Mock)."""

import pytest
from src.module import tokenize
from src.retrieval.expansion import expand_query

DOCS = [
    "the wifi password is bluefish42 stored securely in the vault",
    "an unrelated note about migrating turtles",
]


class TestExpansion:
    def test_superset_of_original(self):
        expanded = expand_query("wifi password", DOCS)
        assert set(tokenize("wifi password")).issubset(set(tokenize(expanded)))

    def test_adds_feedback_terms(self):
        expanded = expand_query("wifi password", DOCS, top_terms=3)
        # A discriminative content term from the top doc is appended.
        assert "bluefish42" in expanded or "vault" in expanded or "stored" in expanded

    def test_empty_documents_returns_query(self):
        assert expand_query("wifi password", []) == "wifi password"

    def test_no_useful_terms_returns_query(self):
        # Doc shares only the query terms -> nothing new to add.
        assert expand_query("wifi password", ["wifi password"]) == "wifi password"

    def test_deterministic(self):
        assert expand_query("wifi password", DOCS) == expand_query("wifi password", DOCS)

    def test_top_docs_non_positive_raises(self):
        with pytest.raises(ValueError, match="top_docs must be positive"):
            expand_query("q", DOCS, top_docs=0)

    def test_top_terms_non_positive_raises(self):
        with pytest.raises(ValueError, match="top_terms must be positive"):
            expand_query("q", DOCS, top_terms=0)
