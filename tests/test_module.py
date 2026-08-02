"""Tests for the Module / LM abstraction layer (Zero-Mock)."""

from typing import Any

import pytest
from src.module import (
    EVIDENCE_MARKER,
    QUESTION_MARKER,
    ExtractiveLM,
    Module,
    Predict,
    Prediction,
    render_signature_prompt,
    tokenize,
)
from src.signatures import InputField, OutputField, Signature


class TestTokenize:
    def test_lowercases_and_splits(self):
        assert tokenize("Hello, World 42!") == ["hello", "world", "42"]

    def test_empty(self):
        assert tokenize("") == []


class TestPrediction:
    def test_getattr(self):
        p = Prediction({"answer": "x"})
        assert p.answer == "x"

    def test_getitem(self):
        p = Prediction({"answer": "x"})
        assert p["answer"] == "x"

    def test_get_default(self):
        p = Prediction({"answer": "x"})
        assert p.get("missing", "d") == "d"

    def test_missing_attr_raises(self):
        p = Prediction({})
        with pytest.raises(AttributeError):
            _ = p.nope


class _QA(Signature):
    """Answer the question from the evidence."""

    query: str = InputField("the question")
    answer: str = OutputField("the answer")


class TestRenderPrompt:
    def test_contains_markers_and_evidence(self):
        prompt = render_signature_prompt(_QA, ["e1", "e2"], query="what?")
        assert EVIDENCE_MARKER in prompt
        assert QUESTION_MARKER in prompt
        assert "- e1" in prompt and "- e2" in prompt
        assert "what?" in prompt
        assert prompt.startswith("Answer the question from the evidence.")


class TestExtractiveLM:
    def test_picks_max_overlap_line(self):
        lm = ExtractiveLM()
        prompt = render_signature_prompt(
            _QA,
            ["the cat sat", "the wifi password is bluefish42", "a dog ran"],
            query="what is the wifi password",
        )
        assert "bluefish42" in lm.complete(prompt)

    def test_tie_break_prefers_shorter_line(self):
        lm = ExtractiveLM()
        # Both lines share the single token "alpha"; the shorter line wins.
        prompt = render_signature_prompt(
            _QA,
            ["alpha extra extra extra padding", "alpha short"],
            query="alpha",
        )
        assert lm.complete(prompt) == "alpha short"

    def test_no_evidence_echoes_prefix(self):
        lm = ExtractiveLM(max_chars=10)
        out = lm.complete("just some text with no markers")
        assert out == "just some "

    def test_split_handles_missing_question(self):
        lm = ExtractiveLM()
        prompt = f"instr\n\n{EVIDENCE_MARKER}\n- only evidence\n"
        # No QUESTION marker -> question empty -> first line returned.
        assert lm.complete(prompt) == "only evidence"


class TestPredict:
    def test_forward_returns_prediction(self):
        pred = Predict(_QA, lm=ExtractiveLM())
        result = pred.forward(evidence_texts=["the answer is 7"], query="what is the answer")
        assert "7" in result.answer
        assert "prompt" in result.values

    def test_forward_validates_inputs(self):
        pred = Predict(_QA)
        with pytest.raises(ValueError, match="missing required input"):
            pred.forward(evidence_texts=[])


class _Concrete(Module):
    def forward(self, *args: Any, **kwargs: Any) -> int:
        del kwargs
        return args[0] * 2


class TestModule:
    def test_call_delegates_to_forward(self):
        assert _Concrete()(3) == 6

    def test_base_forward_not_implemented(self):
        with pytest.raises(NotImplementedError):
            Module().forward()
