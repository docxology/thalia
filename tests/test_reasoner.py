"""Tests for Stage 2 — the typed declarative Reasoner (Zero-Mock)."""

import pytest
from src.signatures import (
    EvidenceWindow,
    MemorySnapshot,
    RankedEvidence,
    TaskCategory,
)
from src.routing import classify_task
from src.stages.reasoner import Reasoner


def _ranked(texts):
    return [
        RankedEvidence(window=EvidenceWindow(text=t, source_index=i), score=1.0 - 0.1 * i) for i, t in enumerate(texts)
    ]


class TestClassifyTask:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("How do I fix this python error?", TaskCategory.CODE),
            ("I no longer use Vim; I now use Helix", TaskCategory.KNOWLEDGE_UPDATE),
            ("When is the meeting scheduled?", TaskCategory.TEMPORAL),
            ("What did we discuss across our sessions?", TaskCategory.MULTI_SESSION),
            ("What is my favorite food?", TaskCategory.PREFERENCE),
            ("Tell me a joke", TaskCategory.SINGLE_SESSION),
        ],
    )
    def test_classification(self, query, expected):
        assert classify_task(query) is expected


class TestReasonerInit:
    def test_non_positive_max_evidence_raises(self):
        with pytest.raises(ValueError, match="max_evidence must be positive"):
            Reasoner(max_evidence=0)


class TestReasonerForward:
    def test_cot_path_grounds_in_evidence(self):
        r = Reasoner()
        ranked = _ranked(["the answer is 42", "irrelevant chatter"])
        pred = r(
            query="what is the answer",
            ranked_evidence=ranked,
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert "42" in pred["answer"]
        assert pred["reasoning_trace"].startswith("[cot]")
        assert pred["evidence_citations"]

    def test_react_path_for_code(self):
        r = Reasoner()
        ranked = _ranked(["the python error is a KeyError", "unrelated"])
        pred = r(
            query="what python error occurs",
            ranked_evidence=ranked,
            task_category=TaskCategory.CODE,
        )
        assert pred["reasoning_trace"].startswith("[react]")
        assert "KeyError" in pred["answer"]

    def test_react_falls_back_when_no_token_overlap(self):
        r = Reasoner()
        # No evidence shares a query token -> react uses the full ranked set.
        ranked = _ranked(["alpha beta", "gamma delta"])
        pred = r(
            query="zzz python qqq",
            ranked_evidence=ranked,
            task_category=TaskCategory.CODE,
        )
        assert "hop1 grep -> 2/2" in pred["reasoning_trace"]

    def test_no_evidence_path(self):
        r = Reasoner()
        pred = r(
            query="anything",
            ranked_evidence=[],
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert pred["evidence_citations"] == []
        assert "no evidence" in pred["reasoning_trace"]

    def test_citation_fallback_to_top_window(self):
        r = Reasoner()
        # Answer (an evidence line) always overlaps that line, so >=1 citation.
        ranked = _ranked(["unique-token-line", "other"])
        pred = r(
            query="unique-token-line",
            ranked_evidence=ranked,
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert len(pred["evidence_citations"]) >= 1

    def test_requires_consolidation_for_knowledge_update(self):
        r = Reasoner()
        pred = r(
            query="I now use Lisbon",
            ranked_evidence=_ranked(["now live in Lisbon"]),
            task_category=TaskCategory.KNOWLEDGE_UPDATE,
        )
        assert pred["requires_consolidation"] is True

    def test_requires_consolidation_for_remember_marker(self):
        r = Reasoner()
        pred = r(
            query="please remember the door code is 1234",
            ranked_evidence=_ranked(["door code is 1234"]),
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert pred["requires_consolidation"] is True
        assert pred["explicit_request"] is True

    def test_do_not_forget_sets_explicit_request(self):
        r = Reasoner()
        pred = r(
            query="do not forget the gate code is 9",
            ranked_evidence=_ranked(["gate code is 9"]),
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert pred["explicit_request"] is True
        assert pred["requires_consolidation"] is True

    def test_no_consolidation_for_plain_query(self):
        r = Reasoner()
        pred = r(
            query="what is the door code",
            ranked_evidence=_ranked(["door code is 1234"]),
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert pred["requires_consolidation"] is False

    def test_default_memory_snapshot(self):
        r = Reasoner()
        pred = r(
            query="x",
            ranked_evidence=_ranked(["x marks spot"]),
            task_category=TaskCategory.SINGLE_SESSION,
            memory_context=MemorySnapshot(memory_md="prior fact"),
        )
        assert pred["answer"]


class TestReasonerVerify:
    def test_grounding_threshold_validated(self):
        with pytest.raises(ValueError, match="grounding_threshold must be in"):
            Reasoner(verify=True, grounding_threshold=2.0)

    def test_grounding_support_empty_answer_returns_zero(self):
        """_grounding_support returns 0.0 when the answer tokenises to nothing (line 152)."""
        from src.signatures import EvidenceCitation

        # An answer of pure whitespace/punctuation produces no tokens → 0.0.
        citations = [EvidenceCitation(source_index=0, excerpt="some relevant evidence")]
        assert Reasoner._grounding_support("", citations) == 0.0
        assert Reasoner._grounding_support("   ", citations) == 0.0

    def test_verify_ok_path(self):
        from src.llm import CallableLM

        r = Reasoner(verify=True)
        pred = r(
            query="what is the answer",
            ranked_evidence=_ranked(["the answer is 42", "noise"]),
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert "[verify ok" in pred["reasoning_trace"]

    def test_verify_reanswer_path(self):
        from src.llm import CallableLM

        r = Reasoner(
            verify=True,
            grounding_threshold=0.9,
            lm=CallableLM(lambda prompt: "zzz totally unrelated tokens"),
        )
        pred = r(
            query="what is the answer",
            ranked_evidence=_ranked(["the answer is 42", "noise"]),
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert "[verify reanswer" in pred["reasoning_trace"]

    def test_verify_off_by_default(self):
        r = Reasoner()
        pred = r(
            query="what is the answer",
            ranked_evidence=_ranked(["the answer is 42"]),
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert "verify" not in pred["reasoning_trace"]
