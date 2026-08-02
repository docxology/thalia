"""Tests for the executable formalism-to-code publication contract."""

from pathlib import Path
from typing import Any, cast

import pytest

from src.formalism_traceability import (
    _has_manuscript_anchor,
    load_and_validate_traceability,
    traceability_markdown,
    validate_traceability,
)
from src.manuscript_integrity import load_paper_audit


PROJECT = Path(__file__).resolve().parent.parent


def _as_dynamic_mapping(value: object) -> dict[str, Any]:
    """Narrow JSON/YAML-shaped reports for mutation-focused contract tests."""
    return cast(dict[str, Any], value)


def test_project_traceability_resolves_symbols_tests_and_equations():
    report = _as_dynamic_mapping(load_and_validate_traceability())
    assert report["status"] == "pass"
    assert report["n_formalisms"] >= 15
    assert report["n_connections"] >= 4
    assert report["n_claims"] >= 8
    assert report["issues"] == []
    assert all(entry["invariant_anchors"] for entry in report["formalisms"])


def test_traceability_table_is_deterministic_and_exposes_contract_fields():
    first = traceability_markdown(_as_dynamic_mapping(load_paper_audit()))
    second = traceability_markdown(_as_dynamic_mapping(load_paper_audit()))
    assert first == second
    assert "`token_f1_set`" in first
    assert "src/compiler/metrics.py::token_f1" in first
    assert "Unit / estimand" in first
    assert "Invariant anchors" in first


def test_manuscript_anchor_parser_accepts_figure_attributes():
    assert _has_manuscript_anchor("![caption]{#fig:audit width=90%}", "fig:audit")
    assert _has_manuscript_anchor("text {eq:metric}", "eq:metric")
    assert not _has_manuscript_anchor("{#fig:other}", "fig:audit")


def test_traceability_rejects_missing_code_symbol():
    payload = _as_dynamic_mapping(load_paper_audit())
    payload["formalisms"] = [dict(payload["formalisms"][0], implementation="src/module.py::does_not_exist")]
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_code_symbol" for issue in report["issues"])


def test_traceability_rejects_missing_invariant_anchor():
    payload = _as_dynamic_mapping(load_paper_audit())
    formalism = dict(payload["formalisms"][0])
    anchors = dict(formalism["invariant_anchors"])
    del anchors["deterministic_tokenization"]
    formalism["invariant_anchors"] = anchors
    payload["formalisms"] = [formalism]
    with pytest.raises(ValueError, match="invariant_anchors"):
        validate_traceability(payload, project_root=PROJECT)


def test_traceability_rejects_missing_invariant_code_symbol():
    payload = _as_dynamic_mapping(load_paper_audit())
    formalism = dict(payload["formalisms"][0])
    formalism["invariant_anchors"] = {"deterministic_tokenization": "src/module.py::missing"}
    payload["formalisms"] = [formalism]
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_code_symbol" for issue in report["issues"])


def test_traceability_rejects_missing_equation_anchor():
    payload = _as_dynamic_mapping(load_paper_audit())
    payload["formalisms"] = [dict(payload["formalisms"][0], equation="eq:not_in_manuscript")]
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_equation_label" for issue in report["issues"])


def test_traceability_rejects_unknown_connection_node():
    payload = _as_dynamic_mapping(load_paper_audit())
    payload["connections"] = [dict(payload["connections"][0], sources=["missing_formalism"])]
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "unknown_connection_node" for issue in report["issues"])


def test_traceability_rejects_non_mapping_connection():
    payload = _as_dynamic_mapping(load_paper_audit())
    payload["connections"] = ["not a mapping"]
    with pytest.raises(ValueError, match="connections entries"):
        validate_traceability(payload, project_root=PROJECT)


def test_traceability_rejects_missing_claim_artifact():
    payload = _as_dynamic_mapping(load_paper_audit())
    payload["claims"] = [dict(payload["claims"][0], artifact="output/does-not-exist.json")]
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT, check_artifacts=True))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_artifact_path" for issue in report["issues"])


def test_traceability_rejects_missing_claim_test_anchor():
    payload = _as_dynamic_mapping(load_paper_audit())
    payload["claims"] = [dict(payload["claims"][0], tests=["tests/does_not_exist.py"])]
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_test_path" for issue in report["issues"])


def test_paper_audit_rejects_duplicate_notation_symbol():
    payload = _as_dynamic_mapping(load_paper_audit())
    notation = dict(payload["notation"])
    symbols = list(notation["symbols"])
    symbols.append(dict(symbols[0]))
    notation["symbols"] = symbols
    payload["notation"] = notation
    with pytest.raises(ValueError, match="duplicate notation symbol"):
        validate_traceability(payload, project_root=PROJECT)


def test_traceability_resolves_statistical_contract_anchors():
    payload = _as_dynamic_mapping(load_paper_audit())
    contracts = list(payload["statistical_contracts"])
    contracts[0] = dict(contracts[0], implementation="src/evaluation/statistics.py::missing_method")
    payload["statistical_contracts"] = contracts
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_code_symbol" for issue in report["issues"])


def test_traceability_rejects_unsafe_code_anchor():
    payload = _as_dynamic_mapping(load_paper_audit())
    payload["formalisms"] = [dict(payload["formalisms"][0], implementation="../outside.py::thing")]
    report = _as_dynamic_mapping(validate_traceability(payload, project_root=PROJECT))
    assert report["status"] == "fail"
    assert any(issue["kind"] == "unsafe_code_path" for issue in report["issues"])
