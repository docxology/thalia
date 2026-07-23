"""Tests for seeded scaling, uncertainty, and sample-size accounting (Zero-Mock)."""

import pytest

from src.evaluation import bootstrap_ci, build_large_dataset, build_research_dataset, large_dataset_eval, sample_size_scaling_eval, validate_dataset
from src.signatures import TaskCategory


class TestLargeDataset:
    def test_balanced_and_sized(self):
        ds = build_large_dataset(per_category=10, seed=0)
        assert len(ds) == 10 * len(TaskCategory)
        from collections import Counter

        counts = Counter(e.task_category for e in ds)
        assert set(counts.values()) == {10}

    def test_seeded_deterministic(self):
        a = build_large_dataset(per_category=8, seed=3)
        b = build_large_dataset(per_category=8, seed=3)
        assert [e.session_history for e in a] == [e.session_history for e in b]

    def test_different_seed_differs(self):
        a = build_large_dataset(per_category=8, seed=0)
        b = build_large_dataset(per_category=8, seed=1)
        assert [e.session_history for e in a] != [e.session_history for e in b]

    def test_research_dataset_is_balanced_stratified_and_unique(self):
        ds = build_research_dataset(per_category=4, seed=7)
        assert len(ds) == 4 * len(TaskCategory)
        assert len({e.example_id for e in ds}) == len(ds)
        assert {e.stratum for e in ds} == {"literal_lexical", "semantic_paraphrase", "noisy_long_context", "multi_hop_update"}
        assert [e.example_id for e in ds] == [e.example_id for e in build_research_dataset(per_category=4, seed=7)]
        with pytest.raises(ValueError, match="duplicate"):
            validate_dataset([ds[0], ds[0]])

    def test_research_construct_metadata_is_auditable(self):
        ds = build_research_dataset(per_category=5, seed=4)
        semantic = [example for example in ds if example.stratum == "semantic_paraphrase"]
        assert semantic
        assert all(example.metadata_dict()["surface_relation"] == "paraphrase" for example in semantic)
        assert all("favorite" not in example.query.lower() for example in semantic)

        noisy = [example for example in ds if example.stratum == "noisy_long_context"]
        assert noisy
        for example in noisy:
            metadata = example.metadata_dict()
            indices = [int(value) for value in metadata["negative_line_indices"].split(",")]
            assert len(indices) == int(metadata["negative_lines"])
            assert indices == list(range(4, 4 + len(indices)))
            assert all("unrelated remark" in example.session_history.splitlines()[index] for index in indices)

        multi_hop = [example for example in ds if example.stratum == "multi_hop_update"]
        assert multi_hop
        for example in multi_hop:
            assert len(example.expected_source_indices) >= 2
            assert example.metadata_dict()["source_requirement"] == "multiple_records"
            cited = [example.session_history.splitlines()[index] for index in example.expected_source_indices]
            assert any("supersedes" in line for line in cited) or any("confirmed" in line for line in cited)


class TestBootstrapCI:
    def test_ci_brackets_mean_and_is_deterministic(self):
        vals = [0.6, 0.7, 0.8, 0.55, 0.9, 0.65]
        mean, lo, hi = bootstrap_ci(vals, n_boot=500, seed=0)
        assert lo <= mean <= hi
        assert abs(mean - sum(vals) / len(vals)) < 1e-9
        assert bootstrap_ci(vals, n_boot=500, seed=0) == bootstrap_ci(vals, n_boot=500, seed=0)

    def test_empty(self):
        assert bootstrap_ci([]) == (0.0, 0.0, 0.0)

    def test_percentile_level_is_pinned(self):
        # Pin the exact CI so an off-by-magnitude bug in the percentile indices
        # (e.g. alpha/2 -> alpha, or a swapped lo/hi) fails instead of surviving.
        vals = [0.6, 0.7, 0.8, 0.55, 0.9, 0.65]
        mean, lo, hi = bootstrap_ci(vals, n_boot=500, seed=0)
        assert (round(mean, 4), round(lo, 4), round(hi, 4)) == (0.7, 0.6083, 0.7917)
        assert lo < mean < hi  # a non-degenerate interval for n>1

    def test_single_observation_is_degenerate_not_faked(self):
        # One point has no spread: report it as zero-width, never a fake CI.
        assert bootstrap_ci([0.42]) == (0.42, 0.42, 0.42)


class TestLargeEval:
    def test_reports_composite_and_per_category_cis(self):
        r = large_dataset_eval(per_category=6, seed=0, n_boot=400)
        assert r["n"] == 6 * len(TaskCategory)
        assert 0.0 <= r["composite_lo"] <= r["composite_mean"] <= r["composite_hi"] <= 1.0
        assert set(r["category_accuracy"]) == {c.name.lower() for c in TaskCategory}
        for _cat, (m, lo, hi) in r["category_accuracy"].items():
            assert lo <= m <= hi

    def test_deterministic(self):
        assert large_dataset_eval(per_category=6, n_boot=400) == large_dataset_eval(per_category=6, n_boot=400)


class TestSampleSizeScaling:
    def test_accounts_for_seeds_methods_and_examples(self):
        result = sample_size_scaling_eval(per_category_values=(1, 2), seeds=(0, 1), n_boot=120)
        assert result["per_category_values"] == [1, 2]
        assert result["seed_values"] == [0, 1]
        assert result["accounting"]["n_requested"] == 2 * len(TaskCategory) * 3
        assert result["accounting"]["n_method_evaluations"] == result["accounting"]["n_requested"] * 3
        assert [row["n_total"] for row in result["rows"]] == [2 * len(TaskCategory), 4 * len(TaskCategory)]
        assert set(result["rows"][0]["methods"]) == {"hybrid", "lexical", "semantic"}
        assert "holm_adjusted_p_value" in result["rows"][0]["paired_comparisons"]["hybrid_vs_lexical"]
        assert result["rows"][0]["paired_comparisons"]["hybrid_vs_lexical"]["cluster_count"] == 2
        assert set(result["rows"][0]["stratum_paired_comparisons"]) == {
            "hybrid_vs_lexical",
            "hybrid_vs_semantic",
        }
        assert len(result["rows"][0]["stratum_paired_comparisons"]["hybrid_vs_lexical"]) == 4
        assert result["rows"][0]["stratum_paired_comparisons"]["hybrid_vs_lexical"]["literal_lexical"]["holm_adjusted_p_value"] == 1.0
        assert result["comparison_family"]["size"] == len(result["rows"]) * 2 * (1 + 4)

    def test_ledger_and_event_accounting_is_deterministic(self):
        result = sample_size_scaling_eval(per_category_values=(1,), seeds=(0, 1), n_boot=30, include_ledger=True)
        assert result["accounting"]["n_unique_examples"] == 2 * len(TaskCategory)
        assert len(result["ledger"]) == result["accounting"]["n_method_evaluations"]
        assert [row["sequence"] for row in result["ledger"]] == list(range(1, len(result["ledger"]) + 1))
        assert result["events"][0]["n_unique_examples"] == result["accounting"]["n_unique_examples"]
        assert result["events"][0]["event"] == "run_started"
        assert result["events"][-1]["event"] == "run_finished"
        assert [row["sequence"] for row in result["events"]] == list(range(1, len(result["events"]) + 1))
        assert result == sample_size_scaling_eval(per_category_values=(1,), seeds=(0, 1), n_boot=30, include_ledger=True)

    def test_deterministic(self):
        a = sample_size_scaling_eval(per_category_values=(1,), seeds=(3,), n_boot=80)
        b = sample_size_scaling_eval(per_category_values=(1,), seeds=(3,), n_boot=80)
        assert a == b

    def test_validates_sample_grid(self):
        with pytest.raises(ValueError, match="strictly increasing"):
            sample_size_scaling_eval(per_category_values=(2, 1), seeds=(0,), n_boot=10)
        with pytest.raises(ValueError, match="seeds must be non-empty"):
            sample_size_scaling_eval(per_category_values=(1,), seeds=(), n_boot=10)
