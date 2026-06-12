"""Tests for the deterministic falsifiability ablations (Zero-Mock)."""

from src.evaluation import (
    composite_weight_sensitivity,
    injection_resistance,
    memory_recall_ablation,
    no_harness_baseline,
)


class TestInjectionResistance:
    def test_grounding_keeps_true_source_auditable(self):
        r = injection_resistance()
        # Lexical extraction is not injection-immune: harness and naive poison alike.
        assert r["harness_poison_rate"] == r["naive_poison_rate"]
        # But only the grounded harness keeps the true source auditable.
        assert r["harness_audit_rate"] == 1.0 and r["naive_audit_rate"] == 0.0

    def test_deterministic(self):
        assert injection_resistance() == injection_resistance()

    def test_rows_record_exact_cases(self):
        r = injection_resistance()
        assert len(r["rows"]) == r["n_probes"]
        assert all("harness_poisoned" in row and "harness_auditable" in row for row in r["rows"])
        assert sum(row["harness_auditable"] for row in r["rows"]) == r["n_probes"]


class TestMemoryRecallAblation:
    def test_episodic_store_is_load_bearing_for_recall(self):
        m = memory_recall_ablation()
        # A punctuated NL query recovers the store-only fact, and nothing without it.
        assert m["recall_hit"] is True and m["recalled_windows"] >= 1
        assert m["no_store_hit"] is False and m["no_store_windows"] == 0

    def test_deterministic(self):
        assert memory_recall_ablation() == memory_recall_ablation()


class TestNoHarnessBaseline:
    def test_accuracy_ties_but_orchestration_lifts_composite(self):
        b = no_harness_baseline()
        # The extractive LM finds the gold line with or without narrowing -> accuracy ties.
        assert b["naive_accuracy"] == b["pipeline_accuracy"]
        # The naive baseline earns no grounding/efficiency by construction.
        assert b["naive_grounding"] == 0.0 and b["naive_efficiency"] == 0.0
        # The orchestration's whole value is grounding + efficiency -> positive lift.
        assert b["composite_lift"] > 0.2
        assert b["pipeline_composite"] > b["naive_composite"]

    def test_deterministic(self):
        assert no_harness_baseline() == no_harness_baseline()


class TestWeightSensitivity:
    def test_winner_robust_across_simplex(self):
        s = composite_weight_sensitivity()
        assert s["robust"] is True
        assert len(s["distinct_winners"]) == 1
        assert len(s["winners"]) == len(s["accuracy_weights"])

    def test_deterministic(self):
        assert composite_weight_sensitivity() == composite_weight_sensitivity()
