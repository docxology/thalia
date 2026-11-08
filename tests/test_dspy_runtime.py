"""Tests for the real DSPy runtime (Zero-Mock).

The pure adapter helpers are tested directly. The real dspy glue — real
``dspy.Predict`` and a real ``dspy.BootstrapFewShot`` optimizer backed by the
project's real ExtractiveLM — runs when DSPy is installed. Live inference
additionally requires ``THALIA_LIVE_TESTS=1``. Nothing here is mocked.
"""

import os
from types import SimpleNamespace

import pytest

from src.dspy_runtime import (
    DEFAULT_OLLAMA_MODEL,
    DSPY_AVAILABLE,
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


@pytest.mark.skipif(not DSPY_AVAILABLE, reason="requires the optional DSPy extra")
class TestPersistentCacheBoundary:
    @pytest.mark.parametrize("configurator", ["configure", "configure_ollama", "configure_openrouter"])
    def test_configuring_backend_does_not_replay_persistent_cache(self, tmp_path, configurator):
        import dspy
        from src.dspy_runtime import runtime

        previous_cache, previous_lm = dspy.cache, dspy.settings.lm
        disk_cache = None
        request = {"model": "cache-boundary-test", "prompt": "source-owned synthetic request"}
        persisted = {"answer": "untrusted persisted answer"}
        current = {"answer": "current in-memory answer"}
        try:
            dspy.configure_cache(
                enable_disk_cache=True, enable_memory_cache=False, disk_cache_dir=str(tmp_path / "cache"),
            )
            disk_cache = dspy.cache
            disk_cache.put(request, persisted)
            # No memory cache: a hit here proves the fixture actually persisted.
            assert disk_cache.get(request) == persisted
            kwargs = {} if configurator == "configure" else {"api_base": "http://127.0.0.1:1"}
            if configurator == "configure_openrouter":
                kwargs["api_key"] = "public-noncredential-test-value"
            getattr(runtime, configurator)(**kwargs)  # Construction only; no model requests.
            assert dspy.cache.get(request) is None
            dspy.cache.put(request, current)
            assert dspy.cache.get(request) == current
            assert disk_cache.get(request) == persisted
        finally:
            if disk_cache is not None:
                disk_cache.disk_cache.close()
            dspy.cache = previous_cache
            dspy.configure(lm=previous_lm)


@pytest.mark.skipif(not DSPY_AVAILABLE, reason="requires the optional DSPy extra")
class TestLiveEvaluationAccounting:
    def test_balanced_subset_is_capacity_aware_and_deterministic(self):
        from collections import Counter

        from src.dspy_runtime.live_eval import _balanced_research_subset

        subset = _balanced_research_subset(7)
        repeat = _balanced_research_subset(7)
        assert [example.example_id for example in subset] == [example.example_id for example in repeat]
        counts = Counter(example.task_category for example in subset)
        assert len(subset) == 7
        assert max(counts.values()) - min(counts.values()) <= 1

    def test_balanced_subset_caps_at_available_examples(self):
        from src.dspy_runtime.live_eval import _balanced_research_subset

        assert len(_balanced_research_subset(10_000)) == 24

    @pytest.mark.parametrize("limit", [0, -1, True, 1.5])
    def test_balanced_subset_rejects_invalid_limits(self, limit):
        from src.dspy_runtime.live_eval import _balanced_research_subset

        with pytest.raises(ValueError, match="positive integer"):
            _balanced_research_subset(limit)


@pytest.mark.skipif(not DSPY_AVAILABLE, reason="requires the optional DSPy extra")
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
    not DSPY_AVAILABLE or os.environ.get("THALIA_LIVE_TESTS") != "1",
    reason=f"opt-in THALIA_LIVE_TESTS=1 and a running Ollama serving {DEFAULT_OLLAMA_MODEL}",
)
class TestRealNeuralDspy:
    """Exercises a REAL neural LLM (Gemma via Ollama) through real dspy. No mock."""

    def test_neural_probe_accounts_for_observed_poisoning(self):
        from src.dspy_runtime import injection_resistance_neural

        result = injection_resistance_neural()
        rows = result["rows"]
        assert result["n_probes"] == len(rows)
        assert result["neural_poison_rate"] == sum(row["neural_poisoned"] for row in rows) / len(rows)
        assert result["neural_correct_rate"] == sum(row["neural_correct"] for row in rows) / len(rows)

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
