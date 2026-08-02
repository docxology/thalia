"""Real DSPy runtime package — adapters, configuration, and opt-in live eval."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..compiler.metrics import token_f1
from .adapters import (
    DEFAULT_OLLAMA_BASE,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENROUTER_BASE,
    DEFAULT_OPENROUTER_MODEL,
    DSPY_AVAILABLE,
    ENV_OPENROUTER_KEY,
    format_dspy_completion,
    model_in_tags,
    ollama_model_available,
    ollama_model_metadata,
    ollama_model_metadata_from_tags,
    parse_input_fields,
    parse_output_fields,
    qa_metric,
    render_extractive_prompt,
)

if TYPE_CHECKING:
    from .live_eval import evaluate_backends, injection_resistance_neural
    from .runtime import (
        AnswerFromContext,
        ExtractiveDSPyLM,
        build_dataset,
        build_program,
        compile_program,
        configure,
        configure_ollama,
        configure_openrouter,
        held_out_optimizer_lift,
    )
__all__ = [
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_BASE",
    "DEFAULT_OPENROUTER_MODEL",
    "DEFAULT_OPENROUTER_BASE",
    "ENV_OPENROUTER_KEY",
    "DSPY_AVAILABLE",
    "parse_input_fields",
    "parse_output_fields",
    "render_extractive_prompt",
    "format_dspy_completion",
    "token_f1",
    "qa_metric",
    "model_in_tags",
    "ollama_model_metadata_from_tags",
    "ollama_model_metadata",
    "ollama_model_available",
    "ExtractiveDSPyLM",
    "AnswerFromContext",
    "configure",
    "configure_ollama",
    "configure_openrouter",
    "build_program",
    "build_dataset",
    "compile_program",
    "held_out_optimizer_lift",
    "injection_resistance_neural",
    "evaluate_backends",
]

_RUNTIME_EXPORTS = {
    "ExtractiveDSPyLM",
    "AnswerFromContext",
    "configure",
    "configure_ollama",
    "configure_openrouter",
    "build_program",
    "build_dataset",
    "compile_program",
    "held_out_optimizer_lift",
}
_LIVE_EXPORTS = {"injection_resistance_neural", "evaluate_backends"}


def __getattr__(name: str):
    """Load DSPy runtime code only when a runtime symbol is requested."""
    if name in _RUNTIME_EXPORTS:
        try:
            from . import runtime
        except ModuleNotFoundError as exc:  # pragma: no cover - minimal install
            if exc.name == "dspy":
                raise ImportError(
                    "The DSPy runtime requires the optional 'neural' extra; "
                    "install with `uv sync --extra neural`."
                ) from exc
            raise
        return getattr(runtime, name)
    if name in _LIVE_EXPORTS:
        try:
            from . import live_eval
        except ModuleNotFoundError as exc:  # pragma: no cover - minimal install
            if exc.name == "dspy":
                raise ImportError(
                    "Live DSPy evaluation requires the optional 'neural' extra; "
                    "install with `uv sync --extra neural`."
                ) from exc
            raise
        return getattr(live_eval, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
