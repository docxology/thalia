"""Tests for Stage 1 — the lexical-first hybrid Retriever (Zero-Mock)."""

import pytest
from src.signatures import DeliveryMode, EvidenceWindow, TaskCategory
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
