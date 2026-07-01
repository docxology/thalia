"""Tests for the real LM adapters (Zero-Mock; uses a real in-process HTTP server)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from src.llm import CallableLM, OllamaError, OllamaLM, OpenRouterError, OpenRouterLM

# A port that is essentially always closed -> connection-refused for error paths.
CLOSED_URL = "http://127.0.0.1:1"


def _make_handler(state):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence test server logging
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self._send(200, state["generate"])

        def do_GET(self):
            self._send(200, {"models": state.get("models", [])})

    return _Handler


@pytest.fixture
def ollama_server():
    """Start a real HTTP server emulating Ollama; yield (url, mutable state)."""
    state = {"generate": {"response": "stub answer"}, "models": []}
    server = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", state
    finally:
        server.shutdown()
        server.server_close()


class TestCallableLM:
    def test_wraps_callable(self):
        lm = CallableLM(lambda p: p.upper())
        assert lm.complete("hi") == "HI"

    def test_coerces_non_string(self):
        lm = CallableLM(lambda p: 42)
        assert lm.complete("x") == "42"

    def test_non_callable_raises(self):
        with pytest.raises(TypeError, match="requires a callable"):
            CallableLM("not callable")


class TestOllamaLM:
    def test_complete_returns_response(self, ollama_server):
        url, _ = ollama_server
        lm = OllamaLM(host=url, timeout=5)
        assert lm.complete("hello") == "stub answer"

    def test_complete_strips_whitespace(self, ollama_server):
        url, state = ollama_server
        state["generate"] = {"response": "  padded  "}
        lm = OllamaLM(host=url, timeout=5)
        assert lm.complete("x") == "padded"

    def test_missing_response_field_raises(self, ollama_server):
        url, state = ollama_server
        state["generate"] = {"unexpected": "shape"}
        lm = OllamaLM(host=url, timeout=5)
        with pytest.raises(OllamaError, match="missing 'response'"):
            lm.complete("x")

    def test_connection_error_raises(self):
        lm = OllamaLM(host=CLOSED_URL, timeout=1)
        with pytest.raises(OllamaError, match="failed"):
            lm.complete("x")

    def test_is_available_true(self, ollama_server):
        url, _ = ollama_server
        assert OllamaLM(host=url, timeout=5).is_available() is True

    def test_is_available_false_on_closed_port(self):
        assert OllamaLM(host=CLOSED_URL, timeout=1).is_available() is False

    def test_host_trailing_slash_normalised(self):
        assert OllamaLM(host="http://localhost:11434/").host == "http://localhost:11434"


class TestOpenRouterLM:
    def test_complete_returns_response(self, httpserver):
        """Real HTTP server: OpenRouterLM parses the chat completions response."""
        httpserver.expect_request("/chat/completions", method="POST").respond_with_json(
            {"choices": [{"message": {"content": "bluefish42"}}]}
        )
        lm = OpenRouterLM(api_key="test-key", api_base=httpserver.url_for(""), timeout=5)
        assert lm.complete("what is the wifi password?") == "bluefish42"

    def test_complete_strips_whitespace(self, httpserver):
        """OpenRouterLM strips whitespace from the response content."""
        httpserver.expect_request("/chat/completions", method="POST").respond_with_json(
            {"choices": [{"message": {"content": "  bluefish42  "}}]}
        )
        lm = OpenRouterLM(api_key="test-key", api_base=httpserver.url_for(""), timeout=5)
        assert lm.complete("what is the wifi password?") == "bluefish42"

    def test_missing_choices_field_raises(self, httpserver):
        """Malformed response without choices raises OpenRouterError."""
        httpserver.expect_request("/chat/completions", method="POST").respond_with_json(
            {"unexpected": "shape"}
        )
        lm = OpenRouterLM(api_key="test-key", api_base=httpserver.url_for(""), timeout=5)
        with pytest.raises(OpenRouterError, match="missing expected fields"):
            lm.complete("x")

    def test_empty_choices_array_raises(self, httpserver):
        """Empty choices array raises OpenRouterError."""
        httpserver.expect_request("/chat/completions", method="POST").respond_with_json(
            {"choices": []}
        )
        lm = OpenRouterLM(api_key="test-key", api_base=httpserver.url_for(""), timeout=5)
        with pytest.raises(OpenRouterError, match="missing expected fields"):
            lm.complete("x")

    def test_no_api_key_raises(self):
        """OpenRouterLM raises when no API key is available."""
        with pytest.raises(OpenRouterError, match="API key not set"):
            OpenRouterLM(api_key="")

    def test_is_available_returns_true_with_key(self):
        """is_available is True when an API key is configured."""
        assert OpenRouterLM(api_key="key").is_available() is True

    def test_sends_correct_headers(self, httpserver):
        """OpenRouterLM sends the API key in the Authorization header."""
        httpserver.expect_request(
            "/chat/completions",
            method="POST",
            headers={"Authorization": "Bearer test-key-sent"},
        ).respond_with_json({"choices": [{"message": {"content": "ok"}}]})
        lm = OpenRouterLM(api_key="test-key-sent", api_base=httpserver.url_for(""), timeout=5)
        assert lm.complete("x") == "ok"
