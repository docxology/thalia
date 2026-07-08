"""Pure DSPy adapter helpers and Ollama network probes."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from ..compiler.metrics import token_f1
from ..module import EVIDENCE_MARKER, QUESTION_MARKER

DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_OLLAMA_BASE = "http://localhost:11434"
DEFAULT_OPENROUTER_MODEL = "openrouter/tencent/hy3-preview"
DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
ENV_OPENROUTER_KEY = "THALIA_OPENROUTER_API_KEY"

DSPY_AVAILABLE = True

_FIELD_RE = re.compile(r"\[\[ ## (\w+) ## \]\]")
_QUESTION_FIELDS = ("question", "query")


def parse_input_fields(user_message: str) -> dict[str, str]:
    """Parse dspy's ``[[ ## name ## ]]\\n<value>`` blocks from a user message."""
    body = user_message.split("Respond with")[0]
    parts = _FIELD_RE.split(body)
    fields: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        fields[parts[i]] = parts[i + 1].strip()
    return fields


def parse_output_fields(system_message: str) -> list[str]:
    """Parse the requested output field names from dspy's system message."""
    segment = system_message.split("Your output fields are:", 1)[-1].split("All interactions", 1)[0]
    return re.findall(r"`(\w+)`", segment)


def render_extractive_prompt(inputs: dict[str, str]) -> str:
    """Render dspy inputs into the EVIDENCE/QUESTION prompt ExtractiveLM parses."""
    question = ""
    evidence: list[str] = []
    for name, value in inputs.items():
        if name in _QUESTION_FIELDS:
            question = value
            continue
        for line in re.split(r"(?<=[.!?])\s+|\n+", value):
            if line.strip():
                evidence.append(line.strip())
    if not question and inputs:
        question = list(inputs.values())[-1]
    body = "\n".join(f"- {line}" for line in evidence)
    return f"{EVIDENCE_MARKER}\n{body}\n\n{QUESTION_MARKER}\n{question}"


def format_dspy_completion(output_fields: list[str], answer: str) -> str:
    """Wrap an extracted answer in dspy's field-delimited completion format."""
    fields = output_fields or ["answer"]
    blocks = [f"[[ ## {field} ## ]]\n{answer}" for field in fields]
    blocks.append("[[ ## completed ## ]]")
    return "\n\n".join(blocks)


def qa_metric(example: Any, prediction: Any, trace: Any = None) -> bool:
    """Real evaluation metric for the dspy optimizer: token-F1 >= 0.5."""
    return token_f1(getattr(prediction, "answer", "") or "", getattr(example, "answer", "") or "") >= 0.5


def model_in_tags(tags: dict, model: str) -> bool:
    """Pure: True when an Ollama ``/api/tags`` payload lists ``model``."""
    wanted = {model, f"{model}:latest"} if ":" not in model else {model}
    return any(entry.get("name") in wanted or entry.get("model") in wanted for entry in tags.get("models", []))


def ollama_model_metadata_from_tags(tags: dict, model: str) -> dict:
    """Pure Ollama tag parser for provenance fields."""
    wanted = {model, f"{model}:latest"} if ":" not in model else {model}
    for entry in tags.get("models", []):
        if entry.get("name") in wanted or entry.get("model") in wanted:
            return {
                "requested_model": model,
                "model": entry.get("name") or entry.get("model") or model,
                "digest": entry.get("digest"),
                "modified_at": entry.get("modified_at"),
                "size": entry.get("size"),
                "details": entry.get("details", {}),
                "available": True,
            }
    return {
        "requested_model": model,
        "model": model,
        "digest": None,
        "modified_at": None,
        "size": None,
        "details": {},
        "available": False,
    }


def ollama_model_metadata(model: str = DEFAULT_OLLAMA_MODEL, api_base: str = DEFAULT_OLLAMA_BASE) -> dict:  # pragma: no cover
    """Return best-effort Ollama model/runtime provenance."""
    try:
        with urllib.request.urlopen(f"{api_base}/api/tags", timeout=3) as resp:
            metadata = ollama_model_metadata_from_tags(json.load(resp), model)
    except Exception as exc:
        metadata = ollama_model_metadata_from_tags({}, model)
        metadata["error"] = f"{type(exc).__name__}: {exc}"
    metadata["api_base"] = api_base
    try:
        with urllib.request.urlopen(f"{api_base}/api/version", timeout=3) as resp:
            version = json.load(resp)
        metadata["ollama_version"] = version.get("version")
    except Exception:
        metadata["ollama_version"] = None
    return metadata


def ollama_model_available(model: str = DEFAULT_OLLAMA_MODEL, api_base: str = DEFAULT_OLLAMA_BASE) -> bool:  # pragma: no cover
    """Real probe: True when Ollama lists ``model`` and generation succeeds."""
    try:
        if not ollama_model_metadata(model=model, api_base=api_base).get("available"):
            return False
        payload = json.dumps(
            {
                "model": model,
                "prompt": "Reply with ok.",
                "stream": False,
                "options": {"temperature": 0.0},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{api_base}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return isinstance(body.get("response"), str)
    except Exception:
        return False


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
    "qa_metric",
    "model_in_tags",
    "ollama_model_metadata_from_tags",
    "ollama_model_metadata",
    "ollama_model_available",
]
