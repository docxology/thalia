"""Tests for config serialisation, file loading, and env overrides (Zero-Mock)."""

import pytest
from src.config import (
    HarnessConfig,
    apply_env_overrides,
    default_config,
    load_config,
    save_config,
)

_ENV_KEYS = (
    "THALIA_TOP_K",
    "THALIA_MAX_WINDOWS",
    "THALIA_MAX_EVIDENCE",
    "THALIA_RRF_K",
    "THALIA_CONTEXT_BUDGET_TOKENS",
    "THALIA_LEXICAL_WEIGHT",
    "THALIA_SEMANTIC_WEIGHT",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure no THALIA_* env vars leak into a test from the surrounding shell."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class TestDictRoundTrip:
    def test_to_dict_has_all_fields(self):
        d = default_config().to_dict()
        assert set(d) >= {"top_k", "max_windows", "max_evidence", "rrf_k"}

    def test_from_dict_round_trip(self):
        cfg = HarnessConfig(top_k=4, max_evidence=3)
        assert HarnessConfig.from_dict(cfg.to_dict()) == cfg

    def test_from_dict_ignores_unknown_keys(self):
        cfg = HarnessConfig.from_dict({"top_k": 5, "bogus": 99})
        assert cfg.top_k == 5

    @pytest.mark.parametrize(
        "field, value",
        [("top_k", True), ("max_windows", 2.5), ("rrf_k", 1.5), ("recall_limit", False)],
    )
    def test_rejects_non_integral_integer_fields(self, field, value):
        with pytest.raises(ValueError, match=field):
            HarnessConfig(**{field: value})

    def test_rejects_non_finite_weights(self):
        with pytest.raises(ValueError, match="lexical_weight"):
            HarnessConfig(lexical_weight=float("nan"), semantic_weight=0.5)

    def test_rejects_non_boolean_flags(self):
        with pytest.raises(ValueError, match="verify"):
            HarnessConfig(verify=1)  # pyright: ignore[reportArgumentType] - invalid input contract


class TestEnvOverrides:
    def test_no_env_returns_same(self):
        cfg = default_config()
        assert apply_env_overrides(cfg) == cfg

    def test_int_override(self, monkeypatch):
        monkeypatch.setenv("THALIA_TOP_K", "3")
        assert apply_env_overrides(default_config()).top_k == 3

    def test_weight_pair_override(self, monkeypatch):
        monkeypatch.setenv("THALIA_LEXICAL_WEIGHT", "0.8")
        monkeypatch.setenv("THALIA_SEMANTIC_WEIGHT", "0.2")
        cfg = apply_env_overrides(default_config())
        assert cfg.lexical_weight == 0.8 and cfg.semantic_weight == 0.2

    def test_single_weight_override_raises(self, monkeypatch):
        monkeypatch.setenv("THALIA_LEXICAL_WEIGHT", "0.8")
        with pytest.raises(ValueError, match="both be set or both None"):
            apply_env_overrides(default_config())

    def test_invalid_value_raises(self, monkeypatch):
        monkeypatch.setenv("THALIA_TOP_K", "not-an-int")
        with pytest.raises(ValueError, match="not a valid int"):
            apply_env_overrides(default_config())


class TestFileLoad:
    def test_load_flat_yaml(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("top_k: 4\nmax_evidence: 3\n")
        cfg = load_config(path)
        assert cfg.top_k == 4 and cfg.max_evidence == 3

    def test_load_harness_keyed_yaml(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("harness:\n  top_k: 2\n  max_windows: 9\n")
        cfg = load_config(path)
        assert cfg.top_k == 2 and cfg.max_windows == 9

    def test_load_applies_env(self, tmp_path, monkeypatch):
        path = tmp_path / "c.yaml"
        path.write_text("top_k: 4\n")
        monkeypatch.setenv("THALIA_TOP_K", "7")
        assert load_config(path).top_k == 7

    def test_load_no_env_when_disabled(self, tmp_path, monkeypatch):
        path = tmp_path / "c.yaml"
        path.write_text("top_k: 4\n")
        monkeypatch.setenv("THALIA_TOP_K", "7")
        assert load_config(path, apply_env=False).top_k == 4

    def test_non_mapping_raises(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("- a\n- b\n")
        with pytest.raises(ValueError, match="must contain a mapping"):
            load_config(path)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nope.yaml")

    def test_repo_config_file_loads(self):
        # The shipped config/harness.yaml round-trips to the default config.
        from pathlib import Path

        repo_config = Path(__file__).resolve().parent.parent / "config" / "harness.yaml"
        cfg = load_config(repo_config)
        assert cfg == default_config()


class TestSave:
    def test_save_round_trip(self, tmp_path):
        cfg = HarnessConfig(top_k=6, max_evidence=4)
        out = save_config(cfg, tmp_path / "out.yaml")
        assert out.exists()
        assert load_config(out, apply_env=False) == cfg

    def test_save_creates_parent_dir(self, tmp_path):
        out = save_config(default_config(), tmp_path / "nested" / "c.yaml")
        assert out.exists()
