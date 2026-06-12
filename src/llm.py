"""Real, swappable language-model adapters for the Reasoner.

The deterministic core uses :class:`src.module.ExtractiveLM`. These adapters make
the harness *genuinely* usable with a real model while preserving the one-method
``LMClient`` protocol (``complete(prompt) -> str``):

* :class:`CallableLM` — wrap any ``Callable[[str], str]`` (an SDK call, a local
  function) as an LM. Trivially real and testable.
* :class:`OllamaLM` — call a local Ollama server over HTTP via the standard
  library (no third-party dependency). Opt-in; never invoked by the default core.

Failures are raised, never silently swallowed: a broken model call must surface,
not degrade into an empty answer.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"


class CallableLM:
    """Adapt any ``Callable[[str], str]`` to the ``LMClient`` protocol.

    Example:
        >>> lm = CallableLM(lambda prompt: prompt.upper())
        >>> lm.complete("hi")
        'HI'
    """

    def __init__(self, fn: Callable[[str], str]) -> None:
        if not callable(fn):
            raise TypeError("CallableLM requires a callable")
        self._fn = fn

    def complete(self, prompt: str) -> str:
        """Return ``fn(prompt)`` coerced to a string."""
        return str(self._fn(prompt))


class OllamaLM:
    """Call a local Ollama server's ``/api/generate`` endpoint over HTTP.

    Uses only the standard library. Opt-in: construct one and pass it as ``lm=`` to
    the Reasoner or AutoHarness. Network errors raise :class:`OllamaError` rather
    than degrading silently.

    Args:
        model: Ollama model name (default ``gemma3:4b``).
        host: Base URL of the Ollama server (default ``http://localhost:11434``).
        timeout: Per-request timeout in seconds.
        options: Optional Ollama generation options (e.g. ``{"temperature": 0}``).
    """

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        host: str = DEFAULT_OLLAMA_HOST,
        timeout: float = 30.0,
        options: dict | None = None,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.options = options or {"temperature": 0.0}

    def complete(self, prompt: str) -> str:
        """Generate a completion for ``prompt`` from the Ollama server.

        Raises:
            OllamaError: On any transport error or malformed response.
        """
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": self.options,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise OllamaError(f"Ollama request to {self.host} failed: {exc}") from exc
        if "response" not in body:
            raise OllamaError(f"Ollama response missing 'response' field: {body!r}")
        return str(body["response"]).strip()

    def is_available(self) -> bool:
        """Best-effort liveness probe of the Ollama server (False on any error)."""
        try:
            request = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return bool(200 <= response.status < 300)
        except (urllib.error.URLError, OSError):
            return False


class OllamaError(RuntimeError):
    """Raised when an Ollama request fails or returns a malformed response."""


__all__ = [
    "CallableLM",
    "OllamaLM",
    "OllamaError",
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_MODEL",
]
