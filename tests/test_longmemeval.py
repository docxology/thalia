"""Tests for the LongMemEval_S loader (Zero-Mock; gated on the downloaded benchmark)."""

import json

import pytest

from src.evaluation.longmemeval import DEFAULT_PATH, load_longmemeval, longmemeval_available
from src.compiler.metrics import EvalExample
from src.signatures import TaskCategory


def test_available_returns_bool():
    assert isinstance(longmemeval_available(), bool)


def test_missing_file_raises_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="get_longmemeval"):
        load_longmemeval(path=tmp_path / "absent.json")


def test_ranking_recall_by_mode_has_backward_compatible_shape_without_embedder():
    from src.evaluation.longmemeval import _ranking_recall_by_mode

    example = EvalExample(
        session_history="User: the wifi password is bluefish42\nUser: the cat is grey",
        query="What is the wifi password?",
        expected_answer="bluefish42",
        expected_source_indices=(0,),
        task_category=TaskCategory.SINGLE_SESSION,
    )
    result = _ranking_recall_by_mode([example], neural_model="definitely-missing-model", k=1)
    assert result["available"] is False
    assert result["n"] == 1
    assert result["lexical"] == 1.0
    assert "dense" not in result and "hybrid" not in result


@pytest.mark.skipif(not longmemeval_available(), reason="LongMemEval_S not downloaded")
class TestRealBenchmark:
    def test_loads_into_eval_examples(self):
        ds = load_longmemeval(limit=10)
        assert len(ds) == 10
        for ex in ds:
            assert isinstance(ex.session_history, str) and ex.session_history
            assert isinstance(ex.task_category, TaskCategory)
            assert ex.expected_answer

    def test_session_grounding_indices_independently_rederived(self):
        # Re-derive, from the RAW benchmark, which flattened line indices belong to an
        # answer session, and assert they match the loader's expected_source_indices
        # exactly. This kills a mutation of `if sid in answer_sessions` to `not in`, a
        # mis-zipped session->turn mapping, or off-by-one drift — defects the old
        # in-range bound check (always true by construction) could never catch.
        raw = json.loads(DEFAULT_PATH.read_text())[:8]
        ds = load_longmemeval(limit=8)
        for item, ex in zip(raw, ds):
            answer = set(item["answer_session_ids"])
            expected, idx = [], 0
            for sid, session in zip(item["haystack_session_ids"], item["haystack_sessions"]):
                for _turn in session:
                    if sid in answer:
                        expected.append(idx)
                    idx += 1
            assert tuple(expected) == ex.expected_source_indices
            # and the evidence is a strict, non-trivial subset of the haystack lines
            n_lines = ex.session_history.count("\n") + 1
            assert 0 < len(ex.expected_source_indices) <= n_lines or len(answer) == 0

    def test_evidence_lines_belong_to_an_answer_session(self):
        # At least one example must carry non-empty evidence indices (an answer session
        # present in the haystack), proving the session->line mapping works.
        ds = load_longmemeval(limit=20)
        assert any(len(ex.expected_source_indices) > 0 for ex in ds)

    def test_bottleneck_analysis_asserts_the_headline_orderings(self):
        # The headline functions (bottleneck_analysis / longmemeval_eval) are gated and
        # were untested, so the central claims could regress to no-ops with the suite
        # green. Drive bottleneck_analysis with tiny limits and assert the scientific
        # orderings it is supposed to demonstrate.
        from src.dspy_runtime import ollama_model_available

        if not ollama_model_available():
            pytest.skip("ollama model not available for the neural rows")
        from src.evaluation.longmemeval import bottleneck_analysis

        r = bottleneck_analysis(ranking_limit=6, sweep_values=(15, 30), neural_limit=3)
        # Localisation: full-haystack ranking recovers evidence better than the Inspector surfaces it.
        assert r["ranking_recall_at_10"] >= r["inspector_recall"]
        # Relaxing the narrowing is monotonic non-decreasing in extractive grounding.
        assert r["extractive_grounding_by_maxwindows"][15] <= r["extractive_grounding_by_maxwindows"][30]
        # The shipped fix surfaces at least as much evidence as the default budget (grounding is deterministic in window count).
        assert r["neural_adaptive"]["grounding"] >= r["neural_by_maxwindows"][15]["grounding"] - 1e-9

    def test_inspector_not_ranking_is_the_recall_bottleneck(self):
        # Falsifiable guard for the headline finding (deterministic, no model): over a
        # real subset, full-haystack BM25 ranking recovers the evidence far better than
        # the Inspector's narrowing surfaces it -> the Inspector, not ranking, is the cap.
        from src.config import default_config
        from src.retrieval.lexical import BM25Index
        from src.stages.inspector import Inspector

        cfg = default_config()
        inspector = Inspector(max_windows=cfg.max_windows, partition_threshold=cfg.partition_threshold, partition_size=cfg.partition_size)
        examples = [e for e in load_longmemeval(limit=25) if e.expected_source_indices]
        rank_hits = insp_hits = 0
        for ex in examples:
            gold = set(ex.expected_source_indices)
            lines = [ln for ln in ex.session_history.split("\n") if ln.strip()]
            ranked = {i for i, _ in BM25Index(lines).top_k(ex.query, k=10)}
            windows = {w.source_index for w in inspector(session_history=ex.session_history, query=ex.query)["evidence_windows"]}
            rank_hits += 1 if ranked & gold else 0
            insp_hits += 1 if windows & gold else 0
        ranking_recall = rank_hits / len(examples)
        inspector_recall = insp_hits / len(examples)
        assert ranking_recall > inspector_recall  # ranking is not the bottleneck; the Inspector is
        assert ranking_recall >= 0.9  # full-haystack ranking essentially always recovers the evidence
