"""Tests for evaluation metrics (Zero-Mock)."""

import pytest
from src.compiler.metrics import (
    EvalExample,
    EvalReport,
    answer_score,
    efficiency_score,
    evaluate,
    grounding_score,
    harness_metric,
    token_f1,
)
from src.signatures import (
    EpisodicEntry,
    EvidenceCitation,
    EvidenceWindow,
    HarnessOutput,
    RankedEvidence,
    TaskCategory,
)


def _output(answer, cited=(), n_ranked=1):
    citations = tuple(EvidenceCitation(source_index=i, excerpt=t) for i, t in cited)
    ranked = tuple(RankedEvidence(window=EvidenceWindow(text="w", source_index=j), score=1.0) for j in range(n_ranked))
    return HarnessOutput(
        answer=answer,
        reasoning_trace="",
        evidence_citations=citations,
        ranked_evidence=ranked,
        task_category=TaskCategory.SINGLE_SESSION,
        memory_written=EpisodicEntry(0, "q", answer),
    )


class TestTokenF1:
    def test_both_empty_is_one(self):
        assert token_f1("", "") == 1.0

    def test_one_empty_is_zero(self):
        assert token_f1("hello", "") == 0.0

    def test_no_overlap_is_zero(self):
        assert token_f1("alpha", "beta") == 0.0

    def test_perfect_match_is_one(self):
        assert token_f1("the cat", "the cat") == 1.0

    def test_partial_overlap(self):
        # pred={a,b}, gold={a,c}; overlap=1 -> P=0.5,R=0.5,F1=0.5
        assert token_f1("a b", "a c") == 0.5

    def test_duplicate_tokens_are_deduplicated_by_contract(self):
        # The implementation is set-based: duplicate surface tokens do not
        # change either denominator or the overlap count.
        assert token_f1("alpha alpha beta", "alpha beta") == 1.0

    def test_token_f1_is_not_multiset_f1(self):
        assert token_f1("alpha alpha", "alpha gamma") == pytest.approx(2 / 3)


class TestComponentScores:
    def test_answer_score(self):
        out = _output("now live in Lisbon")
        ex = EvalExample("s", "q", "live in Lisbon")
        assert answer_score(out, ex) > 0.5

    def test_grounding_with_expected_index_hit(self):
        out = _output("Lisbon", cited=((2, "now live in Lisbon"),))
        ex = EvalExample("s", "q", "Lisbon", expected_source_indices=(2,))
        # hit bonus (0.5) + support term.
        assert grounding_score(out, ex) >= 0.5

    def test_grounding_with_expected_index_miss(self):
        out = _output("Lisbon", cited=((9, "unrelated text"),))
        ex = EvalExample("s", "q", "Lisbon", expected_source_indices=(2,))
        assert grounding_score(out, ex) < 0.5

    def test_grounding_without_expected_indices(self):
        out = _output("Lisbon", cited=((0, "now live in Lisbon"),))
        ex = EvalExample("s", "q", "Lisbon")
        assert grounding_score(out, ex) > 0.0

    def test_grounding_no_citations_is_zero(self):
        out = _output("Lisbon", cited=())
        ex = EvalExample("s", "q", "Lisbon")
        assert grounding_score(out, ex) == 0.0

    def test_efficiency_decreases_with_more_evidence(self):
        few = _output("a", n_ranked=2)
        many = _output("a", n_ranked=12)
        assert efficiency_score(few) > efficiency_score(many)

    def test_efficiency_floored_at_zero(self):
        assert efficiency_score(_output("a", n_ranked=100)) == 0.0


class TestHarnessMetric:
    def test_bounded_zero_to_one(self):
        out = _output("Lisbon", cited=((0, "Lisbon"),), n_ranked=1)
        ex = EvalExample("s", "q", "Lisbon", expected_source_indices=(0,))
        score = harness_metric(out, ex)
        assert 0.0 <= score <= 1.0


class TestEvaluate:
    def test_empty_dataset_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            evaluate(lambda ex: _output("a"), [])

    def test_aggregates_components(self):
        dataset = [
            EvalExample("s", "q", "Lisbon", expected_source_indices=(0,)),
            EvalExample("s", "q", "Paris", expected_source_indices=(0,)),
        ]

        def run(ex):
            return _output(ex.expected_answer, cited=((0, ex.expected_answer),), n_ranked=1)

        report = evaluate(run, dataset)
        assert isinstance(report, EvalReport)
        assert report.n == 2
        assert len(report.per_example) == 2
        assert 0.0 <= report.composite <= 1.0
        assert report.accuracy == 1.0  # exact answers
