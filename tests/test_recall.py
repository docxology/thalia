"""Tests for memory recall (Zero-Mock, real SQLite store)."""

import pytest
from src.memory.episodic_store import EpisodicStore
from src.recall import recall_evidence
from src.signatures import EpisodicEntry


def _store(*pairs):
    store = EpisodicStore()
    for i, (q, a) in enumerate(pairs):
        store.append(EpisodicEntry(i, q, a))
    return store


class TestRecall:
    def test_recalls_matching_episode(self):
        store = _store(("where do I live", "I live in Lisbon"), ("what is for lunch", "tacos"))
        windows = recall_evidence(store, "", "where do I live", limit=3)
        assert any("Lisbon" in w.text for w in windows)
        store.close()

    def test_recalled_indices_are_negative(self):
        store = _store(("where do I live", "Lisbon"))
        windows = recall_evidence(store, "", "where do I live")
        assert all(w.source_index < 0 for w in windows)
        store.close()

    def test_recalls_memory_md_lines(self):
        store = EpisodicStore()
        memory = "# MEMORY\n\n## Consolidated\n- the door code is 4321\n- unrelated fact"
        windows = recall_evidence(store, memory, "what is the door code")
        assert any("4321" in w.text for w in windows)
        # Heading lines are skipped.
        assert not any(w.text.startswith("#") for w in windows)
        store.close()

    def test_empty_returns_empty(self):
        store = EpisodicStore()
        assert recall_evidence(store, "", "anything") == []
        store.close()

    def test_read_only(self):
        store = _store(("q", "a"))
        before = store.count()
        recall_evidence(store, "", "q")
        assert store.count() == before
        store.close()

    def test_limit_non_positive_raises(self):
        store = EpisodicStore()
        with pytest.raises(ValueError, match="limit must be positive"):
            recall_evidence(store, "", "q", limit=0)
        store.close()
