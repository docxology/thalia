"""Tests for the append-only SQLite episodic store (Zero-Mock, real SQLite)."""

import pytest
from src.memory.episodic_store import EpisodicStore, _fts_match_expression, _search_terms
from src.signatures import EpisodicEntry


def _entry(turn_id, query="q", answer="a", indices=()):
    return EpisodicEntry(turn_id=turn_id, query=query, answer=answer, evidence_indices=indices)


class TestSchema:
    def test_starts_empty(self):
        store = EpisodicStore()
        assert store.count() == 0

    def test_fts_probe_runs(self):
        store = EpisodicStore()
        assert isinstance(store.fts_available, bool)


class TestAppend:
    def test_append_increments_count(self):
        store = EpisodicStore()
        store.append(_entry(0))
        store.append(_entry(1))
        assert store.count() == 2

    def test_duplicate_turn_id_raises(self):
        store = EpisodicStore()
        store.append(_entry(0))
        with pytest.raises(ValueError, match="append-only"):
            store.append(_entry(0))

    def test_indices_roundtrip(self):
        store = EpisodicStore()
        store.append(_entry(0, indices=(3, 7, 9)))
        assert store.get(0).evidence_indices == (3, 7, 9)

    def test_empty_indices_roundtrip(self):
        store = EpisodicStore()
        store.append(_entry(0, indices=()))
        assert store.get(0).evidence_indices == ()


class TestRetrieval:
    def test_get_present(self):
        store = EpisodicStore()
        store.append(_entry(5, query="hello"))
        assert store.get(5).query == "hello"

    def test_get_absent_returns_none(self):
        assert EpisodicStore().get(99) is None

    def test_all_ordered_by_turn_id(self):
        store = EpisodicStore()
        store.append(_entry(2))
        store.append(_entry(0))
        store.append(_entry(1))
        assert [e.turn_id for e in store.all()] == [0, 1, 2]


class TestSearch:
    def test_search_terms_strip_fts_syntax(self):
        assert _search_terms('What is the wifi-password? "bluefish42"') == ["what", "is", "the", "wifi", "password", "bluefish42"]

    def test_fts_match_expression_preserves_or_semantics(self):
        assert _fts_match_expression("wifi password?") == "wifi OR password"
        assert _fts_match_expression("wifi password?", operator="AND") == "wifi AND password"

    def test_fts_match_expression_rejects_bad_operator(self):
        with pytest.raises(ValueError, match="operator must be"):
            _fts_match_expression("wifi", operator="NEAR")

    def test_finds_matching_episode(self):
        store = EpisodicStore()
        store.append(_entry(0, query="the wifi password", answer="bluefish42"))
        store.append(_entry(1, query="the cat", answer="meow"))
        results = store.search("wifi")
        assert any("wifi" in e.query for e in results)

    def test_search_matches_answer_text(self):
        store = EpisodicStore()
        store.append(_entry(0, query="q", answer="bluefish42"))
        assert store.search("bluefish42")

    def test_empty_query_returns_empty(self):
        store = EpisodicStore()
        store.append(_entry(0))
        assert store.search("   ") == []

    def test_no_match_returns_empty(self):
        store = EpisodicStore()
        store.append(_entry(0, query="alpha", answer="beta"))
        assert store.search("nonexistentterm") == []

    def test_punctuated_natural_language_query_does_not_crash(self):
        # Regression: a raw query with FTS5 special characters (".", "?", "-", '"')
        # previously raised `fts5: syntax error`. It must now sanitise to bare tokens
        # and still match.
        store = EpisodicStore()
        store.append(_entry(0, query="note", answer="my wifi password is bluefish42."))
        for query in ('What is the wifi-password?', 'wifi "password".', 'a.b.c wifi'):
            results = store.search(query)
            assert any("bluefish42" in e.answer for e in results)

    def test_limit_non_positive_raises(self):
        store = EpisodicStore()
        with pytest.raises(ValueError, match="limit must be positive"):
            store.search("x", limit=0)

    def test_limit_respected(self):
        store = EpisodicStore()
        for i in range(5):
            store.append(_entry(i, query=f"shared token doc {i}"))
        assert len(store.search("shared", limit=2)) <= 2


class TestLikeFallback:
    """Exercise the non-FTS5 LIKE search path deterministically.

    Toggling ``fts_available`` is not a mock — it selects the real fallback code
    path the store uses on SQLite builds without the FTS5 extension.
    """

    def test_like_search_finds_match(self):
        store = EpisodicStore()
        store.fts_available = False
        store.append(_entry(0, query="the wifi password", answer="bluefish42"))
        store.append(_entry(1, query="unrelated", answer="text"))
        results = store.search("wifi")
        assert any("wifi" in e.query for e in results)

    def test_like_search_limit(self):
        store = EpisodicStore()
        store.fts_available = False
        for i in range(4):
            store.append(_entry(i, query=f"shared token {i}"))
        assert len(store.search("shared", limit=2)) == 2

    def test_like_search_no_match(self):
        store = EpisodicStore()
        store.fts_available = False
        store.append(_entry(0, query="alpha", answer="beta"))
        assert store.search("zzz") == []


class TestClose:
    def test_close_does_not_raise(self):
        store = EpisodicStore()
        store.close()


class TestFts5Unavailable:
    """Exercise the _fts5_available False path (lines 24-25).

    ``monkeypatch`` swaps out the module-level helper so that an
    ``EpisodicStore`` constructed in this test believes FTS5 is absent.
    The store must initialise without the FTS virtual table and fall back
    to LIKE-scan search correctly.
    """

    def test_fts5_available_false_path(self, monkeypatch):
        import src.memory.episodic_store as es_mod

        monkeypatch.setattr(es_mod, "_fts5_available", lambda _conn: False)

        store = EpisodicStore()
        assert store.fts_available is False
        # Schema init must complete without error even without the FTS table.
        assert store.count() == 0

    def test_store_searches_with_like_when_fts5_unavailable(self, monkeypatch):
        import src.memory.episodic_store as es_mod

        monkeypatch.setattr(es_mod, "_fts5_available", lambda _conn: False)

        store = EpisodicStore()
        store.append(_entry(0, query="the door code", answer="4321"))
        store.append(_entry(1, query="unrelated", answer="nothing"))

        results = store.search("door")
        assert any("door" in e.query for e in results)
        store.close()
