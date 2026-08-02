"""Tests for the LongMemEval_S loader (Zero-Mock; gated on the downloaded benchmark)."""

import json

import pytest

from src.evaluation.longmemeval import (
    DEFAULT_PATH,
    _load_neural_checkpoint,
    _rrf_rank,
    _write_neural_checkpoint,
    load_longmemeval,
    longmemeval_available,
    validate_longmemeval_payload,
)
from src.compiler.metrics import EvalExample
from src.signatures import TaskCategory


def test_available_returns_bool():
    assert isinstance(longmemeval_available(), bool)


def test_rrf_rank_fusion_order():
    # Two rankings that agree on their top item but disagree on the rest.
    # Index 2 ranks #1 in both lists -> should come out first after RRF fusion.
    # Index 0 ranks #2 in list A and #3 in list B (lower combined score than index 1).
    # Index 1 ranks #3 in list A and #2 in list B.
    ranking_a = [2, 0, 1]
    ranking_b = [2, 1, 0]
    result = _rrf_rank([ranking_a, ranking_b])
    assert isinstance(result, list)
    assert set(result) == {0, 1, 2}
    # Index 2 must be first: it earned the top rank in both lists.
    assert result[0] == 2
    # Index 1 ranked #2 in list B vs index 0 ranked #2 in list A; scores are
    # symmetric, so they tie — only verify 1 and 0 both appear after 2.
    assert set(result[1:]) == {0, 1}


def test_rrf_rank_single_ranking_preserves_order():
    # With a single ranking the RRF score is 1/(k0+rank+1), so the original order
    # must be preserved exactly.
    ranking = [5, 3, 7, 1]
    result = _rrf_rank([ranking])
    assert result == ranking


@pytest.mark.skipif(not longmemeval_available(), reason="LongMemEval_S not downloaded")
def test_load_longmemeval_limit_truncates():
    # Exercise the `if limit is not None: data = data[:limit]` branch (line 83->85).
    full = load_longmemeval()
    limited = load_longmemeval(limit=3)
    assert len(limited) == 3
    # The truncated slice must be a strict prefix of the full dataset.
    assert len(full) > 3
    for i in range(3):
        assert limited[i].query == full[i].query


def test_missing_file_raises_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="get_longmemeval"):
        load_longmemeval(path=tmp_path / "absent.json")


def test_validation_checks_every_record_and_alignment():
    valid = {
        "question_id": "q0",
        "question_date": "2025-01-01",
        "question": "q",
        "answer": "a",
        "question_type": "single-session-user",
        "answer_session_ids": ["s0"],
        "haystack_session_ids": ["s0"],
        "haystack_dates": ["2025-01-01"],
        "haystack_sessions": [[{"role": "user", "content": "fact"}]],
    }
    assert validate_longmemeval_payload([valid]) == [valid]
    malformed = dict(valid)
    malformed["question_id"] = "q1"
    malformed["haystack_session_ids"] = []
    with pytest.raises(ValueError, match="unaligned"):
        validate_longmemeval_payload([valid, malformed])
    malformed = dict(valid)
    malformed["haystack_sessions"] = [[{"role": "user"}]]
    with pytest.raises(ValueError, match="turn"):
        validate_longmemeval_payload([malformed])
    malformed = dict(valid)
    malformed["answer_session_ids"] = ["missing"]
    with pytest.raises(ValueError, match="unknown sessions"):
        validate_longmemeval_payload([malformed])
    malformed = dict(valid)
    malformed["question_type"] = "unknown"
    with pytest.raises(ValueError, match="question_type"):
        validate_longmemeval_payload([malformed])


def test_validation_rejects_duplicate_ids_and_invalid_limits(tmp_path):
    valid = {
        "question_id": "q0",
        "question_date": "2025-01-01",
        "question": "q",
        "answer": "a",
        "question_type": "single-session-user",
        "answer_session_ids": ["s0"],
        "haystack_session_ids": ["s0"],
        "haystack_dates": ["2025-01-01"],
        "haystack_sessions": [[{"role": "user", "content": "fact"}]],
    }
    with pytest.raises(ValueError, match="duplicates"):
        validate_longmemeval_payload([valid, dict(valid)])
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps([valid]))
    with pytest.raises(ValueError, match="positive"):
        load_longmemeval(path, limit=0)


def test_neural_checkpoint_round_trip_is_atomic_and_scope_aware(tmp_path):
    checkpoint = tmp_path / "neural_checkpoint.json"
    benchmark = {"sha256": "abc123", "size_bytes": 3}
    rows = {
        "q1": {"example_id": "q1", "accuracy": 1.0, "grounding": 0.5, "session_reachability": 1.0},
        "q0": {"example_id": "q0", "accuracy": 0.0, "grounding": 1.0, "session_reachability": 0.0},
    }
    _write_neural_checkpoint(
        checkpoint,
        rows,
        benchmark=benchmark,
        model="gemma-test",
        generation_options={"temperature": 0.0},
    )
    assert checkpoint.is_file()
    assert not checkpoint.with_name(f".{checkpoint.name}.tmp").exists()
    loaded = _load_neural_checkpoint(
        checkpoint,
        benchmark=benchmark,
        model="gemma-test",
        generation_options={"temperature": 0.0},
        requested_ids={"q0", "q1", "q-missing"},
    )
    assert list(loaded) == ["q0", "q1"]
    assert loaded == rows
    assert _load_neural_checkpoint(
        checkpoint,
        benchmark={"sha256": "different", "size_bytes": 3},
        model="gemma-test",
        generation_options={"temperature": 0.0},
        requested_ids={"q0", "q1"},
    ) == {}
    assert _load_neural_checkpoint(
        checkpoint,
        benchmark=benchmark,
        model="different-model",
        generation_options={"temperature": 0.0},
        requested_ids={"q0", "q1"},
    ) == {}


def test_neural_checkpoint_rejects_duplicate_or_invalid_rows(tmp_path):
    checkpoint = tmp_path / "neural_checkpoint.json"
    benchmark = {"sha256": "abc123", "size_bytes": 3}
    checkpoint.write_text(
        json.dumps(
            {
                "benchmark_sha256": "abc123",
                "benchmark_size_bytes": 3,
                "model": "gemma-test",
                "rows": [
                    {"example_id": "q0", "accuracy": 0.5, "grounding": 0.5, "session_reachability": 1.0},
                    {"example_id": "q0", "accuracy": 0.4, "grounding": 0.4, "session_reachability": 1.0},
                ],
            }
        )
    )
    assert _load_neural_checkpoint(
        checkpoint,
        benchmark=benchmark,
        model="gemma-test",
        generation_options={"temperature": 0.0},
        requested_ids={"q0"},
    ) == {}
    checkpoint.write_text(
        json.dumps(
            {
                "benchmark_sha256": "abc123",
                "benchmark_size_bytes": 3,
                "model": "gemma-test",
                "rows": [{"example_id": "q0", "accuracy": 2.0, "grounding": 0.5, "session_reachability": 1.0}],
            }
        )
    )
    assert _load_neural_checkpoint(
        checkpoint,
        benchmark=benchmark,
        model="gemma-test",
        generation_options={"temperature": 0.0},
        requested_ids={"q0"},
    ) == {}


def test_ranking_recall_by_mode_reports_optional_embedder_unavailability():
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
