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


# DSPy 3.4 bundles lm15 but its adapters still dispatch messages=.
_CANONICAL_LM = tuple(int(part) for part in _dspy.__version__.split(".")[:2]) >= (3, 5)


def _extractive_completion(lm: LMClient, system: str, user: str) -> str:
    inputs = parse_input_fields(user)
    output_fields = parse_output_fields(system)
    answer = lm.complete(render_extractive_prompt(inputs))
    return format_dspy_completion(output_fields, answer)


class _ExtractiveEngine:
    """DSPy 3.5+ canonical engine; execution/cache ownership stays with DSPy."""

    def __init__(self, lm: LMClient) -> None:
        self.lm = lm

    def complete(self, request: Any) -> Any:
        from dspy.lm15 import Message, Response, Usage

        system = request.system or ""
        if not isinstance(system, str):
            system = "".join(part.text for part in system)
        user = "".join(message.text or "" for message in request.messages if message.role == "user")
        completion = _extractive_completion(self.lm, system, user)
        return Response(
            id=None, model=request.model, message=Message.assistant(completion),
            finish_reason="stop", usage=Usage(),
        )


class ExtractiveDSPyLM(_dspy.BaseLM):
    """A real ``dspy`` LM backed by the project's deterministic ExtractiveLM."""

    def __init__(self, lm: LMClient | None = None, model: str = "thalia-extractive") -> None:
        self.lm: LMClient = lm or ExtractiveLM()
        if _CANONICAL_LM:
            super().__init__(model=model, engine=_ExtractiveEngine(self.lm), num_retries=0)
        else:
            super().__init__(model=model)

    def __call__(
        self,
        prompt: Any = None,
        messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> Any:
        if _CANONICAL_LM:
            if messages is not None:
                raise TypeError("Canonical DSPy calls require a Request rather than messages=")
            return super().__call__(prompt, **kwargs)
        messages = messages or ([{"role": "user", "content": prompt}] if prompt else [])
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user = "".join(m["content"] for m in messages if m.get("role") == "user")
        return [_extractive_completion(self.lm, system, user)]


class AnswerFromContext(_dspy.Signature):
    """Answer the question using only the provided context."""

    context: str = _dspy.InputField(desc="Evidence the answer must be grounded in.")
    question: str = _dspy.InputField(desc="The question to answer.")
    answer: str = _dspy.OutputField(desc="The grounded answer span.")


def _configure_backend(lm: Any) -> Any:
    """Do not replay persistent, pickle-backed SDK cache entries."""
    _dspy.configure_cache(enable_disk_cache=False)
    _dspy.configure(lm=lm, adapter=_dspy.ChatAdapter())
    return lm


def configure(lm: LMClient | None = None) -> Any:
    """Configure the extractive adapter and disable persistent SDK caching."""
    backend = ExtractiveDSPyLM(lm=lm)
    return _configure_backend(backend)


def configure_ollama(
    model: str = DEFAULT_OLLAMA_MODEL,
    api_base: str = DEFAULT_OLLAMA_BASE,
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> Any:
    """Configure dspy.LM → LiteLLM → Ollama without persistent SDK caching."""
    lm = _dspy.LM(model=f"ollama_chat/{model}", api_base=api_base, api_key="", temperature=temperature, max_tokens=max_tokens)
    return _configure_backend(lm)


def configure_openrouter(
    model: str = DEFAULT_OPENROUTER_MODEL,
    api_base: str = DEFAULT_OPENROUTER_BASE,
    api_key: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> Any:
    """Configure dspy.LM → LiteLLM → OpenRouter without persistent SDK caching."""
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
    return _configure_backend(lm)


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
