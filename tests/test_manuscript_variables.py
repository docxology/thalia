"""Tests for manuscript variable generation (Zero-Mock)."""

import json

from src.config import default_config
from src.manuscript_variables import generate_variables

EXPECTED_TOKENS = {
    "CONFIG_TOP_K",
    "CONFIG_MAX_WINDOWS",
    "CONFIG_MAX_EVIDENCE",
    "CONFIG_RRF_K",
    "CONFIG_CONTEXT_BUDGET",
    "CONFIG_NUM_STAGES",
    "RESULT_NUM_EXAMPLES",
    "RESULT_COMPOSITE",
    "RESULT_ACCURACY",
    "RESULT_GROUNDING",
    "RESULT_EFFICIENCY",
    "RESULT_LEXICAL_COMPOSITE",
    "RESULT_SEMANTIC_COMPOSITE",
    "RESULT_HYBRID_COMPOSITE",
    "RESULT_BEST_MODE",
    "RESULT_COMPILED_SCORE",
    "RESULT_COMPILED_TOP_K",
    "RESULT_COMPILED_MAX_EVIDENCE",
    "RESULT_NUM_CANDIDATES",
    "RESULT_NEURAL_MODEL",
    "RESULT_NEURAL_MEAN_F1",
    "RESULT_EXTRACTIVE_MEAN_F1",
}


class TestGenerateVariables:
    def test_all_expected_tokens_present(self):
        variables = generate_variables()
        assert EXPECTED_TOKENS <= set(variables)

    def test_missing_neural_eval_raises_clearly(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_NEURAL_EVAL_PATH", tmp_path / "absent.json")
        try:
            mv.generate_variables()
            raise AssertionError("expected FileNotFoundError")
        except FileNotFoundError as exc:
            assert "run_neural_eval" in str(exc)

    def test_all_values_are_strings(self):
        variables = generate_variables()
        assert all(isinstance(v, str) for v in variables.values())

    def test_num_examples_matches_dataset(self):
        assert generate_variables()["RESULT_NUM_EXAMPLES"] == "6"

    def test_num_stages_is_five(self):
        assert generate_variables()["CONFIG_NUM_STAGES"] == "5"

    def test_config_echoed(self):
        variables = generate_variables(default_config())
        assert variables["CONFIG_TOP_K"] == "8"

    def test_deterministic(self):
        assert generate_variables() == generate_variables()

    def test_older_bottleneck_aggregate_without_mode_breakdown_is_supported(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        original = json.loads(mv._LME_BN_PATH.read_text())
        original.pop("ranking_recall_by_mode", None)
        path = tmp_path / "longmemeval_bottleneck.json"
        path.write_text(json.dumps(original), encoding="utf-8")
        monkeypatch.setattr(mv, "_LME_BN_PATH", path)

        variables = mv.generate_variables()

        assert variables["RESULT_BN_RECALL_MODE_N"] == variables["RESULT_BN_N"]
        assert variables["RESULT_BN_RECALL_LEXICAL"] == variables["RESULT_BN_RANKING_RECALL"]
        assert "RESULT_BN_RECALL_DENSE" not in variables
        assert "RESULT_BN_RECALL_HYBRID" not in variables
