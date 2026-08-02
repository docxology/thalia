"""Tests for the source-bound integrity-advantage evidence screen."""

from pathlib import Path

import pytest

from src.evaluation.integrity_advantage import (
    _binary_comparison,
    _load_json,
    _point_comparison,
    _require_rows,
    build_integrity_advantage_report,
)
from src.evaluation.schemas import IntegrityAdvantagePayload


def test_binary_comparison_normalizes_lower_is_better() -> None:
    record = _binary_comparison(
        comparison_id="poison",
        label="Poisoning",
        construct="context_poisoning",
        comparator="baseline",
        left_label="harness",
        right_label="baseline",
        left=[False, False, True, False],
        right=[True, False, True, True],
        direction="lower_is_better",
        unit="probe",
        evidence_tier="synthetic",
        claim_status="screen",
        interpretation="lower observed poisoning is favorable",
    )

    assert record["raw_delta"] == -0.5
    assert record["advantage_delta"] == 0.5
    assert record["raw_low"] == -1.0
    assert record["raw_high"] == 0.0
    assert record["low"] == 0.0
    assert record["high"] == 1.0
    assert record["left_rate"]["successes"] == 1
    assert record["right_rate"]["successes"] == 3
    assert record["left_success_right_failure"] == 0
    assert record["left_failure_right_success"] == 2


def test_report_has_separate_native_endpoint_rows() -> None:
    report = build_integrity_advantage_report(Path(__file__).resolve().parents[1])
    payload = IntegrityAdvantagePayload.from_json(report)
    rows = {row["id"]: row for row in payload.comparisons}

    assert set(rows) == {
        "orchestration_composite",
        "provenance_auditability",
        "poisoning_rate",
        "learned_retrieval_recall",
        "compiler_mipro_holdout",
        "local_neural_answer_f1",
        "adaptive_context_policy",
    }
    assert rows["provenance_auditability"]["advantage_delta"] == 1.0
    assert rows["provenance_auditability"]["construct"] == "lexical_cited_excerpt_source_exposure_proxy"
    assert "proxy" in rows["provenance_auditability"]["label"].lower()
    assert rows["poisoning_rate"]["construct"] == "recorded_poisoned_answer_rate"
    assert rows["orchestration_composite"]["component_deltas"]["answer_token_f1"] == 0.0
    assert rows["adaptive_context_policy"]["uncertainty_available"] is False
    assert payload.current_conclusions["general_answer_quality_status"] == "unestablished"
    assert report["promotion"] == {
        "status": "screen_only_unpromoted",
        "promoted": False,
        "p0_provenance_confirmation_executed": False,
        "p0_provenance_poisoning_separation_executed": False,
        "promotion_gate_passed": False,
        "reason": (
            "The P0 provenance confirmation and provenance-versus-poisoning "
            "separation studies are unexecuted; this report is an exploratory "
            "source-bound screen, not a promoted integrity claim."
        ),
    }
    assert {row["promotion_status"] for row in rows.values()} == {"screen_only_unpromoted"}


def test_integrity_helpers_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _load_json(tmp_path / "missing.json")
    invalid_json = tmp_path / "array.json"
    invalid_json.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        _load_json(invalid_json)
    with pytest.raises(ValueError, match="row objects"):
        _require_rows([], "rows")
    with pytest.raises(ValueError, match="row objects"):
        _require_rows(["bad"], "rows")
    with pytest.raises(ValueError, match="unsupported direction"):
        _binary_comparison(
            comparison_id="bad",
            label="bad",
            construct="bad",
            comparator="bad",
            left_label="left",
            right_label="right",
            left=[True],
            right=[False],
            direction="unknown",
            unit="probe",
            evidence_tier="synthetic",
            claim_status="screen",
            interpretation="bad",
        )
    with pytest.raises(ValueError, match="unsupported direction"):
        _point_comparison(
            comparison_id="bad",
            label="bad",
            construct="bad",
            comparator="bad",
            left_label="left",
            right_label="right",
            raw_delta=0.0,
            n=1,
            unit="probe",
            direction="unknown",
            evidence_tier="synthetic",
            claim_status="screen",
            interpretation="bad",
        )
