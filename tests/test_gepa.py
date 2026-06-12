"""Tests for GEPA-style evolution and skill constraints (Zero-Mock)."""

import pytest
from src.compiler.gepa import (
    DSPY_AVAILABLE,
    GEPAOptimizer,
    SKILL_MAX_BYTES,
    check_skill_constraints,
    to_dspy_signature,
)
from src.compiler.metrics import EvalExample, EvalReport
from src.config import HarnessConfig, default_config
from src.signatures import (
    EpisodicEntry,
    EvidenceWindow,
    HarnessOutput,
    InputField,
    InspectorSignature,
    MemoryGateSignature,
    OutputField,
    RankedEvidence,
    ReasonerSignature,
    RetrieverSignature,
    Signature,
    TaskCategory,
)

DATASET = [EvalExample("s", "q", "answer", expected_source_indices=(0,))]


def _build_fn(config):
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


class TestSkillConstraints:
    def test_valid_skill_passes(self):
        report = check_skill_constraints("# SKILL\n\nsome content")
        assert report.ok
        assert report.within_size and report.non_empty
        assert report.reasons == ()

    def test_oversized_skill_fails(self):
        report = check_skill_constraints("x" * (SKILL_MAX_BYTES + 1))
        assert not report.ok
        assert not report.within_size
        assert any("exceeds budget" in r for r in report.reasons)

    def test_empty_skill_fails(self):
        report = check_skill_constraints("   ")
        assert not report.ok
        assert not report.non_empty

    def test_custom_budget(self):
        assert check_skill_constraints("hello", max_bytes=3).within_size is False


def _report(accuracy, grounding, efficiency):
    return EvalReport(
        composite=0.0,
        accuracy=accuracy,
        grounding=grounding,
        efficiency=efficiency,
        n=1,
    )


class TestReflect:
    def test_grounding_weakest_deepens_retrieval(self):
        opt = GEPAOptimizer()
        cfg = default_config()
        new = opt.reflect(cfg, _report(0.9, 0.1, 0.9))
        assert new.top_k == cfg.top_k + 1
        assert new.max_evidence == cfg.max_evidence + 1

    def test_accuracy_weakest_sets_lexical_weights(self):
        opt = GEPAOptimizer()
        cfg = default_config()
        new = opt.reflect(cfg, _report(0.1, 0.9, 0.9))
        assert new.lexical_weight == 0.8 and new.semantic_weight == 0.2
        assert new.max_windows == cfg.max_windows + 2

    def test_efficiency_weakest_tightens_retrieval(self):
        opt = GEPAOptimizer()
        cfg = HarnessConfig(top_k=8, max_evidence=5)
        new = opt.reflect(cfg, _report(0.9, 0.9, 0.1))
        assert new.top_k == 7 and new.max_evidence == 4

    def test_efficiency_floor_does_not_go_below_two(self):
        opt = GEPAOptimizer()
        cfg = HarnessConfig(top_k=2, max_evidence=1)
        new = opt.reflect(cfg, _report(0.9, 0.9, 0.1))
        assert new.top_k == 2 and new.max_evidence == 1

    def test_invalid_mutation_returns_config_unchanged(self):
        # A degenerate cap forces the grounding-branch mutation to build an invalid
        # config (max_evidence -> min(0, ...) == 0), which HarnessConfig rejects.
        # reflect must swallow that ValueError and return the incumbent untouched —
        # no mocking: a real cap, a real report, a real validation failure.
        opt = GEPAOptimizer(max_evidence_cap=0)
        cfg = default_config()
        new = opt.reflect(cfg, _report(0.9, 0.1, 0.9))  # grounding weakest
        assert new == cfg


class TestEvolve:
    def test_empty_dataset_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            GEPAOptimizer().evolve(_build_fn, [], iterations=2)

    def test_negative_iterations_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            GEPAOptimizer().evolve(_build_fn, DATASET, iterations=-1)

    def test_zero_iterations_returns_seed(self):
        result = GEPAOptimizer().evolve(_build_fn, DATASET, iterations=0)
        assert result.n_candidates == 1
        assert len(result.trace) == 1

    def test_evolution_records_trace(self):
        result = GEPAOptimizer().evolve(_build_fn, DATASET, iterations=4)
        assert result.n_candidates == 5  # seed + 4 iterations
        assert result.best_score == max(s for _, s in result.trace)

    def test_evolution_improves_or_holds(self):
        # Seed with a wasteful config; reflection should not worsen the best.
        seed = HarnessConfig(top_k=12, max_evidence=8)
        result = GEPAOptimizer().evolve(_build_fn, DATASET, seed_config=seed, iterations=6)
        seed_score = result.trace[0][1]
        assert result.best_score >= seed_score


class TestDSPyBridge:
    def test_dspy_availability_flag_is_bool(self):
        assert isinstance(DSPY_AVAILABLE, bool)

    def test_bridge_raises_without_dspy(self):
        if DSPY_AVAILABLE:
            pytest.skip("dspy installed; offline guard not exercised")
        with pytest.raises(RuntimeError, match="dspy is not installed"):
            to_dspy_signature(InspectorSignature)


class _ScalarSig(Signature):
    """Answer the question using the supporting context."""

    question: str = InputField("the question to answer")
    context: str = InputField("supporting context")
    answer: str = OutputField("the grounded answer")


@pytest.mark.skipif(not DSPY_AVAILABLE, reason="real dspy not installed; bridge body needs the `dspy` extra")
class TestRealDspyBridge:
    """Validate ``to_dspy_signature`` against a real installed dspy (Zero-Mock).

    These exercise the ``pragma: no cover`` bridge body that only runs when the
    ``dspy`` extra is present, proving it emits genuine, usable ``dspy.Signature``
    classes rather than a stub.
    """

    def test_scalar_signature_roundtrips_to_real_dspy(self):
        import dspy

        converted = to_dspy_signature(_ScalarSig)
        assert issubclass(converted, dspy.Signature)
        assert set(converted.input_fields) == {"question", "context"}
        assert set(converted.output_fields) == {"answer"}
        # the ATLAS instruction (class docstring) carries through to dspy
        assert _ScalarSig.instructions() in converted.instructions

    def test_all_stage_signatures_convert_and_are_predict_usable(self):
        import dspy

        for sig in (InspectorSignature, RetrieverSignature, ReasonerSignature, MemoryGateSignature):
            converted = to_dspy_signature(sig)
            assert issubclass(converted, dspy.Signature)
            assert set(converted.input_fields) == set(sig.inputs())
            assert set(converted.output_fields) == set(sig.outputs())
            # a converted signature must be a usable dspy artifact, not just a class
            predictor = dspy.Predict(converted)
            assert predictor.signature is converted
