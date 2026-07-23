"""Regression tests for pre-registered generalization lanes."""

import pytest

from src.evaluation.compiler_generalization import compiler_generalization_eval
from src.evaluation.generalization import seed_sensitivity_eval


def test_seed_sensitivity_is_clustered_and_complete():
    result = seed_sensitivity_eval(per_category=1, seeds=(0, 1), n_boot=30)
    assert result["headline_replacement"] is False
    assert result["seed_values"] == [0, 1]
    assert set(result["cluster_statistics"]) == {"hybrid", "lexical", "semantic"}
    accounting = result["sample_accounting"]
    assert accounting["n_requested"] == accounting["n_evaluated"]
    assert accounting["n_failed"] == 0
    assert accounting["status"] == "complete"
    for comparison in result["paired_comparisons"].values():
        assert comparison["cluster_count"] == 2
        assert comparison["small_cluster_warning"] is True


def test_seed_sensitivity_rejects_invalid_contract():
    with pytest.raises(ValueError, match="per_category"):
        seed_sensitivity_eval(per_category=0)
    with pytest.raises(ValueError, match="seeds"):
        seed_sensitivity_eval(per_category=1, seeds=(0, 0), n_boot=10)


def test_compiler_generalization_reports_train_and_held_out_scores():
    result = compiler_generalization_eval(per_category=2, seeds=(0,), gepa_iterations=1)
    assert result["experiment"] == "compiler_held_out_generalization_v2"
    assert result["sample_accounting"]["status"] == "complete"
    row = result["rows"][0]
    assert row["n_train"] > 0 and row["n_holdout"] > 0
    accounting = result["sample_accounting"]
    components = accounting["components"]
    assert accounting["n_evaluated"] == sum(
        component["n_evaluated"] for component in components.values()
    )
    assert components["compiler_candidate_train_evaluations"]["n_evaluated"] > 0
    for method in ("baseline", "mipro", "gepa"):
        assert 0.0 <= row[method]["holdout_composite"] <= 1.0
        assert "config_fingerprint" not in row[method] or row[method]["config_fingerprint"]


def test_compiler_generalization_requires_a_holdout():
    with pytest.raises(ValueError, match="per_category"):
        compiler_generalization_eval(per_category=1)
    with pytest.raises(ValueError, match="holdout_fraction"):
        compiler_generalization_eval(per_category=2, holdout_fraction=1.0)
