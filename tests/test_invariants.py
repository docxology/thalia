"""Tests asserting every formal harness invariant holds (Zero-Mock)."""

from src.invariants import InvariantResult, all_invariants, summarize


class TestAllInvariants:
    def test_returns_results(self):
        results = all_invariants()
        assert results
        assert all(isinstance(r, InvariantResult) for r in results)

    def test_every_invariant_passes(self):
        failed = [r.name for r in all_invariants() if not r.passed]
        assert failed == [], f"failing invariants: {failed}"

    def test_each_result_has_detail(self):
        assert all(r.detail for r in all_invariants())

    def test_names_unique(self):
        names = [r.name for r in all_invariants()]
        assert len(names) == len(set(names))


class TestSummarize:
    def test_all_passing(self):
        results = all_invariants()
        n_pass, n_total = summarize(results)
        assert n_pass == n_total == len(results)

    def test_counts_failures(self):
        mixed = [
            InvariantResult("a", True, ""),
            InvariantResult("b", False, ""),
            InvariantResult("c", True, ""),
        ]
        assert summarize(mixed) == (2, 3)
