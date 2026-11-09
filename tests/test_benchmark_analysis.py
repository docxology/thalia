"""Arithmetic audits of validated paired rows; no measured model evidence."""

from __future__ import annotations

import copy
from statistics import mean

import pytest

from src.evaluation.benchmark_analysis import analyze_benchmark_rows, summarize_seed_pairs


def _paired_inputs():
    examples = [
        {"example_id": str(index), "seed": seed, "category": "test", "stratum": "test"}
        for index, seed in enumerate((7, 2, 2, 2))
    ]
    backends = ["second", "first"]
    methods = ["adaptive", "full_context", "custom"]
    rows = []
    for backend in backends:
        for method in methods:
            for example in examples:
                if method == "full_context":
                    score = 0.0
                elif method == "custom":
                    score = 1.0 if example["seed"] == 2 else 0.0
                else:
                    score = 0.0 if example["seed"] == 2 else 1.0
                rows.append({
                    **example, "backend": backend, "method": method,
                    "status": "complete", "token_f1": score,
                    "latency_seconds": 0.0, "prompt_characters": 1,
                })
    return rows, dict(backends=backends, methods=methods, examples=examples,
                      reference_method="full_context")


def test_seed_audit_preserves_selection_order_sorted_seeds_and_equal_seed_estimand():
    rows, selection = _paired_inputs()
    original = copy.deepcopy((rows, selection))
    audits = summarize_seed_pairs(rows[::-1], **selection)
    assert [(row["backend"], row["method"], row["seed"]) for row in audits] == [
        (backend, method, seed)
        for backend in ("second", "first")
        for method in ("adaptive", "custom")
        for seed in (2, 7)
    ]
    assert audits[2:] != []
    assert audits[2] == {
        "backend": "second", "method": "custom", "reference_method": "full_context",
        "seed": 2, "status": "complete", "n_requested_pairs": 3,
        "n_complete_pairs": 3, "wins": 3, "ties": 0, "losses": 0, "mean_delta": 1.0,
    }
    assert audits[3] == {
        "backend": "second", "method": "custom", "reference_method": "full_context",
        "seed": 7, "status": "complete", "n_requested_pairs": 1,
        "n_complete_pairs": 1, "wins": 0, "ties": 1, "losses": 0, "mean_delta": 0.0,
    }
    comparisons = analyze_benchmark_rows(rows, **selection, n_boot=13, analysis_seed=4)["comparisons"]
    custom = next(row for row in comparisons if row["backend"] == "second" and row["method"] == "custom")
    assert custom["mean_delta"] == mean(row["mean_delta"] for row in audits[2:4]) == 0.5
    assert mean(row["token_f1"] for row in rows if row["backend"] == "second" and row["method"] == "custom") == 0.75
    assert summarize_seed_pairs(rows, **selection) == audits
    assert (rows, selection) == original


@pytest.mark.parametrize("failed_method", ["custom", "full_context"])
def test_one_failed_pair_suppresses_seed_and_whole_contrast_not_surviving_counts(failed_method):
    rows, selection = _paired_inputs()
    failed = next(row for row in rows if row["backend"] == "second" and row["method"] == failed_method and row["example_id"] == "1")
    failed.update(status="failed", token_f1=None)
    original = copy.deepcopy((rows, selection))
    audits = summarize_seed_pairs(rows, **selection)
    seed = next(row for row in audits if row["backend"] == "second" and row["method"] == "custom" and row["seed"] == 2)
    assert seed == {
        "backend": "second", "method": "custom", "reference_method": "full_context",
        "seed": 2, "status": "incomplete", "n_requested_pairs": 3,
        "n_complete_pairs": 2, "wins": 2, "ties": 0, "losses": 0, "mean_delta": None,
    }
    other_seed = next(row for row in audits if row["backend"] == "second" and row["method"] == "custom" and row["seed"] == 7)
    assert other_seed["status"] == "complete" and other_seed["mean_delta"] == 0.0
    comparisons = analyze_benchmark_rows(rows, **selection, n_boot=13, analysis_seed=4)["comparisons"]
    contrast = next(row for row in comparisons if row["backend"] == "second" and row["method"] == "custom")
    assert contrast["mean_delta"] is None and contrast["interval"] is None
    assert contrast["n_complete_pairs"] == 3 and contrast["status"] == "incomplete"
    assert (rows, selection) == original


def test_zero_surviving_pairs_retains_every_represented_seed_and_other_backends():
    rows, selection = _paired_inputs()
    for row in rows:
        if row["backend"] == "second" and row["method"] == "full_context":
            row.update(status="failed", token_f1=None)
    audits = summarize_seed_pairs(rows, **selection)
    assert len(audits) == 8
    for row in audits[:4]:
        assert row["status"] == "incomplete"
        assert row["n_complete_pairs"] == row["wins"] == row["ties"] == row["losses"] == 0
        assert row["mean_delta"] is None
        assert row["n_requested_pairs"] == (3 if row["seed"] == 2 else 1)
    assert all(row["status"] == "complete" for row in audits[4:])


def test_wins_ties_losses_use_paired_differences_not_candidate_scores():
    examples = [{"example_id": str(index), "seed": -3} for index in range(3)]
    rows = [
        {**example, "backend": "local", "method": method, "status": "complete", "token_f1": score}
        for method, scores in (("reference", (0.5, 0.5, 0.5)), ("candidate", (0.0, 0.5, 1.0)))
        for example, score in zip(examples, scores)
    ]
    assert summarize_seed_pairs(
        rows, backends=["local"], methods=["candidate", "reference"], examples=examples,
        reference_method="reference",
    ) == [{
        "backend": "local", "method": "candidate", "reference_method": "reference",
        "seed": -3, "status": "complete", "n_requested_pairs": 3,
        "n_complete_pairs": 3, "wins": 1, "ties": 1, "losses": 1, "mean_delta": 0.0,
    }]


def test_absent_reference_and_empty_cohort_do_not_invent_seed_estimates():
    rows, selection = _paired_inputs()
    original = copy.deepcopy((rows, selection))
    assert summarize_seed_pairs(rows, **{**selection, "reference_method": "not-selected"}) == []
    assert summarize_seed_pairs([], **{**selection, "examples": []}) == []
    assert summarize_seed_pairs(rows, **{**selection, "methods": ["full_context"]}) == []
    assert (rows, selection) == original
