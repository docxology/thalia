"""Module and language-model abstractions for the THALIA harness.

Mirrors the DSPy ``Module`` / ``Predict`` shape and exposes a small
``complete(prompt: str) -> str`` language-model protocol, while keeping a fully
deterministic default so the pipeline runs and is tested without any network call.

* :class:`Module` — composable stage with ``forward`` / ``__call__``.
* :class:`Prediction` — attribute bag returned by a module (DSPy ``Prediction``).
* :class:`LMClient` — protocol matching ``complete(prompt: str) -> str``.
* :class:`ExtractiveLM` — deterministic default LM: returns the evidence span with
  maximum lexical overlap with the question. A real LLM adapter implements the same
  ``complete`` method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Protocol, runtime_checkable

from .signatures import Field, FieldKind, Signature

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Prompt section markers used by the deterministic responder. They are stable so
# the extractive parser and the prompt renderer stay in lock-step.
EVIDENCE_MARKER = "### EVIDENCE"
QUESTION_MARKER = "### QUESTION"


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenization shared across retrieval + reasoning."""
    return _TOKEN_RE.findall(text.lower())


@dataclass
class Prediction:
    """Attribute bag returned by a module (DSPy-compatible ``Prediction``)."""

    values: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - thin delegation
        try:
            return self.values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, name: str) -> Any:
        return self.values[name]

    def get(self, name: str, default: Any = None) -> Any:
        """Dict-style access with a default."""
        return self.values.get(name, default)


@runtime_checkable
class LMClient(Protocol):
    """One-method language-model interface used by the Reasoner."""

    def complete(self, prompt: str) -> str:
        """Return a completion for ``prompt``."""
        ...


class ExtractiveLM:
    """Deterministic, network-free language model.

    The completion is the line of the prompt's EVIDENCE block with the greatest
    token overlap with the QUESTION block. With no evidence it echoes a trimmed
    prefix of the prompt. This makes every downstream stage testable and
    reproducible; swap in a real LM by passing any object with ``complete``.
    """

    def __init__(self, max_chars: int = 240) -> None:
        self.max_chars = max_chars

    def complete(self, prompt: str) -> str:
        """Return the best-overlapping evidence line for the embedded question."""
        evidence, question = self._split(prompt)
        if not evidence:
            return prompt.strip()[: self.max_chars]

        q_tokens = set(tokenize(question))
        best_line = evidence[0]
        best_score = -1.0
        for line in evidence:
            line_tokens = set(tokenize(line))
            if not line_tokens:
                continue
            overlap = len(q_tokens & line_tokens)
            # Tie-break deterministically on shorter (more specific) lines.
            score = overlap - 1e-3 * len(line_tokens)
            if score > best_score:
                best_score = score
                best_line = line
        return best_line.strip()[: self.max_chars]

    @staticmethod
    def _split(prompt: str) -> tuple[list[str], str]:
        """Split a rendered prompt into (evidence_lines, question_text)."""
        evidence_lines: list[str] = []
        question = ""
        if EVIDENCE_MARKER in prompt:
            after = prompt.split(EVIDENCE_MARKER, 1)[1]
            evidence_block = after.split(QUESTION_MARKER, 1)[0]
            evidence_lines = [ln.strip(" -\t") for ln in evidence_block.splitlines() if ln.strip(" -\t")]
        if QUESTION_MARKER in prompt:
            question = prompt.split(QUESTION_MARKER, 1)[1].strip()
        return evidence_lines, question


def render_signature_prompt(
    signature: type[Signature],
    evidence_texts: list[str],
    **inputs: Any,
) -> str:
    """Render a deterministic prompt from a signature, evidence, and inputs.

    The layout places the instruction first, then the evidence block, then the
    question — the exact structure :class:`ExtractiveLM` parses.

    Args:
        signature: The stage signature providing the instruction text.
        evidence_texts: Evidence excerpts to embed (verbatim).
        **inputs: Named inputs; a ``query`` input becomes the QUESTION block.

    Returns:
        A rendered prompt string.
    """
    lines = [signature.instructions(), ""]
    lines.append(EVIDENCE_MARKER)
    for text in evidence_texts:
        lines.append(f"- {text}")
    lines.append("")
    lines.append(QUESTION_MARKER)
    lines.append(str(inputs.get("query", "")))
    return "\n".join(lines)


class Module:
    """Base class for composable pipeline stages (DSPy-compatible ``Module``)."""

    def forward(self, **kwargs: Any) -> Any:
        """Execute the stage. Subclasses override this."""
        raise NotImplementedError

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.forward(*args, **kwargs)


class Predict(Module):
    """Single-shot prediction over a signature using an :class:`LMClient`.

    A light analogue of ``dspy.Predict``: it validates inputs against the
    signature, renders a prompt, and returns the raw completion in a
    :class:`Prediction` keyed by the signature's first output field.
    """

    def __init__(self, signature: type[Signature], lm: LMClient | None = None) -> None:
        self.signature = signature
        self.lm: LMClient = lm or ExtractiveLM()

    def forward(self, evidence_texts: list[str] | None = None, **inputs: Any) -> Prediction:
        self.signature.validate_inputs(**inputs)
        prompt = render_signature_prompt(self.signature, evidence_texts or [], **inputs)
        completion = self.lm.complete(prompt)
        output_fields = list(self.signature.outputs())
        primary = output_fields[0] if output_fields else "answer"
        return Prediction({primary: completion, "prompt": prompt})


__all__ = [
    "tokenize",
    "Prediction",
    "LMClient",
    "ExtractiveLM",
    "render_signature_prompt",
    "Module",
    "Predict",
    "EVIDENCE_MARKER",
    "QUESTION_MARKER",
    "Field",
    "FieldKind",
]
