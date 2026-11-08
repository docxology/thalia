"""Tests for Stage 1 — the lexical-first hybrid Retriever (Zero-Mock)."""

import cProfile

import pytest
from src.retrieval.expansion import expand_query
from src.retrieval.lexical import BM25Index
from src.retrieval.mmr import mmr_rerank
from src.retrieval.semantic import SemanticIndex
from src.signatures import DeliveryMode, EvidenceWindow, RankedEvidence, TaskCategory
from src.stages.retriever import Retriever, estimate_tokens


def _windows(texts):
    return [EvidenceWindow(text=t, source_index=i) for i, t in enumerate(texts)]


WINDOWS = _windows(
    [
        "the wifi password is bluefish42",
        "the guest network is homenet",
        "my email password is hunter2",
        "the cat sat on the mat",
    ]
)


class TestEstimateTokens:
    def test_counts_tokens(self):
        assert estimate_tokens(["a b c", "d e"]) == 5

    def test_counts_shared_alphanumeric_tokens(self):
        assert estimate_tokens(["Wi-Fi password: bluefish42."]) == 4

    def test_empty(self):
        assert estimate_tokens([]) == 0


class TestRetrieverInit:
    def test_non_positive_top_k_raises(self):
        with pytest.raises(ValueError, match="top_k must be positive"):
            Retriever(top_k=0)

    def test_negative_rrf_k_raises(self):
        with pytest.raises(ValueError, match="k must be non-negative"):
            Retriever(k=-1)

    def test_one_weight_set_raises(self):
        with pytest.raises(ValueError, match="both be set or both None"):
            Retriever(lexical_weight=0.8)

    def test_zero_lane_weights_rejected(self):
        with pytest.raises(ValueError, match="at least one lane weight"):
            Retriever(lexical_weight=0.0, semantic_weight=0.0)

    def test_mmr_lambda_range(self):
        with pytest.raises(ValueError, match="mmr_lambda must be in"):
            Retriever(mmr_lambda=1.5)


class TestWeights:
    def test_explicit_override(self):
        r = Retriever(lexical_weight=0.9, semantic_weight=0.1)
        assert r._weights(TaskCategory.PREFERENCE) == (0.9, 0.1)

    def test_category_default(self):
        r = Retriever()
        assert r._weights(TaskCategory.TEMPORAL) == (0.75, 0.25)

    def test_unknown_category_uses_module_default(self):
        r = Retriever()
        # Any category not in the table falls back to the RRF defaults.
        weights = r._weights(TaskCategory.SINGLE_SESSION)
        assert isinstance(weights, tuple) and len(weights) == 2


class TestRetrieverForward:
    def test_empty_windows_returns_inline_empty(self):
        r = Retriever()
        pred = r(evidence_windows=[], query="x", task_category=TaskCategory.CODE)
        assert pred["ranked_evidence"] == []
        assert pred["delivery_mode"] is DeliveryMode.INLINE

    def test_ranks_relevant_window_first(self):
        r = Retriever()
        pred = r(
            evidence_windows=WINDOWS,
            query="wifi password",
            task_category=TaskCategory.SINGLE_SESSION,
        )
        ranked = pred["ranked_evidence"]
        assert ranked[0].window.source_index == 0

    def test_top_k_limits_results(self):
        r = Retriever(top_k=2)
        pred = r(
            evidence_windows=WINDOWS,
            query="password",
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert len(pred["ranked_evidence"]) <= 2

    def test_inline_when_within_budget(self):
        r = Retriever()
        pred = r(
            evidence_windows=WINDOWS,
            query="wifi password",
            task_category=TaskCategory.SINGLE_SESSION,
            context_budget_tokens=1000,
        )
        assert pred["delivery_mode"] is DeliveryMode.INLINE

    def test_file_based_when_budget_exceeded(self):
        r = Retriever()
        pred = r(
            evidence_windows=WINDOWS,
            query="the password network wifi",
            task_category=TaskCategory.SINGLE_SESSION,
            context_budget_tokens=1,  # tiny budget forces overflow
        )
        assert pred["delivery_mode"] is DeliveryMode.FILE_BASED

    def test_ranked_evidence_carries_ranks(self):
        r = Retriever()
        pred = r(
            evidence_windows=WINDOWS,
            query="wifi password",
            task_category=TaskCategory.SINGLE_SESSION,
        )
        top = pred["ranked_evidence"][0]
        assert top.lexical_rank >= 0 or top.semantic_rank >= 0
        assert top.score > 0.0

    def test_expansion_terms_positive(self):
        with pytest.raises(ValueError, match="expansion_terms must be positive"):
            Retriever(expansion_terms=0)

    def test_recency_weight_range(self):
        with pytest.raises(ValueError, match="recency_weight must be in"):
            Retriever(recency_weight=2.0)

    def test_recency_zero_is_noop(self):
        windows = [EvidenceWindow(text=f"wifi password detail {i}", source_index=i) for i in range(4)]
        base = Retriever(recency_weight=0.0)(evidence_windows=windows, query="wifi password")
        order = [r.window.source_index for r in base["ranked_evidence"]]
        assert order == sorted(order)

    def test_high_recency_promotes_latest(self):
        windows = [EvidenceWindow(text=f"wifi password detail {i}", source_index=i) for i in range(4)]
        out = Retriever(recency_weight=1.0)(evidence_windows=windows, query="wifi password")
        assert out["ranked_evidence"][0].window.source_index == 3

    def test_query_expansion_ranks_relevant(self):
        windows = [
            EvidenceWindow(text="the wifi password is bluefish42 vault", source_index=0),
            EvidenceWindow(text="unrelated turtles", source_index=1),
        ]
        out = Retriever(query_expansion=True)(evidence_windows=windows, query="wifi password")
        assert out["ranked_evidence"][0].window.source_index == 0

    def test_bad_rerank_raises(self):
        with pytest.raises(ValueError, match="rerank must be 'rrf' or 'mmr'"):
            Retriever(rerank="turbo")

    def test_mmr_returns_budgeted_ranked(self):
        windows = [
            EvidenceWindow(text="the wifi password is alpha", source_index=0),
            EvidenceWindow(text="the wifi password is alpha", source_index=1),
            EvidenceWindow(text="the dentist appointment is tuesday", source_index=2),
            EvidenceWindow(text="the cat sat on the mat", source_index=3),
        ]
        r = Retriever(rerank="mmr", top_k=2, mmr_lambda=0.3)
        pred = r(evidence_windows=windows, query="wifi password", task_category=TaskCategory.SINGLE_SESSION)
        assert len(pred["ranked_evidence"]) == 2


class TestActiveLanes:
    @pytest.mark.parametrize(
        "lexical_weight,semantic_weight,index_type,active_rank,disabled_rank",
        [
            (2.0, 0.0, BM25Index, "lexical_rank", "semantic_rank"),
            (0.0, 2.0, SemanticIndex, "semantic_rank", "lexical_rank"),
        ],
    )
    def test_membership_ranks_and_scores_follow_only_active_index(
        self, lexical_weight, semantic_weight, index_type, active_rank, disabled_rank
    ):
        texts = ["password password", "password detail", "passwords passwords", ""]
        windows = _windows(texts)
        query = "password"
        lexical_ids = {idx for idx, _ in BM25Index(texts).top_k(query, len(texts))}
        semantic_ids = {idx for idx, _ in SemanticIndex(texts).top_k(query, len(texts))}
        # A real sub-word match that BM25 cannot retrieve exposes candidate leakage.
        assert 2 in semantic_ids - lexical_ids
        expected = index_type(texts).top_k(query, len(texts))
        out = Retriever(
            lexical_weight=lexical_weight, semantic_weight=semantic_weight, k=0
        )(evidence_windows=windows, query=query)
        ranked = out["ranked_evidence"]
        assert [r.window.source_index for r in ranked] == [idx for idx, _ in expected]
        for rank, item in enumerate(ranked):
            assert getattr(item, active_rank) == rank
            assert getattr(item, disabled_rank) == -1
            assert item.score == round(2.0 / (rank + 1), 8)
        assert out["delivery_mode"] is DeliveryMode.INLINE

    @pytest.mark.parametrize("lexical_weight,semantic_weight", [(1.0, 0.0), (0.0, 1.0)])
    @pytest.mark.parametrize("query_expansion", [False, True])
    @pytest.mark.parametrize("rerank", ["rrf", "mmr"])
    def test_disabled_scoring_index_does_not_run_beyond_independent_feedback(
        self, lexical_weight, semantic_weight, query_expansion, rerank
    ):
        # Profile real code execution without replacing any index/model boundary.
        active = BM25Index if lexical_weight else SemanticIndex
        disabled = SemanticIndex if lexical_weight else BM25Index
        retriever = Retriever(
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
            query_expansion=query_expansion,
            rerank=rerank,
        )
        profile = cProfile.Profile()
        out = profile.runcall(retriever, evidence_windows=WINDOWS, query="wifi password")
        calls = {entry.code: entry.callcount for entry in profile.getstats()}
        assert out["ranked_evidence"]
        active_calls = 1 + int(query_expansion and active is BM25Index)
        # Explicit PRF performs one independent BM25 pass even with no lexical
        # fusion lane. MMR embeds texts but never builds a SemanticIndex.
        disabled_calls = int(query_expansion and disabled is BM25Index)
        for method in ("__init__", "score", "top_k"):
            assert calls.get(getattr(active, method).__code__, 0) == active_calls
            assert calls.get(getattr(disabled, method).__code__, 0) == disabled_calls

    def test_semantic_only_preserves_explicit_bm25_query_expansion(self):
        texts = ["password alpha alpha", "alpha alpha", "password beta"]
        query = "password"
        expanded = expand_query(query, texts, top_terms=1)
        assert expanded != query
        expected = SemanticIndex(texts).top_k(expanded, len(texts))
        out = Retriever(
            lexical_weight=0.0, semantic_weight=1.0, query_expansion=True, expansion_terms=1
        )(evidence_windows=_windows(texts), query=query)
        ranked = out["ranked_evidence"]
        assert [r.window.source_index for r in ranked] == [idx for idx, _ in expected]
        for rank, item in enumerate(ranked):
            assert item.lexical_rank == -1
            assert item.semantic_rank == rank
            assert item.score == round(1.0 / (61 + rank), 8)

    @pytest.mark.parametrize("rerank", ["rrf", "mmr"])
    @pytest.mark.parametrize("recency_weight", [0.0, 1.0])
    def test_recency_and_mmr_select_only_active_candidates(self, rerank, recency_weight):
        windows = [
            EvidenceWindow(text="password alpha", source_index=-1),
            EvidenceWindow(text="password beta", source_index=3),
            EvidenceWindow(text="passwords passwords", source_index=100),
        ]
        # The recalled window stays exempt; the late semantic-only candidate must
        # not get a recency bonus or an MMR slot in the lexical-only configuration.
        expected = [
            RankedEvidence(window=windows[0], score=round(1 / 61, 8), lexical_rank=0, semantic_rank=-1),
            RankedEvidence(window=windows[1], score=round(1 / 62, 8), lexical_rank=1, semantic_rank=-1),
        ]
        if recency_weight:
            expected[1] = RankedEvidence(
                window=windows[1],
                score=round(expected[1].score + expected[0].score, 8),
                lexical_rank=1,
                semantic_rank=-1,
            )
            expected.reverse()
        if rerank == "mmr":
            expected = mmr_rerank(expected, lambda_=0.3, k=8)
        out = Retriever(
            lexical_weight=1.0, semantic_weight=0.0, rerank=rerank,
            recency_weight=recency_weight, mmr_lambda=0.3,
        )(evidence_windows=windows, query="password")
        assert out["ranked_evidence"] == expected

    @pytest.mark.parametrize("lexical_weight,semantic_weight", [(1.0, 0.0), (0.0, 1.0)])
    def test_active_lane_without_signal_returns_no_evidence(self, lexical_weight, semantic_weight):
        out = Retriever(lexical_weight=lexical_weight, semantic_weight=semantic_weight)(
            evidence_windows=_windows(["", ""]), query="password", context_budget_tokens=1
        )
        assert out["ranked_evidence"] == []
        assert out["delivery_mode"] is DeliveryMode.INLINE

    @pytest.mark.parametrize(
        "category,weights",
        [
            (TaskCategory.TEMPORAL, (0.75, 0.25)),
            (TaskCategory.SINGLE_SESSION, (0.70, 0.30)),
            (TaskCategory.MULTI_SESSION, (0.65, 0.35)),
            (TaskCategory.CODE, (0.70, 0.30)),
            (TaskCategory.PREFERENCE, (0.55, 0.45)),
            (TaskCategory.KNOWLEDGE_UPDATE, (0.55, 0.45)),
        ],
    )
    def test_positive_category_defaults_keep_real_index_fusion(self, category, weights):
        texts = [w.text for w in WINDOWS]
        query = "wifi password"
        lexical = {idx: rank for rank, (idx, _) in enumerate(BM25Index(texts).top_k(query, len(texts)))}
        semantic = {idx: rank for rank, (idx, _) in enumerate(SemanticIndex(texts).top_k(query, len(texts)))}
        scores = {
            idx: (weights[0] / (61 + lexical[idx]) if idx in lexical else 0.0)
            + (weights[1] / (61 + semantic[idx]) if idx in semantic else 0.0)
            for idx in lexical.keys() | semantic.keys()
        }
        expected_ids = sorted(scores, key=lambda idx: (-round(scores[idx], 12), idx))
        out = Retriever()(evidence_windows=WINDOWS, query=query, task_category=category)
        ranked = out["ranked_evidence"]
        assert [r.window.source_index for r in ranked] == expected_ids
        for item in ranked:
            idx = item.window.source_index
            assert item.score == round(scores[idx], 8)
            assert item.lexical_rank == lexical.get(idx, -1)
            assert item.semantic_rank == semantic.get(idx, -1)
