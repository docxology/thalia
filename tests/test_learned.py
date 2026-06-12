"""Tests for the optional learned-embedding semantic lane (Zero-Mock).

The deterministic surrogate side and the pure probe set are tested unconditionally;
the real Ollama embedder is exercised when a model is live and skipped otherwise.
Nothing is mocked.
"""

import pytest

from src.retrieval.learned import (
    DEFAULT_DOCUMENT_PREFIX,
    DEFAULT_EMBED_MODEL,
    DEFAULT_QUERY_PREFIX,
    PARAPHRASE_PROBES,
    embed_model_available,
    model_metadata_from_tags,
    surrogate_recall_at_1,
)


class TestSurrogateAndProbes:
    def test_probes_are_well_formed(self):
        assert len(PARAPHRASE_PROBES) >= 3
        for query, docs, gold in PARAPHRASE_PROBES:
            assert isinstance(query, str) and query
            assert len(docs) >= 2 and 0 <= gold < len(docs)

    def test_surrogate_recall_is_a_fraction(self):
        # The hashing surrogate cannot bridge true paraphrases, so it should miss
        # most probes — a real, deterministic measurement (no mock).
        recall = surrogate_recall_at_1()
        assert 0.0 <= recall <= 1.0
        assert recall < 1.0  # the surrogate is morphological, not semantic

    def test_embed_model_probe_returns_bool(self):
        assert isinstance(embed_model_available(api_base="http://localhost:1"), bool)

    def test_model_metadata_from_tags_matches_bare_model_to_latest(self):
        tags = {
            "models": [
                {"name": "nomic-embed-text:latest", "digest": "abc123", "size": 42, "details": {"family": "nomic"}},
            ]
        }
        metadata = model_metadata_from_tags(tags, "nomic-embed-text")
        assert metadata["available"] is True
        assert metadata["model"] == "nomic-embed-text:latest"
        assert metadata["digest"] == "abc123"

    def test_model_metadata_missing_is_explicit(self):
        metadata = model_metadata_from_tags({"models": []}, "nomic-embed-text")
        assert metadata["available"] is False
        assert metadata["digest"] is None

    def test_default_embedding_prefixes_are_nomic_search_tasks(self):
        assert DEFAULT_DOCUMENT_PREFIX == "search_document: "
        assert DEFAULT_QUERY_PREFIX == "search_query: "


@pytest.mark.skipif(
    not embed_model_available(),
    reason=f"needs a live Ollama serving {DEFAULT_EMBED_MODEL}",
)
class TestRealLearnedEmbedder:
    """Exercises a real neural embedder; the learned lane must beat the surrogate."""

    def test_learned_embedder_beats_surrogate_on_paraphrases(self):
        from src.retrieval.learned import learned_recall_at_1, surrogate_recall_at_1

        assert learned_recall_at_1() > surrogate_recall_at_1()

    def test_learned_index_ranks_paraphrase_gold_first(self):
        from src.retrieval.learned import LearnedSemanticIndex

        query, docs, gold = PARAPHRASE_PROBES[0]
        top = LearnedSemanticIndex(docs).top_k(query, k=1)
        assert top and top[0][0] == gold

    def test_learned_index_records_prefixes(self):
        from src.retrieval.learned import LearnedSemanticIndex

        _query, docs, _gold = PARAPHRASE_PROBES[0]
        index = LearnedSemanticIndex(docs)
        assert index.document_prefix == DEFAULT_DOCUMENT_PREFIX
        assert index.query_prefix == DEFAULT_QUERY_PREFIX

    def test_dense_rag_baseline_recovers_a_fact(self):
        from src.retrieval.learned import dense_rag_answer

        session = "User: the cat is grey.\nUser: the wifi password is bluefish42.\nUser: lunch is at noon."
        assert "bluefish42" in dense_rag_answer(session, "What is the wifi password?").lower()
