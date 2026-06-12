"""Tests for the ATLAS query CLI (Zero-Mock)."""

import json

import pytest
from src.cli import build_parser, main, resolve_config, run_query
from src.config import default_config
from src.llm import CallableLM

SESSION = "User: my wifi password is bluefish42\nAssistant: noted"

_ENV_KEYS = (
    "ATLAS_TOP_K",
    "ATLAS_MAX_WINDOWS",
    "ATLAS_MAX_EVIDENCE",
    "ATLAS_RRF_K",
    "ATLAS_CONTEXT_BUDGET_TOKENS",
    "ATLAS_LEXICAL_WEIGHT",
    "ATLAS_SEMANTIC_WEIGHT",
    "ATLAS_ADAPTIVE_WINDOWS",
    "ATLAS_ADAPTIVE_WINDOW_RATIO",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class TestRunQuery:
    def test_returns_expected_keys(self):
        result = run_query("what is the wifi password", SESSION)
        for key in ("answer", "task_category", "delivery_mode", "citations", "ranked_evidence", "inspector_metadata"):
            assert key in result

    def test_grounds_in_history(self):
        result = run_query("what is the wifi password", SESSION)
        assert "wifi" in result["answer"].lower()

    def test_accepts_real_callable_lm(self):
        # A real (non-default) LM flows through run_query end-to-end.
        lm = CallableLM(lambda prompt: "FIXED-ANSWER")
        result = run_query("anything", SESSION, lm=lm)
        assert result["answer"] == "FIXED-ANSWER"


class TestOutputToDict:
    def test_serialisable(self):
        result = run_query("what is the wifi password", SESSION)
        json.dumps(result)  # must not raise


class TestParser:
    def test_query_required(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_parses_flags(self):
        args = build_parser().parse_args(["--query", "q", "--top-k", "3"])
        assert args.query == "q" and args.top_k == 3


class TestResolveConfig:
    def test_defaults(self):
        args = build_parser().parse_args(["--query", "q"])
        assert resolve_config(args) == default_config()

    def test_flag_override(self):
        args = build_parser().parse_args(["--query", "q", "--top-k", "2", "--max-evidence", "1"])
        cfg = resolve_config(args)
        assert cfg.top_k == 2 and cfg.max_evidence == 1

    def test_env_applied(self, monkeypatch):
        monkeypatch.setenv("ATLAS_TOP_K", "5")
        args = build_parser().parse_args(["--query", "q"])
        assert resolve_config(args).top_k == 5

    def test_flag_beats_env(self, monkeypatch):
        monkeypatch.setenv("ATLAS_TOP_K", "5")
        args = build_parser().parse_args(["--query", "q", "--top-k", "3"])
        assert resolve_config(args).top_k == 3

    def test_config_file(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("top_k: 6\n")
        args = build_parser().parse_args(["--query", "q", "--config", str(path)])
        assert resolve_config(args).top_k == 6


class TestMain:
    def test_json_output(self, capsys):
        code = main(["--query", "what is the wifi password", "--session-history", SESSION, "--json"])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert "answer" in payload

    def test_text_output(self, capsys):
        code = main(["--query", "what is the wifi password", "--session-history", SESSION])
        assert code == 0
        assert "answer:" in capsys.readouterr().out

    def test_session_file(self, tmp_path, capsys):
        path = tmp_path / "hist.txt"
        path.write_text(SESSION)
        code = main(["--query", "what is the wifi password", "--session-file", str(path)])
        assert code == 0
        assert "wifi" in capsys.readouterr().out.lower()


class TestExtendedParserFlags:
    _ENV_KEYS = (
        "ATLAS_RERANK",
        "ATLAS_MMR_LAMBDA",
        "ATLAS_VERIFY",
        "ATLAS_GROUNDING_THRESHOLD",
        "ATLAS_PARTITION_THRESHOLD",
        "ATLAS_PARTITION_SIZE",
        "ATLAS_QUERY_EXPANSION",
        "ATLAS_RECENCY_WEIGHT",
        "ATLAS_RECALL_MEMORY",
        "ATLAS_ADAPTIVE_WINDOWS",
        "ATLAS_ADAPTIVE_WINDOW_RATIO",
    )

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for key in self._ENV_KEYS:
            monkeypatch.delenv(key, raising=False)

    def test_rerank_choice(self):
        args = build_parser().parse_args(["--query", "q", "--rerank", "mmr"])
        assert args.rerank == "mmr"

    def test_rerank_rejects_invalid(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--query", "q", "--rerank", "turbo"])

    def test_verify_flag(self):
        args = build_parser().parse_args(["--query", "q", "--verify"])
        assert args.verify is True

    def test_rerank_override(self):
        args = build_parser().parse_args(["--query", "q", "--rerank", "mmr"])
        assert resolve_config(args).rerank == "mmr"

    def test_mmr_lambda_override(self):
        args = build_parser().parse_args(["--query", "q", "--mmr-lambda", "0.5"])
        assert resolve_config(args).mmr_lambda == 0.5

    def test_verify_override(self):
        args = build_parser().parse_args(["--query", "q", "--verify"])
        assert resolve_config(args).verify is True

    def test_query_expansion_flag(self):
        args = build_parser().parse_args(["--query", "q", "--query-expansion"])
        assert resolve_config(args).query_expansion is True

    def test_recency_weight_flag(self):
        args = build_parser().parse_args(["--query", "q", "--recency-weight", "0.5"])
        assert resolve_config(args).recency_weight == 0.5

    def test_recall_memory_flag(self):
        args = build_parser().parse_args(["--query", "q", "--recall-memory"])
        assert resolve_config(args).recall_memory is True

    def test_adaptive_window_flags(self):
        args = build_parser().parse_args(["--query", "q", "--adaptive-windows", "--adaptive-window-ratio", "9"])
        cfg = resolve_config(args)
        assert cfg.adaptive_windows is True
        assert cfg.adaptive_window_ratio == 9

    def test_adaptive_flags_beat_env(self, monkeypatch):
        monkeypatch.setenv("ATLAS_ADAPTIVE_WINDOWS", "false")
        monkeypatch.setenv("ATLAS_ADAPTIVE_WINDOW_RATIO", "4")
        args = build_parser().parse_args(["--query", "q", "--adaptive-windows", "--adaptive-window-ratio", "8"])
        cfg = resolve_config(args)
        assert cfg.adaptive_windows is True
        assert cfg.adaptive_window_ratio == 8
