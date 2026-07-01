"""Tests for the HarnessConfig parameter object (Zero-Mock)."""

import pytest
from src.config import HarnessConfig, default_config


class TestValidation:
    def test_default_is_valid(self):
        cfg = default_config()
        assert cfg.top_k == 8 and cfg.max_windows == 15

    def test_non_positive_max_windows(self):
        with pytest.raises(ValueError, match="max_windows must be positive"):
            HarnessConfig(max_windows=0)

    def test_non_positive_top_k(self):
        with pytest.raises(ValueError, match="top_k must be positive"):
            HarnessConfig(top_k=0)

    def test_negative_rrf_k(self):
        with pytest.raises(ValueError, match="rrf_k must be non-negative"):
            HarnessConfig(rrf_k=-1)

    def test_non_positive_max_evidence(self):
        with pytest.raises(ValueError, match="max_evidence must be positive"):
            HarnessConfig(max_evidence=0)

    def test_non_positive_budget(self):
        with pytest.raises(ValueError, match="context_budget_tokens must be positive"):
            HarnessConfig(context_budget_tokens=0)

    def test_one_weight_set_raises(self):
        with pytest.raises(ValueError, match="both be set or both None"):
            HarnessConfig(lexical_weight=0.6)

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="lane weights must be non-negative"):
            HarnessConfig(lexical_weight=-0.1, semantic_weight=0.5)

    def test_both_weights_set_ok(self):
        cfg = HarnessConfig(lexical_weight=0.7, semantic_weight=0.3)
        assert cfg.lexical_weight == 0.7


class TestWith:
    def test_with_replaces_field(self):
        cfg = default_config().with_(top_k=4)
        assert cfg.top_k == 4
        assert cfg.max_windows == 15  # unchanged

    def test_with_validates(self):
        with pytest.raises(ValueError):
            default_config().with_(top_k=-5)

    def test_frozen_hashable(self):
        # Frozen dataclasses are hashable -> usable as dict keys / in sets.
        assert len({default_config(), default_config()}) == 1

    def test_bad_rerank_raises(self):
        with pytest.raises(ValueError, match="rerank must be one of"):
            HarnessConfig(rerank="turbo")

    def test_mmr_lambda_range(self):
        with pytest.raises(ValueError, match="mmr_lambda must be in"):
            HarnessConfig(mmr_lambda=1.5)

    def test_grounding_threshold_range(self):
        with pytest.raises(ValueError, match="grounding_threshold must be in"):
            HarnessConfig(grounding_threshold=-0.1)

    def test_partition_threshold_positive(self):
        with pytest.raises(ValueError, match="partition_threshold must be positive"):
            HarnessConfig(partition_threshold=0)

    def test_partition_size_positive(self):
        with pytest.raises(ValueError, match="partition_size must be positive"):
            HarnessConfig(partition_size=0)

    def test_expansion_terms_positive(self):
        with pytest.raises(ValueError, match="expansion_terms must be positive"):
            HarnessConfig(expansion_terms=0)

    def test_recency_weight_range(self):
        with pytest.raises(ValueError, match="recency_weight must be in"):
            HarnessConfig(recency_weight=-0.1)

    def test_recall_limit_positive(self):
        with pytest.raises(ValueError, match="recall_limit must be positive"):
            HarnessConfig(recall_limit=0)

    def test_adaptive_defaults(self):
        cfg = default_config()
        assert cfg.rerank == "rrf" and cfg.verify is False and cfg.mmr_lambda == 0.7
        assert cfg.query_expansion is False and cfg.recency_weight == 0.0
        assert cfg.recall_memory is False and cfg.recall_limit == 3

    def test_adaptive_window_ratio_non_positive_raises(self):
        with pytest.raises(ValueError, match="adaptive_window_ratio must be positive"):
            HarnessConfig(adaptive_window_ratio=0)

    def test_adaptive_window_ratio_negative_raises(self):
        with pytest.raises(ValueError, match="adaptive_window_ratio must be positive"):
            HarnessConfig(adaptive_window_ratio=-1)


class TestValidateMethod:
    """Tests for HarnessConfig.validate() (the explicit re-validation helper)."""

    def test_validate_passes_on_default_config(self):
        cfg = default_config()
        cfg.validate()  # must not raise

    def test_validate_detects_bypassed_construction_constraint(self):
        """validate() catches invariant violations introduced after construction via object.__setattr__."""
        cfg = default_config()
        # Bypass frozen dataclass enforcement to simulate a deserialised/patched config.
        object.__setattr__(cfg, "adaptive_window_ratio", 0)
        with pytest.raises(ValueError, match="adaptive_window_ratio must be positive"):
            cfg.validate()


class TestEnvOverrides:
    _ENV_KEYS = (
        "THALIA_RERANK",
        "THALIA_MMR_LAMBDA",
        "THALIA_VERIFY",
        "THALIA_GROUNDING_THRESHOLD",
        "THALIA_PARTITION_THRESHOLD",
        "THALIA_PARTITION_SIZE",
        "THALIA_QUERY_EXPANSION",
        "THALIA_EXPANSION_TERMS",
        "THALIA_RECENCY_WEIGHT",
        "THALIA_RECALL_MEMORY",
        "THALIA_RECALL_LIMIT",
        "THALIA_ADAPTIVE_WINDOWS",
        "THALIA_ADAPTIVE_WINDOW_RATIO",
    )

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for key in self._ENV_KEYS:
            monkeypatch.delenv(key, raising=False)

    def test_rerank_env(self, monkeypatch):
        monkeypatch.setenv("THALIA_RERANK", "mmr")
        from src.config import apply_env_overrides

        assert apply_env_overrides(default_config()).rerank == "mmr"

    def test_verify_env_true(self, monkeypatch):
        monkeypatch.setenv("THALIA_VERIFY", "true")
        from src.config import apply_env_overrides

        assert apply_env_overrides(default_config()).verify is True

    def test_verify_env_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("THALIA_VERIFY", "maybe")
        from src.config import apply_env_overrides

        with pytest.raises(ValueError, match="not a valid"):
            apply_env_overrides(default_config())

    def test_adaptive_env(self, monkeypatch):
        monkeypatch.setenv("THALIA_QUERY_EXPANSION", "true")
        monkeypatch.setenv("THALIA_RECENCY_WEIGHT", "0.4")
        monkeypatch.setenv("THALIA_RECALL_MEMORY", "yes")
        monkeypatch.setenv("THALIA_ADAPTIVE_WINDOWS", "true")
        monkeypatch.setenv("THALIA_ADAPTIVE_WINDOW_RATIO", "7")
        from src.config import apply_env_overrides

        cfg = apply_env_overrides(default_config())
        assert cfg.query_expansion is True and cfg.recency_weight == 0.4 and cfg.recall_memory is True
        assert cfg.adaptive_windows is True and cfg.adaptive_window_ratio == 7

    def test_to_dict_round_trip_with_new_fields(self):
        cfg = HarnessConfig(rerank="mmr", verify=True, mmr_lambda=0.4, partition_size=5)
        assert HarnessConfig.from_dict(cfg.to_dict()) == cfg

    def test_canonical_yaml_includes_adaptive_fields(self):
        from pathlib import Path

        from src.config import load_config

        cfg = load_config(Path(__file__).resolve().parent.parent / "config" / "harness.yaml", apply_env=False)
        assert cfg.adaptive_windows is False
        assert cfg.adaptive_window_ratio == 5
