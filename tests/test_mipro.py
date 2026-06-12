"""Tests for the MIPRO-style configuration compiler (Zero-Mock)."""

import pytest
from src.compiler.metrics import EvalExample
from src.compiler.mipro import CompileResult, MIPROCompiler, default_search_space
from src.config import HarnessConfig
from src.signatures import (
    EpisodicEntry,
    EvidenceWindow,
    HarnessOutput,
    RankedEvidence,
    TaskCategory,
)

DATASET = [EvalExample("s", "q", "answer", expected_source_indices=(0,))]


def _output_for(config):
    """Build a runner whose efficiency improves as top_k shrinks.

    Lets the compiler discriminate configs deterministically: fewer ranked
    windows -> higher efficiency -> higher composite.
    """

    def run(example):
        ranked = tuple(
            RankedEvidence(window=EvidenceWindow(text="answer", source_index=j), score=1.0) for j in range(config.top_k)
        )
        return HarnessOutput(
            answer="answer",
            reasoning_trace="",
            evidence_citations=(),
            ranked_evidence=ranked,
            task_category=TaskCategory.SINGLE_SESSION,
            memory_written=EpisodicEntry(0, "q", "answer"),
        )

    return run


class TestSearchSpace:
    def test_default_space_non_empty(self):
        space = default_search_space()
        assert len(space) >= 6
        assert all(isinstance(c, HarnessConfig) for c in space)


class TestMIPROInit:
    def test_bad_auto_raises(self):
        with pytest.raises(ValueError, match="auto must be one of"):
            MIPROCompiler(auto="turbo")

    def test_valid_auto_tiers(self):
        for tier in ("light", "medium", "heavy"):
            assert MIPROCompiler(auto=tier).auto == tier


class TestCompile:
    def test_empty_candidates_raises(self):
        with pytest.raises(ValueError, match="candidate set must be non-empty"):
            MIPROCompiler().compile(_output_for, DATASET, candidates=[])

    def test_empty_dataset_raises(self):
        with pytest.raises(ValueError, match="dataset must be non-empty"):
            MIPROCompiler().compile(_output_for, [])

    def test_selects_best_config(self):
        candidates = [HarnessConfig(top_k=12), HarnessConfig(top_k=2)]
        result = MIPROCompiler(auto="heavy").compile(_output_for, DATASET, candidates)
        # Smaller top_k -> better efficiency -> chosen.
        assert result.best_config.top_k == 2

    def test_light_budget_truncates(self):
        result = MIPROCompiler(auto="light").compile(_output_for, DATASET)
        assert result.n_candidates == 4

    def test_heavy_evaluates_all(self):
        space = default_search_space()
        result = MIPROCompiler(auto="heavy").compile(_output_for, DATASET, space)
        assert result.n_candidates == len(space)

    def test_result_is_compile_result(self):
        result = MIPROCompiler().compile(_output_for, DATASET)
        assert isinstance(result, CompileResult)
        assert len(result.trace) == result.n_candidates
        assert result.best_score == max(s for _, s in result.trace)
