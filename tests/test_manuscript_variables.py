"""Tests for manuscript variable generation (Zero-Mock)."""

import json

import pytest

from src import __version__
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
    "RESULT_QUALITY_TOTAL_N",
    "RESULT_QUALITY_PILOT_N",
    "RESULT_QUALITY_CONFIRMATORY_N",
    "RESULT_QUALITY_CONDITIONS",
    "RESULT_QUALITY_RATERS",
    "RESULT_QUALITY_PRIMARY",
    "RESULT_INTEGRITY_AUDIT_N",
    "RESULT_INTEGRITY_AUDIT_DELTA",
    "RESULT_INTEGRITY_AUDIT_P",
    "RESULT_INTEGRITY_AUDIT_ADJ_P",
    "RESULT_INTEGRITY_COMPOSITE_LIFT",
    "RESULT_INTEGRITY_POISON_P",
    "RESULT_INTEGRITY_POISON_ADJ_P",
    "RESULT_INTEGRITY_LEARNED_ADJ_P",
    "RESULT_INTEGRITY_COMPILER_ADJ_P",
    "RESULT_INTEGRITY_NEURAL_DELTA",
    "RESULT_INTEGRITY_NEURAL_ADJ_P",
    "CURRENT_RELEASE_VERSION",
    "CURRENT_RELEASE_URL",
    "ARCHIVED_RELEASE_DOI",
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

    def test_missing_learned_eval_raises_clearly(self, monkeypatch, tmp_path):
        """_load_learned_eval raises FileNotFoundError with a helpful message (line 79)."""
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_LEARNED_EVAL_PATH", tmp_path / "absent_learned.json")
        try:
            mv.generate_variables()
            raise AssertionError("expected FileNotFoundError")
        except FileNotFoundError as exc:
            assert "run_learned_retrieval" in str(exc)

    def test_all_values_are_strings(self):
        variables = generate_variables()
        assert all(isinstance(v, str) for v in variables.values())

    def test_num_examples_matches_dataset(self):
        assert generate_variables()["RESULT_NUM_EXAMPLES"] == "6"

    def test_num_stages_is_five(self):
        assert generate_variables()["CONFIG_NUM_STAGES"] == "5"

    def test_v2_extension_tokens_bind_to_generated_aggregates(self):
        variables = generate_variables()
        assert variables["RESULT_SEED_SENSITIVITY_SEEDS"] == "10"
        assert variables["RESULT_SEED_SENSITIVITY_EVALUATIONS"] == "1800"
        assert variables["RESULT_COMPILER_SEEDS"] == "20"
        assert variables["RESULT_COMPILER_ACCOUNTED_N"] == "13720"
        assert variables["RESULT_COMPILER_CANDIDATE_N"] == "260"

    def test_quality_scope_tokens_bind_to_thalia_overlay(self):
        variables = generate_variables()
        assert variables["RESULT_QUALITY_TOTAL_N"] == "500"
        assert variables["RESULT_QUALITY_PILOT_N"] == "60"
        assert variables["RESULT_QUALITY_CONFIRMATORY_N"] == "440"
        assert variables["RESULT_QUALITY_CONDITIONS"] == "6"
        assert variables["RESULT_QUALITY_RATERS"] == "2"
        assert variables["RESULT_QUALITY_PRIMARY"] == "correctness_full_rate"

    def test_missing_v2_aggregate_raises_clearly(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_SEED_SENSITIVITY_PATH", tmp_path / "absent_seed.json")
        with pytest.raises(FileNotFoundError, match="run_seed_sensitivity"):
            mv.generate_variables()

    def test_config_echoed(self):
        variables = generate_variables(default_config())
        assert variables["CONFIG_TOP_K"] == "8"

    def test_current_and_archived_identities_are_source_bound(self):
        import src.manuscript_variables as mv

        metadata = json.loads(mv._ZENODO_METADATA_PATH.read_text())
        archived = next(
            item["identifier"]
            for item in metadata["related_identifiers"]
            if item["relation"] == "isNewVersionOf"
        )
        variables = generate_variables()
        assert variables["ARCHIVED_RELEASE_DOI"] == archived
        assert variables["CURRENT_RELEASE_VERSION"] == __version__
        assert variables["CURRENT_RELEASE_URL"] == (
            f"https://github.com/docxology/thalia/releases/tag/v{__version__}"
        )

    @pytest.mark.parametrize(
        "metadata",
        [
            {},
            [],
            {"related_identifiers": None},
            {"related_identifiers": [None]},
            {"related_identifiers": [{"relation": "isIdenticalTo", "scheme": "doi"}]},
        ],
    )
    def test_missing_archive_relation_fails_closed(self, monkeypatch, tmp_path, metadata):
        import src.manuscript_variables as mv

        path = tmp_path / ".zenodo.json"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError, match="exactly one archived release DOI"):
            mv.generate_variables()

    @pytest.mark.parametrize("identifier", [None, 42, "", "not-a-doi", "10.5281/has whitespace"])
    def test_invalid_archived_doi_fails_closed(self, monkeypatch, tmp_path, identifier):
        import src.manuscript_variables as mv

        metadata = {
            "related_identifiers": [
                {"relation": "isNewVersionOf", "scheme": "doi", "identifier": identifier}
            ]
        }
        path = tmp_path / ".zenodo.json"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError, match="valid DOI"):
            mv.generate_variables()

    @pytest.mark.parametrize("change", ["duplicate", "wrong_scheme"])
    def test_ambiguous_or_non_doi_archive_fails_closed(self, monkeypatch, tmp_path, change):
        import src.manuscript_variables as mv

        metadata = json.loads(mv._ZENODO_METADATA_PATH.read_text())
        archive = next(
            item for item in metadata["related_identifiers"] if item["relation"] == "isNewVersionOf"
        )
        if change == "duplicate":
            metadata["related_identifiers"].append(dict(archive))
        else:
            archive["scheme"] = "url"
        path = tmp_path / ".zenodo.json"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError, match="archived release"):
            mv.generate_variables()

    @pytest.mark.parametrize("contents", [None, "{", b"\xff"])
    def test_unreadable_archive_metadata_fails_closed(self, monkeypatch, tmp_path, contents):
        import src.manuscript_variables as mv

        path = tmp_path / ".zenodo.json"
        if isinstance(contents, str):
            path.write_text(contents, encoding="utf-8")
        elif isinstance(contents, bytes):
            path.write_bytes(contents)
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError, match="metadata is unreadable"):
            mv.generate_variables()

    def test_deterministic(self):
        assert generate_variables() == generate_variables()

    def test_bottleneck_aggregate_requires_mode_breakdown(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        original = json.loads(mv._LME_BN_PATH.read_text())
        original.pop("ranking_recall_by_mode", None)
        path = tmp_path / "longmemeval_bottleneck.json"
        path.write_text(json.dumps(original), encoding="utf-8")
        monkeypatch.setattr(mv, "_LME_BN_PATH", path)

        with pytest.raises(KeyError, match="ranking_recall_by_mode"):
            mv.generate_variables()

    def test_missing_audit_bundle_raises_clearly(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_EVAL_RESULTS_PATH", tmp_path / "absent_eval.json")
        with pytest.raises(FileNotFoundError, match="run_harness_eval"):
            mv.generate_variables()
