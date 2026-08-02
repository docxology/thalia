"""Tests for deterministic evaluation accounting and provenance."""

import json

import pytest

from src.evaluation.accounting import (
    deterministic_events,
    fingerprint_examples,
    ledger_row,
    validate_ledger,
    validate_event_stream,
    write_accounting_report,
    write_ledger_and_events,
)
from src.evaluation.dataset import build_research_dataset


def test_ledger_schema_and_event_order(tmp_path):
    example = build_research_dataset(1, 0)[0]
    fingerprint = fingerprint_examples([example])
    row = ledger_row(
        sequence=1,
        example=example,
        method="hybrid",
        metrics={"composite": 0.5},
        status="complete",
        config_fingerprint="config",
        dataset_fingerprint=fingerprint,
    )
    events = deterministic_events(
        [row],
        experiment="test",
        dataset_fingerprint=fingerprint,
        config_fingerprint="config",
        run_id="run",
    )
    ledger_path, event_path = write_ledger_and_events([row], events, tmp_path / "ledger.jsonl", tmp_path / "events.jsonl")
    loaded = json.loads(ledger_path.read_text())
    assert example.task_category is not None
    assert loaded["example_id"] == example.example_id
    assert loaded["status"] == "complete"
    assert loaded["content_fingerprint"]
    assert loaded["category"] == example.task_category.value
    assert [json.loads(line)["sequence"] for line in event_path.read_text().splitlines()] == [1, 2, 3]
    assert json.loads(event_path.read_text().splitlines()[-1])["event"] == "run_finished"
    assert json.loads(event_path.read_text().splitlines()[1])["dataset_fingerprint"] == fingerprint


def test_accounting_report_requires_current_schema_and_writes_atomically(tmp_path):
    path = tmp_path / "accounting.json"
    report = {"schema_version": 2, "experiment": "test", "n_failed": 0}
    assert write_accounting_report(report, path) == path
    assert json.loads(path.read_text()) == report
    with pytest.raises(ValueError, match="schema_version 2"):
        write_accounting_report({"schema_version": 1}, path)


def test_ledger_validation_requires_global_contiguous_sequence():
    example = build_research_dataset(1, 0)[0]
    row = ledger_row(
        sequence=1,
        example=example,
        method="hybrid",
        metrics={"composite": 0.5},
        status="complete",
        config_fingerprint="c",
        dataset_fingerprint="d",
    )
    with pytest.raises(ValueError, match="contiguous"):
        validate_ledger([{**row, "sequence": 2}])


def test_failure_is_accounted_by_class():
    example = build_research_dataset(1, 0)[0]
    row = ledger_row(
        sequence=1,
        example=example,
        method="lexical",
        metrics=None,
        status="failed",
        error=RuntimeError("capacity"),
        config_fingerprint="c",
        dataset_fingerprint="d",
    )
    assert row["error_class"] == "RuntimeError"
    assert deterministic_events([row], experiment="x", dataset_fingerprint="d", config_fingerprint="c", run_id="r")[1]["event"] == "run_failed"


def test_ledger_validation_rejects_missing_content_identity():
    example = build_research_dataset(1, 0)[0]
    row = ledger_row(
        sequence=1,
        example=example,
        method="hybrid",
        metrics={"composite": 0.5},
        status="complete",
        config_fingerprint="c",
        dataset_fingerprint="d",
    )
    row.pop("content_fingerprint")
    with pytest.raises(ValueError, match="content_fingerprint"):
        validate_ledger([row])


def test_ledger_validation_rejects_boolean_sequence_and_invalid_error_class():
    example = build_research_dataset(1, 0)[0]
    row = ledger_row(
        sequence=1,
        example=example,
        method="hybrid",
        metrics={"composite": 0.5},
        status="complete",
        config_fingerprint="c",
        dataset_fingerprint="d",
    )
    with pytest.raises(ValueError, match="contiguous"):
        validate_ledger([{**row, "sequence": True}])
    with pytest.raises(ValueError, match="error_class"):
        validate_ledger([{**row, "error_class": 7}])


def test_event_stream_must_match_ledger_rows():
    example = build_research_dataset(1, 0)[0]
    row = ledger_row(
        sequence=1,
        example=example,
        method="hybrid",
        metrics={"composite": 0.5},
        status="complete",
        config_fingerprint="c",
        dataset_fingerprint="d",
    )
    events = deterministic_events([row], experiment="x", dataset_fingerprint="d", config_fingerprint="c", run_id="r")
    with pytest.raises(ValueError, match="example_id"):
        validate_event_stream([events[0], {**events[1], "example_id": "other"}, events[2]], [row])
    with pytest.raises(ValueError, match="finish counts"):
        validate_event_stream([events[0], events[1], {**events[2], "n_evaluated": 99}], [row])
