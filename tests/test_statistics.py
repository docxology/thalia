"""Tests for reproducible uncertainty estimates and sample accounting."""

import pytest

from src.evaluation.statistics import (
    binary_rate,
    bootstrap_mean,
    clustered_bootstrap_mean,
    clustered_paired_comparison,
    exact_paired_binary,
    holm_named,
    holm_bonferroni,
    paired_bootstrap_delta,
    paired_comparison,
    paired_permutation_p_value,
    sample_size_for_precision,
    stratified_bootstrap_mean,
    wilson_interval,
)


class TestBootstrapMean:
    def test_summary_has_provenance_and_bounds(self):
        result = bootstrap_mean([0.2, 0.5, 0.8], resamples=300, seed=4)
        assert result.n == 3
        assert result.method == "percentile_bootstrap_mean"
        assert result.low <= result.estimate <= result.high
        assert result.resamples == 300
        assert result.seed == 4

    def test_singleton_is_explicitly_degenerate(self):
        result = bootstrap_mean([0.42], resamples=10)
        assert result.low == result.high == result.estimate == 0.42
        assert result.standard_error == 0.0
        assert result.resamples == 0

    @pytest.mark.parametrize(
        "values, message",
        [([], "non-empty"), ([float("nan")], "finite")],
    )
    def test_rejects_invalid_sample(self, values, message):
        with pytest.raises(ValueError, match=message):
            bootstrap_mean(values)

    def test_rejects_invalid_controls(self):
        with pytest.raises(ValueError, match="resamples"):
            bootstrap_mean([1, 2], resamples=0)
        with pytest.raises(ValueError, match="confidence"):
            bootstrap_mean([1, 2], confidence=1.0)

    def test_is_deterministic(self):
        assert bootstrap_mean([0.1, 0.3, 0.9], resamples=200, seed=8) == bootstrap_mean(
            [0.1, 0.3, 0.9], resamples=200, seed=8
        )

    def test_stratified_and_clustered_provenance(self):
        stratified = stratified_bootstrap_mean({"easy": [0.2, 0.4], "hard": [0.8, 1.0]}, resamples=100, seed=2)
        clustered = clustered_bootstrap_mean({"seed0": [0.2, 0.4], "seed1": [0.8, 1.0]}, resamples=100, seed=2)
        assert stratified.strata == ("easy", "hard")
        assert stratified.resample_provenance.startswith("within_stratum")
        assert clustered.cluster_count == 2
        assert clustered.unit == "observation"
        assert stratified == stratified_bootstrap_mean({"easy": [0.2, 0.4], "hard": [0.8, 1.0]}, resamples=100, seed=2)

    def test_resampling_validation_and_singletons(self):
        with pytest.raises(ValueError, match="non-empty"):
            stratified_bootstrap_mean({})
        with pytest.raises(ValueError, match="resamples"):
            clustered_bootstrap_mean({"x": [1]}, resamples=0)
        assert clustered_bootstrap_mean({"x": [1]}, resamples=10).low == 1.0

    def test_group_key_collisions_are_rejected(self):
        with pytest.raises(ValueError, match="collide"):
            clustered_bootstrap_mean({1: [0.1], "1": [0.2]})


class TestRatesAndPairedComparisons:
    def test_wilson_interval_is_bounded_and_contains_rate(self):
        rate, low, high = wilson_interval(7, 10)
        assert rate == 0.7
        assert 0.0 <= low <= rate <= high <= 1.0

    def test_wilson_interval_matches_independent_golden_value(self):
        rate, low, high = wilson_interval(7, 10)
        assert rate == pytest.approx(0.7)
        assert low == pytest.approx(0.396778147461, abs=1e-12)
        assert high == pytest.approx(0.892208732594, abs=1e-12)

    def test_wilson_validation(self):
        with pytest.raises(ValueError, match="trials"):
            wilson_interval(0, 0)
        with pytest.raises(ValueError, match="between"):
            wilson_interval(4, 3)
        with pytest.raises(ValueError, match="integer"):
            wilson_interval(1.0, 2)  # pyright: ignore[reportArgumentType] - invalid input contract

    def test_named_binary_and_exact_mcnemar(self):
        rate = binary_rate(3, 5)
        assert rate.rate == 0.6 and rate.low <= rate.rate <= rate.high
        comparison = exact_paired_binary([1, 1, 1, 0], [0, 1, 0, 0])
        assert comparison.left_success_right_failure == 2
        assert comparison.left_failure_right_success == 0
        assert comparison.p_value == pytest.approx(0.5)
        with pytest.raises(ValueError, match="equal length"):
            exact_paired_binary([1], [1, 0])
        with pytest.raises(ValueError, match="binary"):
            exact_paired_binary([2], [1])

    def test_mcnemar_golden_two_sided_tail(self):
        comparison = exact_paired_binary([1, 1, 1, 0], [0, 0, 1, 0])
        assert comparison.left_success_right_failure == 2
        assert comparison.left_failure_right_success == 0
        assert comparison.p_value == pytest.approx(0.5)

        comparison = exact_paired_binary([1, 1, 1, 0], [0, 0, 0, 1])
        assert comparison.left_success_right_failure == 3
        assert comparison.left_failure_right_success == 1
        assert comparison.p_value == pytest.approx(0.625)

    def test_clustered_paired_comparison_uses_clusters_for_uncertainty(self):
        result = clustered_paired_comparison(
            {"seed0": [0.8, 0.9], "seed1": [0.7, 0.8]},
            {"seed0": [0.5, 0.6], "seed1": [0.4, 0.5]},
            resamples=100,
            permutations=100,
        )
        assert result.n == 4
        assert result.cluster_count == 2
        assert result.mean_delta == pytest.approx(0.3)
        assert result.comparison_family == "clustered_paired_comparison"
        with pytest.raises(ValueError, match="same cluster"):
            clustered_paired_comparison({"a": [1]}, {"b": [0]})

    def test_clustered_paired_comparison_point_estimate_is_cluster_weighted(self):
        # The observation-weighted delta would be 3/4 here; the declared
        # question-cluster estimand is the mean of the two cluster deltas: 1/2.
        result = clustered_paired_comparison(
            {"large-question": [1.0, 1.0, 1.0], "small-question": [0.0]},
            {"large-question": [0.0, 0.0, 0.0], "small-question": [0.0]},
            resamples=100,
            permutations=100,
        )
        assert result.mean_delta == pytest.approx(0.5)
        assert result.estimand == "mean_paired_delta_cluster_weighted"
        assert result.unit == "question_cluster"
        assert result.cluster_count == 2

    def test_paired_delta_and_exact_permutation(self):
        delta = paired_bootstrap_delta([0.8, 0.9, 0.7], [0.5, 0.6, 0.4], resamples=300)
        assert delta.estimate == pytest.approx(0.3)
        assert delta.low <= delta.estimate <= delta.high
        assert paired_permutation_p_value([1, 1, 1], [0, 0, 0]) == pytest.approx(0.25)

    def test_sign_flip_metadata_distinguishes_exhaustive_and_monte_carlo(self):
        exact = paired_comparison([1.0, 2.0], [0.0, 0.0], resamples=100, permutations=100)
        assert exact.p_value == pytest.approx(0.5)
        assert exact.p_value_method == "exhaustive_sign_flip"
        assert "exchangeability" in exact.p_value_assumption
        monte_carlo = paired_comparison([1.0] * 13, [0.0] * 13, resamples=100, permutations=25)
        assert monte_carlo.p_value_method == "monte_carlo_sign_flip_plus_one"

    def test_paired_comparison_reports_effect_and_adjustment_inputs(self):
        result = paired_comparison([0.8, 0.9, 0.7], [0.5, 0.6, 0.4], resamples=200, permutations=200)
        assert result.n == 3
        assert result.mean_delta == pytest.approx(0.3)
        assert result.effect_size is not None
        assert result.effect_size > 0
        assert 0.0 <= result.p_value <= 1.0

    def test_paired_validation_and_monte_carlo_path(self):
        with pytest.raises(ValueError, match="equal length"):
            paired_bootstrap_delta([1], [1, 2])
        with pytest.raises(ValueError, match="permutations"):
            paired_permutation_p_value([1, 2], [0, 0], permutations=0)
        assert paired_permutation_p_value([1] * 13, [0] * 13, permutations=50, seed=2) > 0
        assert paired_permutation_p_value([0, 0], [0, 0]) == 1.0

    def test_holm_preserves_order_and_validates(self):
        adjusted = holm_bonferroni([0.01, 0.2, 0.03])
        assert len(adjusted) == 3
        assert adjusted[0] == pytest.approx(0.03)
        assert all(0.0 <= value <= 1.0 for value in adjusted)
        with pytest.raises(ValueError, match="p_values"):
            holm_bonferroni([1.1])
        named = holm_named({"first": 0.01, "second": 0.2})
        assert named["first"] == pytest.approx(0.02)

    def test_holm_golden_step_down_values(self):
        assert holm_bonferroni([0.01, 0.04, 0.03]) == pytest.approx((0.03, 0.06, 0.06))


class TestPlanningAndAccounting:
    def test_sample_size_plan_grows_with_precision(self):
        assert sample_size_for_precision(0.2, half_width=0.01) > sample_size_for_precision(0.2, half_width=0.05)
        assert sample_size_for_precision(0.0) == 1

    def test_sample_size_validation(self):
        with pytest.raises(ValueError, match="standard_deviation"):
            sample_size_for_precision(-1)
        with pytest.raises(ValueError, match="half_width"):
            sample_size_for_precision(1, half_width=0)
