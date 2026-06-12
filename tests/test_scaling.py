"""Tests for the seeded large dataset and bootstrap-CI scaling eval (Zero-Mock)."""

from src.evaluation import bootstrap_ci, build_large_dataset, large_dataset_eval
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
