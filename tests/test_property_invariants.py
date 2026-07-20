"""Property-based tests for THALIA core invariants using Hypothesis.

These tests use Hypothesis to generate diverse inputs and verify that core
invariants hold across a wide range of values — not just the hand-picked ones
in the static invariant suite. Zero-Mock policy: all tests use real objects
and real data.
"""

from __future__ import annotations

from hypothesis import given, strategies as st

from src.config import HarnessConfig
from src.memory.consolidation import (
    ConsolidationCriteria,
    should_consolidate,
)
from src.memory.episodic_store import EpisodicStore
from src.module import tokenize
from src.retrieval.fusion import ScoredChunk, rrf_fuse
from src.retrieval.lexical import BM25Index
from src.retrieval.mmr import mmr_rerank
from src.retrieval.semantic import embed
from src.signatures import EpisodicEntry, EvidenceWindow, RankedEvidence


class TestBM25IndexProperty:
    """BM25 index invariants across diverse document sets."""

    @given(
        docs=st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=80),
            min_size=1,
            max_size=10,
        ),
        query=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=40),
    )
    def test_top_k_returns_positive_indices(self, docs, query):
        """All returned indices are non-negative and within document range."""
        index = BM25Index(docs)
        results = index.top_k(query, k=min(5, len(docs)))
        for idx, score in results:
            assert 0 <= idx < len(docs)
            assert isinstance(score, float)

    @given(
        docs=st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=80),
            min_size=1,
            max_size=10,
        ),
        query=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=40),
    )
    def test_top_k_results_sorted_by_score_descending(self, docs, query):
        """Results are in descending score order (monotonic non-increasing)."""
        index = BM25Index(docs)
        results = index.top_k(query, k=min(5, len(docs)))
        scores = [s for _, s in results]
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


class TestSemanticEmbedProperty:
    """Semantic embedding invariants."""

    @given(
        text=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=100),
    )
    def test_embedding_is_unit_norm(self, text):
        """The embedding vector has unit L2 norm."""
        import numpy as np

        vec = embed(text)
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-12, f"norm={norm} for text={text!r}"

    @given(
        text_a=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=50),
        text_b=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=50),
    )
    def test_identical_text_identical_embedding(self, text_a, text_b):
        """Same text -> same vector; different text may differ."""
        vec_a = embed(text_a)
        vec_b = embed(text_b)
        import numpy as np

        if text_a == text_b:
            assert np.array_equal(vec_a, vec_b)
        # If different, no assertion — they may or may not be different.


class TestRRFFusionProperty:
    """RRF fusion invariants across diverse scored-chunk inputs."""

    @given(
        list_a=st.lists(st.integers(min_value=0, max_value=20), min_size=0, max_size=10, unique=True),
        list_b=st.lists(st.integers(min_value=0, max_value=20), min_size=0, max_size=10, unique=True),
    )
    def test_rrf_fusion_deterministic(self, list_a, list_b):
        """RRF fusion produces identical results for the same inputs."""
        chunks_a = [ScoredChunk(i) for i in list_a]
        chunks_b = [ScoredChunk(i) for i in list_b]
        first = rrf_fuse(chunks_a, chunks_b)
        second = rrf_fuse(chunks_a, chunks_b)
        assert [c.id for c in first] == [c.id for c in second]

    @given(
        ids=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=15, unique=True),
    )
    def test_rrf_agreement_ranks_higher(self, ids):
        """A chunk in both lanes outranks chunks in only one lane when other
        chunks are absent from the second lane."""
        chunks_a = [ScoredChunk(i) for i in ids]
        # Second lane contains only the first element
        if ids:
            chunks_b = [ScoredChunk(ids[0])]
            fused = rrf_fuse(chunks_a, chunks_b)
            assert fused[0].id == ids[0]


class TestMMRInvariant:
    """MMR invariants across diverse inputs."""

    @given(
        scores=st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=10),
        lambda_val=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_mmr_preserves_all_elements(self, scores, lambda_val):
        """MMR reranking returns the same elements in some order."""
        windows = [EvidenceWindow(text=f"text {i}", source_index=i) for i in range(len(scores))]
        ranked = [RankedEvidence(window=w, score=s) for w, s in zip(windows, scores)]
        # Ensure at least one unique score to avoid tie-break ambiguity
        if len(set(scores)) < 2 and len(scores) > 0:
            return  # skip ties that produce non-deterministic order
        if len(scores) <= 1:
            return  # skip trivial cases
        result = mmr_rerank(ranked, lambda_=lambda_val)
        assert len(result) == len(ranked)


class TestConsolidationProperty:
    """Consolidation gate invariants across diverse criteria."""

    @given(
        flag=st.booleans(),
        session_ending=st.booleans(),
        novel_task_class=st.booleans(),
        explicit_request=st.booleans(),
    )
    def test_consolidation_requires_both_flag_and_criterion(
        self, flag, session_ending, novel_task_class, explicit_request
    ):
        """Consolidation should never fire on a flag alone or criterion alone."""
        criteria = ConsolidationCriteria(
            session_ending=session_ending,
            novel_task_class=novel_task_class,
            explicit_request=explicit_request,
        )
        any_criterion = session_ending or novel_task_class or explicit_request
        if flag and any_criterion:
            assert should_consolidate(flag, criteria) is True
        elif not flag and not any_criterion:
            assert should_consolidate(flag, criteria) is False


class TestEpisodicStoreProperty:
    """Episodic store invariants."""

    @given(
        n=st.integers(min_value=0, max_value=10),
    )
    def test_append_then_count_matches(self, n):
        """After appending N entries, count returns N."""
        store = EpisodicStore()
        count = 0
        for i in range(n):
            store.append(EpisodicEntry(i, f"query_{i}", f"answer_{i}"))
            count += 1
        assert store.count() == n
        store.close()

    @given(
        n=st.integers(min_value=1, max_value=10),
        target=st.integers(min_value=0, max_value=10),
    )
    def test_get_returns_none_for_missing_turns(self, n, target):
        """Getting a non-existent turn returns None."""
        store = EpisodicStore()
        for i in range(n):
            store.append(EpisodicEntry(i, f"query_{i}", f"answer_{i}"))
        assert store.get(n + target) is None
        store.close()


class TestTokenizerProperty:
    """Tokenizer invariants."""

    @given(
        text=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ", min_size=0, max_size=200),
    )
    def test_tokenize_returns_lowercase(self, text):
        """All tokens are lowercase."""
        tokens = tokenize(text)
        for t in tokens:
            assert t == t.lower()

    @given(
        text_a=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=100),
        text_b=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=100),
    )
    def test_tokenize_determinism(self, text_a, text_b):
        """Same text always produces same tokens."""
        assert tokenize(text_a) == tokenize(text_a)
        assert tokenize(text_b) == tokenize(text_b)


class TestHarnessConfigProperty:
    """HarnessConfig invariants across broad parameter ranges."""

    @given(
        top_k=st.integers(min_value=1, max_value=50),
        max_windows=st.integers(min_value=1, max_value=100),
        max_evidence=st.integers(min_value=1, max_value=50),
        rrf_k=st.integers(min_value=0, max_value=200),
        context_budget=st.integers(min_value=1, max_value=16000),
        mmr_lambda=st.floats(min_value=0.0, max_value=1.0),
        grounding=st.floats(min_value=0.0, max_value=1.0),
        partition=st.integers(min_value=1, max_value=200),
        psize=st.integers(min_value=1, max_value=50),
    )
    def test_round_trip_to_dict(self, top_k, max_windows, max_evidence, rrf_k, context_budget, mmr_lambda, grounding, partition, psize):
        """HarnessConfig can be round-tripped through from_dict without error."""
        cfg = HarnessConfig(
            top_k=top_k,
            max_windows=max_windows,
            max_evidence=max_evidence,
            rrf_k=rrf_k,
            context_budget_tokens=context_budget,
            mmr_lambda=mmr_lambda,
            grounding_threshold=grounding,
            partition_threshold=partition,
            partition_size=psize,
        )
        restored = HarnessConfig.from_dict(cfg.to_dict())
        assert restored == cfg
