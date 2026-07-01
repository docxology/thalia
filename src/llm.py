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
import os
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


DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
ENV_OPENROUTER_KEY = "THALIA_OPENROUTER_API_KEY"


class OpenRouterError(RuntimeError):
    """Raised when an OpenRouter API request fails."""


class OpenRouterLM:
    """Call the OpenRouter API over HTTP using only the standard library.

    Provides a real neural LLM backend for the Reasoner, usable anywhere without
    a local model server. The API key is read from the ``THALIA_OPENROUTER_API_KEY``
    environment variable.

    Args:
        model: OpenRouter model slug (default ``nvidia/nemotron-3-ultra-550b-a55b:free``).
        api_base: OpenRouter API base URL.
        api_key: API key (defaults to ``THALIA_OPENROUTER_API_KEY`` env var).
        timeout: Per-request timeout in seconds.
        temperature: Generation temperature (default 0.0 for reproducibility).
        max_tokens: Maximum tokens in the response.
    """

    def __init__(
        self,
        model: str = DEFAULT_OPENROUTER_MODEL,
        api_base: str = DEFAULT_OPENROUTER_BASE,
        api_key: str | None = None,
        timeout: float = 30.0,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> None:
        self.model = model
        self.api_base = api_base.rstrip("/")
        # Treat explicit api_key="" as "intentionally not set" — don't fall through to env.
        if api_key == "":
            self.api_key = ""
        else:
            self.api_key = api_key or os.environ.get(ENV_OPENROUTER_KEY, "")
        if not self.api_key:
            raise OpenRouterError(
                f"OpenRouter API key not set. Set the {ENV_OPENROUTER_KEY} environment variable "
                "or pass api_key explicitly."
            )
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        """Generate a completion for ``prompt`` from the OpenRouter API.

        Raises:
            OpenRouterError: On any transport error, API error, or malformed response.
        """
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc
        try:
            return str(body["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError(f"OpenRouter response missing expected fields: {body!r}") from exc

    def is_available(self) -> bool:
        """True when an API key is configured (no network probe; caller controls cost)."""
        return bool(self.api_key)


__all__ = [
    "CallableLM",
    "OllamaLM",
    "OllamaError",
    "OpenRouterLM",
    "OpenRouterError",
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OPENROUTER_BASE",
    "DEFAULT_OPENROUTER_MODEL",
    "ENV_OPENROUTER_KEY",
]
