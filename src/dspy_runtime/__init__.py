"""Real DSPy runtime package — adapters, configuration, and opt-in live eval."""

from __future__ import annotations

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
