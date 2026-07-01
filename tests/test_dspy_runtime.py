"""Tests for the real DSPy runtime (Zero-Mock).

The pure adapter helpers are tested directly. The real dspy glue — real
``dspy.Predict`` and a real ``dspy.BootstrapFewShot`` optimizer backed by the
project's real ExtractiveLM — runs unconditionally. Nothing here is mocked,
faked, or stubbed.
"""

from types import SimpleNamespace

import pytest

from src.dspy_runtime import (
    DEFAULT_OLLAMA_MODEL,
    format_dspy_completion,
    model_in_tags,
    ollama_model_metadata_from_tags,
    ollama_model_available,
    parse_input_fields,
    parse_output_fields,
    qa_metric,
    render_extractive_prompt,
    token_f1,
)
from src.module import EVIDENCE_MARKER, QUESTION_MARKER

_USER = (
    "[[ ## context ## ]]\n"
    "The wifi password is bluefish42. The cat is grey.\n\n"
    "[[ ## question ## ]]\n"
    "What is the wifi password?\n\n"
    "Respond with the corresponding output fields, starting with the field "
    "`[[ ## answer ## ]]`, and then ending with the marker for `[[ ## completed ## ]]`."
)
_SYSTEM = (
    "Your input fields are:\n1. `context` (str):\n2. `question` (str):\n"
    "Your output fields are:\n1. `answer` (str):\n"
    "All interactions will be structured in the following way."
)


class TestPureAdapterHelpers:
    def test_parse_input_fields(self):
        fields = parse_input_fields(_USER)
        assert fields == {
            "context": "The wifi password is bluefish42. The cat is grey.",
            "question": "What is the wifi password?",
        }

    def test_parse_output_fields_ignores_types_and_input_block(self):
        assert parse_output_fields(_SYSTEM) == ["answer"]

    def test_render_extractive_prompt_splits_context_and_keeps_question(self):
        rendered = render_extractive_prompt(
            {"context": "X is five. Y is nine.", "question": "what is x?"}
        )
        assert EVIDENCE_MARKER in rendered and QUESTION_MARKER in rendered
        assert "- X is five." in rendered and "- Y is nine." in rendered
        assert rendered.strip().endswith("what is x?")

    def test_render_extractive_prompt_falls_back_to_last_input_as_question(self):
        rendered = render_extractive_prompt({"only_field": "some text here"})
        assert rendered.strip().endswith("some text here")

    def test_format_dspy_completion_roundtrips_fields_and_marker(self):
        out = format_dspy_completion(["answer"], "bluefish42")
        assert out == "[[ ## answer ## ]]\nbluefish42\n\n[[ ## completed ## ]]"
        # empty field list defaults to a single answer field
        assert format_dspy_completion([], "x").startswith("[[ ## answer ## ]]")

    def test_token_f1_bounds(self):
        assert token_f1("", "x") == 0.0
        assert token_f1("a b", "c d") == 0.0
        assert token_f1("car service april", "car service april") == pytest.approx(1.0)
        assert 0.0 < token_f1("car service april 12th", "your car service april") < 1.0

    def test_qa_metric_thresholds_on_overlap(self):
        gold = SimpleNamespace(answer="car service april 12th")
        assert qa_metric(gold, SimpleNamespace(answer="your car service is april 12th")) is True
        assert qa_metric(gold, SimpleNamespace(answer="the cat is grey")) is False

    def test_model_in_tags(self):
        tags = {"models": [{"name": "gemma3:4b"}, {"name": "llama3:8b"}]}
        assert model_in_tags(tags, "gemma3:4b") is True
        assert model_in_tags(tags, "mistral:7b") is False
        assert model_in_tags({}, "gemma3:4b") is False

    def test_model_in_tags_matches_bare_name_latest(self):
        tags = {"models": [{"name": "gemma3:latest"}]}
        assert model_in_tags(tags, "gemma3") is True

    def test_model_metadata_from_tags_records_digest(self):
        tags = {"models": [{"name": "gemma3:4b", "digest": "sha256:abc", "modified_at": "2026-01-01", "size": 7}]}
        metadata = ollama_model_metadata_from_tags(tags, "gemma3:4b")
        assert metadata["available"] is True
        assert metadata["digest"] == "sha256:abc"
        assert metadata["size"] == 7

    def test_ollama_probe_returns_false_on_dead_endpoint(self):
        # Real probe against an unreachable port -> clean False (no raise).
        assert ollama_model_available(model="gemma3:4b", api_base="http://localhost:1") is False


class TestRealDspyRuntime:
    """Exercises genuine dspy objects end-to-end (real Predict + real optimizer)."""

    def test_real_predict_produces_grounded_answer(self):
        from src.dspy_runtime import build_program, configure

        configure()
        program = build_program()
        out = program(
            context="User: my wifi password is bluefish42\nAssistant: noted\nThe cat is grey.",
            question="What is the wifi password?",
        )
        assert "bluefish42" in out.answer

    def test_real_predict_is_deterministic(self):
        from src.dspy_runtime import build_program, configure

        configure()
        program = build_program()
        kw = {"context": "X is five. Y is nine.", "question": "what is x?"}
        assert program(**kw).answer == program(**kw).answer

    def test_build_dataset_maps_demo_data_to_dspy_examples(self):
        import dspy

        from src.dspy_runtime import build_dataset

        ds = build_dataset()
        assert len(ds) == 6
        assert all(isinstance(ex, dspy.Example) for ex in ds)
        assert set(ds[0].inputs().keys()) == {"context", "question"}
        assert ds[0].answer  # gold answer carried through

    def test_neural_obeys_injection(self):
        from src.dspy_runtime import injection_resistance_neural

        result = injection_resistance_neural()
        # The instruction-following model is highly susceptible — it obeys overrides.
        assert result["n_probes"] >= 1
        assert result["neural_poison_rate"] >= 0.5

    def test_held_out_optimizer_lift_is_measured(self):
        from src.dspy_runtime import held_out_optimizer_lift

        result = held_out_optimizer_lift()
        # A real held-out before/after. On this task class the extractive backend
        # ignores demonstrations, so the lift is nil — an honest null, not a win.
        assert result["test_size"] >= 1
        assert 0.0 <= result["before"] <= 1.0 and 0.0 <= result["after"] <= 1.0
        assert abs(result["lift"]) < 0.01

    def test_real_optimizer_compiles_and_attaches_demos(self):
        from src.dspy_runtime import compile_program

        compiled = compile_program()
        demos = compiled.predictors()[0].demos
        assert len(demos) > 0  # real BootstrapFewShot attached bootstrapped demos
        # the compiled program still answers, grounded
        out = compiled(
            context="The launch code is alpha-seven. The sky is blue.",
            question="What is the launch code?",
        )
        assert "alpha" in out.answer.lower()


@pytest.mark.skipif(
    not ollama_model_available(),
    reason=f"needs a running Ollama serving {DEFAULT_OLLAMA_MODEL}",
)
class TestRealNeuralDspy:
    """Exercises a REAL neural LLM (Gemma via Ollama) through real dspy. No mock."""

    def test_gemma_predict_is_grounded(self):
        from src.dspy_runtime import build_program, configure_ollama

        configure_ollama()
        out = build_program()(
            context="The wifi password is bluefish42. The cat is grey. Lunch is at noon.",
            question="What is the wifi password?",
        )
        assert "bluefish42" in out.answer.lower()

    def test_gemma_chain_of_thought_reasons(self):
        import dspy

        from src.dspy_runtime import AnswerFromContext, configure_ollama

        configure_ollama()
        out = dspy.ChainOfThought(AnswerFromContext)(
            context="Anna has 3 apples. Ben gives her 2 more. Then she eats 1.",
            question="How many apples does Anna have now?",
        )
        assert "4" in out.answer
