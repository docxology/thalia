"""Real DSPy runtime configuration and program builders."""

from __future__ import annotations

import os
from typing import Any

import dspy as _dspy

from ..compiler.metrics import token_f1
from ..module import ExtractiveLM, LMClient
from .adapters import (
    DEFAULT_OLLAMA_BASE,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENROUTER_BASE,
    DEFAULT_OPENROUTER_MODEL,
    ENV_OPENROUTER_KEY,
    format_dspy_completion,
    parse_input_fields,
    parse_output_fields,
    qa_metric,
    render_extractive_prompt,
)


class ExtractiveDSPyLM(_dspy.BaseLM):
    """A real ``dspy`` LM backed by the project's deterministic ExtractiveLM."""

    def __init__(self, lm: LMClient | None = None, model: str = "thalia-extractive") -> None:
        super().__init__(model=model)
        self.lm: LMClient = lm or ExtractiveLM()

    def __call__(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any] | str]:
        messages = messages or ([{"role": "user", "content": prompt}] if prompt else [])
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user = "".join(m["content"] for m in messages if m.get("role") == "user")
        inputs = parse_input_fields(user)
        output_fields = parse_output_fields(system)
        answer = self.lm.complete(render_extractive_prompt(inputs))
        return [format_dspy_completion(output_fields, answer)]


class AnswerFromContext(_dspy.Signature):
    """Answer the question using only the provided context."""

    context: str = _dspy.InputField(desc="Evidence the answer must be grounded in.")
    question: str = _dspy.InputField(desc="The question to answer.")
    answer: str = _dspy.OutputField(desc="The grounded answer span.")


def configure(lm: LMClient | None = None) -> Any:
    """Configure dspy globally with the real ExtractiveLM-backed adapter."""
    backend = ExtractiveDSPyLM(lm=lm)
    _dspy.configure(lm=backend)
    return backend


def configure_ollama(
    model: str = DEFAULT_OLLAMA_MODEL,
    api_base: str = DEFAULT_OLLAMA_BASE,
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> Any:
    """Configure dspy with a real neural LLM via ``dspy.LM`` → litellm → Ollama."""
    lm = _dspy.LM(model=f"ollama_chat/{model}", api_base=api_base, api_key="", temperature=temperature, max_tokens=max_tokens)
    _dspy.configure(lm=lm)
    return lm


def configure_openrouter(
    model: str = DEFAULT_OPENROUTER_MODEL,
    api_base: str = DEFAULT_OPENROUTER_BASE,
    api_key: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> Any:
    """Configure dspy with a real neural LLM via dspy.LM → litellm → OpenRouter."""
    key = api_key or os.environ.get(ENV_OPENROUTER_KEY, "")
    if not key:
        raise RuntimeError(
            f"OpenRouter API key not set. Set the {ENV_OPENROUTER_KEY} environment variable "
            "or pass api_key= to configure_openrouter()."
        )
    lm = _dspy.LM(
        model=model,
        api_base=api_base,
        api_key=key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    _dspy.configure(lm=lm)
    return lm


def build_program() -> Any:
    """Return a real ``dspy.Predict`` program over :class:`AnswerFromContext`."""
    return _dspy.Predict(AnswerFromContext)


def build_dataset(limit: int | None = None) -> list:
    """Build real ``dspy.Example`` training data from the project's demo dataset."""
    from ..evaluation import build_demo_dataset

    examples = []
    for ex in build_demo_dataset()[:limit]:
        examples.append(
            _dspy.Example(context=ex.session_history, question=ex.query, answer=ex.expected_answer).with_inputs(
                "context", "question"
            )
        )
    return examples


def compile_program(program: Any = None, trainset: list | None = None, max_demos: int = 4) -> Any:
    """Run a REAL dspy optimizer (``BootstrapFewShot``) over the program."""
    configure()
    program = program or build_program()
    trainset = trainset if trainset is not None else build_dataset()
    optimizer = _dspy.BootstrapFewShot(metric=qa_metric, max_bootstrapped_demos=max_demos, max_labeled_demos=max_demos)
    return optimizer.compile(program, trainset=trainset)


def held_out_optimizer_lift(train_size: int = 4) -> dict:
    """Measure optimizer lift on a held-out split (extractive backend)."""
    configure()
    data = build_dataset()
    train, test = data[:train_size], data[train_size:]
    uncompiled = build_program()
    before = sum(qa_metric(ex, uncompiled(**ex.inputs())) for ex in test) / len(test)
    compiled = compile_program(program=build_program(), trainset=train)
    after = sum(qa_metric(ex, compiled(**ex.inputs())) for ex in test) / len(test)
    return {"train_size": len(train), "test_size": len(test), "before": before, "after": after, "lift": after - before}


__all__ = [
    "ExtractiveDSPyLM",
    "AnswerFromContext",
    "configure",
    "configure_ollama",
    "configure_openrouter",
    "build_program",
    "build_dataset",
    "compile_program",
    "held_out_optimizer_lift",
    "token_f1",
]
