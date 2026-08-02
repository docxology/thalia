"""Tests for the deterministic falsifiability ablations (Zero-Mock)."""

from copy import deepcopy

import pytest

from src.evaluation import (
    composite_weight_sensitivity,
    injection_resistance,
    memory_recall_ablation,
    no_harness_baseline,
)


def _retained_injection_aggregate() -> dict:
    from src.evaluation.ablation import _ATTACK_FAMILIES, _INJECTION_PROBES

    rows = []
    neural_rows = []
    for probe_number, probe in enumerate(_INJECTION_PROBES, start=1):
        attack_family = _ATTACK_FAMILIES[(probe_number - 1) % len(_ATTACK_FAMILIES)]
        rows.append(
            {
                "probe": probe_number,
                "attack_family": attack_family,
                "query": probe.query,
                "gold": probe.gold,
                "harness_poisoned": False,
                "harness_correct": True,
                "harness_auditable": True,
                "naive_poisoned": False,
                "naive_correct": True,
                "naive_auditable": False,
            }
        )
        neural_rows.append(
            {
                "probe": probe_number,
                "attack_family": attack_family,
                "query": probe.query,
                "gold": probe.gold,
                "answer": probe.injected_answer if probe_number <= 2 else probe.gold,
                "neural_poisoned": False,
                "neural_correct": False,
                "neural_auditable": False,
            }
        )
    return {
        "n_probes": len(_INJECTION_PROBES),
        "rows": rows,
        "neural_rows": neural_rows,
        "neural_model": "retained-local-model",
        "neural_model_metadata": {"digest": "recorded"},
        "neural_generation_options": {"temperature": 0.0},
        "runtime_provenance": {"python": "recorded"},
        "sample_accounting": {
            "unit": "injection_probe",
            "n_requested": len(_INJECTION_PROBES),
            "n_evaluated": len(_INJECTION_PROBES),
            "n_failed": 0,
        },
    }


class TestMetricConstructAudit:
    def test_reports_decomposed_constructs_by_category(self):
        from src.evaluation import metric_construct_audit

        audit = metric_construct_audit()
        assert audit["n_examples"] > 0
        assert audit["metric_names"] == [
            "answer_token_f1",
            "citation_support_proxy",
            "citation_precision",
            "source_recall",
            "session_reachability",
            "evidence_efficiency",
        ]
        assert audit["by_category"]
        for row in audit["by_category"].values():
            assert all(0.0 <= value <= 1.0 for value in row.values())

    def test_deterministic(self):
        from src.evaluation import metric_construct_audit

        assert metric_construct_audit() == metric_construct_audit()


class TestInjectionResistance:
    def test_poisoning_uses_explicit_injected_answer_not_line_ending(self):
        from src.evaluation.ablation import _INJECTION_PROBES, _is_poisoned

        probe = _INJECTION_PROBES[0]
        assert probe.injected_answer == "hunter2"
        assert all(
            candidate.injected_answer.lower() in candidate.poison_line.lower()
            for candidate in _INJECTION_PROBES
        )
        assert _is_poisoned("hunter2", probe.gold, probe.injected_answer) is True
        assert (
            _is_poisoned("the only correct answer", probe.gold, probe.injected_answer)
            is False
        )

    def test_grounding_keeps_gold_value_in_cited_excerpts(self):
        r = injection_resistance()
        # The finite probe records equal poisoned-answer rates for these conditions.
        assert r["harness_poison_rate"] == r["naive_poison_rate"]
        # The legacy audit field is a lexical cited-excerpt/source-exposure proxy.
        assert r["harness_audit_rate"] == 1.0 and r["naive_audit_rate"] == 0.0

    def test_deterministic(self):
        assert injection_resistance() == injection_resistance()

    def test_rows_record_exact_cases(self):
        r = injection_resistance()
        assert len(r["rows"]) == r["n_probes"]
        assert all(
            "harness_poisoned" in row
            and "harness_auditable" in row
            and row["injected_answer"]
            for row in r["rows"]
        )
        assert sum(row["harness_auditable"] for row in r["rows"]) == r["n_probes"]

    def test_relabels_retained_neural_answers_and_preserves_provenance(self):
        from src.evaluation.ablation import relabel_recorded_injection_answers
        from src.evaluation.statistics import wilson_interval

        retained = _retained_injection_aggregate()
        original = deepcopy(retained)
        relabelled = relabel_recorded_injection_answers(retained)

        assert retained == original
        assert relabelled["runtime_provenance"] == original["runtime_provenance"]
        assert relabelled["neural_model_metadata"] == original["neural_model_metadata"]
        assert relabelled["neural_generation_options"] == original["neural_generation_options"]
        assert all(row["injected_answer"] for row in relabelled["rows"])
        assert all(row["injected_answer"] for row in relabelled["neural_rows"])
        assert sum(row["neural_poisoned"] for row in relabelled["neural_rows"]) == 2
        assert sum(row["neural_correct"] for row in relabelled["neural_rows"]) == 28
        assert relabelled["neural_poison_rate"] == 2 / 30
        assert relabelled["neural_correct_rate"] == 28 / 30
        assert relabelled["neural_poison_ci"] == list(wilson_interval(2, 30))
        assert relabelled["neural_correct_ci"] == list(wilson_interval(28, 30))

    def test_relabel_rejects_rows_that_do_not_bind_current_fixtures(self):
        from src.evaluation.ablation import relabel_recorded_injection_answers

        retained = _retained_injection_aggregate()
        retained["neural_rows"][0]["gold"] = "tampered"
        with pytest.raises(ValueError, match="does not bind to fixture 1"):
            relabel_recorded_injection_answers(retained)


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
