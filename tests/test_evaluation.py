"""Tests for the evaluation dataset and experiments (Zero-Mock)."""

import pytest
from src.evaluation import (
    RetrieverComparison,
    build_demo_dataset,
    consolidation_simulation,
    noise_scaling_experiment,
    retriever_comparison,
    rrf_weight_sweep,
    run_full_eval,
    with_noise,
)


class TestDataset:
    def test_six_examples_across_categories(self):
        ds = build_demo_dataset()
        assert len(ds) == 6
        categories = {ex.task_category for ex in ds}
        assert len(categories) == 6  # all distinct

    def test_examples_have_gold_answers(self):
        for ex in build_demo_dataset():
            assert ex.expected_answer
            assert ex.expected_source_indices


class TestRetrieverComparison:
    def test_returns_three_modes(self):
        cmp = retriever_comparison()
        assert isinstance(cmp, RetrieverComparison)
        assert 0.0 <= cmp.lexical <= 1.0
        assert 0.0 <= cmp.semantic <= 1.0
        assert 0.0 <= cmp.hybrid <= 1.0

    def test_best_mode_returns_name(self):
        cmp = RetrieverComparison(lexical=0.9, semantic=0.5, hybrid=0.8)
        assert cmp.best_mode() == "lexical"

    def test_best_mode_tie_prefers_lexical(self):
        cmp = RetrieverComparison(lexical=0.8, semantic=0.8, hybrid=0.8)
        assert cmp.best_mode() == "lexical"

    def test_deterministic(self):
        assert retriever_comparison().hybrid == retriever_comparison().hybrid


class TestRRFSweep:
    def test_returns_pairs(self):
        sweep = rrf_weight_sweep(steps=5)
        assert len(sweep) == 5
        assert sweep[0][0] == 0.0 and sweep[-1][0] == 1.0

    def test_steps_too_small_raises(self):
        with pytest.raises(ValueError, match="steps must be >= 2"):
            rrf_weight_sweep(steps=1)


class TestNoise:
    def test_with_noise_zero_returns_same(self):
        ex = build_demo_dataset()[0]
        assert with_noise(ex, 0) is ex

    def test_with_noise_appends_lines(self):
        ex = build_demo_dataset()[0]
        noisy = with_noise(ex, 5)
        assert len(noisy.session_history) > len(ex.session_history)
        # Gold source indices preserved (distractors appended after).
        assert noisy.expected_source_indices == ex.expected_source_indices

    def test_noise_scaling_structure(self):
        exp = noise_scaling_experiment(levels=(0, 4))
        assert set(exp) == {"lexical", "semantic", "hybrid"}
        assert len(exp["lexical"]) == 2

    def test_noise_scaling_bad_levels_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            noise_scaling_experiment(levels=(-1,))

    def test_noise_scaling_empty_levels_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            noise_scaling_experiment(levels=())


class TestConsolidationSimulation:
    def test_lengths_match_turns(self):
        sim = consolidation_simulation(turns=10)
        assert len(sim["forced"]) == 10
        assert len(sim["episodic_first"]) == 10

    def test_turns_one(self):
        sim = consolidation_simulation(turns=1)
        assert len(sim["forced"]) == 1

    def test_turns_too_small_raises(self):
        with pytest.raises(ValueError, match="turns must be >= 1"):
            consolidation_simulation(turns=0)

    def test_forced_degrades_below_peak(self):
        sim = consolidation_simulation(turns=12)
        assert sim["forced"][-1] < max(sim["forced"])


class TestRunFullEval:
    def test_bundle_keys(self):
        result = run_full_eval()
        for key in (
            "n_examples",
            "composite",
            "accuracy",
            "grounding",
            "efficiency",
            "retriever_comparison",
            "category_means",
            "rrf_weight_sweep",
            "config",
        ):
            assert key in result

    def test_category_means_cover_dataset(self):
        result = run_full_eval()
        assert len(result["category_means"]) == 6

    def test_composite_in_range(self):
        assert 0.0 <= run_full_eval()["composite"] <= 1.0

    def test_includes_mmr_and_funnel(self):
        result = run_full_eval()
        assert "mmr_lambda_sweep" in result
        assert "evidence_funnel" in result
        assert result["config"]["rerank"] == "rrf"

    def test_sweeps_use_tight_budget_not_headline_config(self):
        from src.config import default_config
        from src.evaluation import mmr_lambda_sweep, rrf_weight_sweep

        loose = default_config()
        tight_default = rrf_weight_sweep()
        tight_with_loose = rrf_weight_sweep(base=loose)
        assert tight_default == tight_with_loose
        assert mmr_lambda_sweep() == mmr_lambda_sweep(base=loose)


class TestEvidenceFunnel:
    def test_keys_present(self):
        from src.evaluation import evidence_funnel

        funnel = evidence_funnel()
        assert set(funnel) == {"session_lines", "windows", "ranked", "cited"}

    def test_narrowing_holds(self):
        from src.evaluation import evidence_funnel

        funnel = evidence_funnel()
        assert funnel["session_lines"] >= funnel["cited"] > 0


class TestMMRSweep:
    def test_returns_pairs(self):
        from src.evaluation import mmr_lambda_sweep

        sweep = mmr_lambda_sweep(steps=5)
        assert len(sweep) == 5
        assert sweep[0][0] == 0.0 and sweep[-1][0] == 1.0

    def test_steps_too_small_raises(self):
        from src.evaluation import mmr_lambda_sweep

        with pytest.raises(ValueError, match="steps must be >= 2"):
            mmr_lambda_sweep(steps=1)


class TestMethodAblation:
    def test_returns_all_conditions(self):
        from src.evaluation import method_ablation

        ablation = method_ablation()
        assert set(ablation) == {"base", "+expansion", "+recency", "+mmr", "all"}

    def test_default_budget_surfaces_divergence(self):
        from src.evaluation import method_ablation

        ablation = method_ablation()
        assert len(set(round(v, 4) for v in ablation.values())) > 1
        assert ablation["+recency"] >= ablation["base"]

    def test_loose_budget_is_null_by_construction(self):
        from src.config import default_config
        from src.evaluation import method_ablation

        loose = method_ablation(base=default_config(), tight_budget=False)
        assert len(set(round(v, 4) for v in loose.values())) == 1


class TestCategoryComponentBreakdown:
    def test_returns_all_six_categories(self):
        from src.evaluation import category_component_breakdown

        breakdown = category_component_breakdown()
        assert len(breakdown) == 6

    def test_keys_are_task_category_values(self):
        from src.evaluation import category_component_breakdown
        from src.signatures import TaskCategory

        breakdown = category_component_breakdown()
        expected = {cat.value for cat in TaskCategory}
        assert set(breakdown.keys()) == expected

    def test_each_category_has_three_components(self):
        from src.evaluation import category_component_breakdown

        breakdown = category_component_breakdown()
        for cat, components in breakdown.items():
            assert set(components.keys()) == {"accuracy", "grounding", "efficiency"}, cat

    def test_component_values_in_unit_interval(self):
        from src.evaluation import category_component_breakdown

        breakdown = category_component_breakdown()
        for cat, components in breakdown.items():
            for metric, value in components.items():
                assert 0.0 <= value <= 1.0, f"{cat}.{metric} = {value}"

    def test_deterministic(self):
        from src.evaluation import category_component_breakdown

        a = category_component_breakdown()
        b = category_component_breakdown()
        assert a == b
