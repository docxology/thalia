"""Tests for the executable formalism-to-code publication contract."""

from pathlib import Path

import pytest

from src.formalism_traceability import (
    load_and_validate_traceability,
    traceability_markdown,
    validate_traceability,
)
from src.manuscript_integrity import load_paper_audit


PROJECT = Path(__file__).resolve().parent.parent


def test_project_traceability_resolves_symbols_tests_and_equations():
    report = load_and_validate_traceability()
    assert report["status"] == "pass"
    assert report["n_formalisms"] >= 15
    assert report["n_connections"] >= 4
    assert report["n_claims"] >= 8
    assert report["issues"] == []


def test_traceability_table_is_deterministic_and_exposes_contract_fields():
    first = traceability_markdown(load_paper_audit())
    second = traceability_markdown(load_paper_audit())
    assert first == second
    assert "`token_f1_set`" in first
    assert "src/compiler/metrics.py::token_f1" in first
    assert "Unit / estimand" in first


def test_traceability_rejects_missing_code_symbol():
    payload = load_paper_audit()
    payload["formalisms"] = [dict(payload["formalisms"][0], implementation="src/module.py::does_not_exist")]
    report = validate_traceability(payload, project_root=PROJECT)
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_code_symbol" for issue in report["issues"])


def test_traceability_rejects_missing_equation_anchor():
    payload = load_paper_audit()
    payload["formalisms"] = [dict(payload["formalisms"][0], equation="eq:not_in_manuscript")]
    report = validate_traceability(payload, project_root=PROJECT)
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_equation_label" for issue in report["issues"])


def test_traceability_rejects_unknown_connection_node():
    payload = load_paper_audit()
    payload["connections"] = [dict(payload["connections"][0], sources=["missing_formalism"])]
    report = validate_traceability(payload, project_root=PROJECT)
    assert report["status"] == "fail"
    assert any(issue["kind"] == "unknown_connection_node" for issue in report["issues"])


def test_traceability_rejects_non_mapping_connection():
    payload = load_paper_audit()
    payload["connections"] = ["not a mapping"]
    with pytest.raises(ValueError, match="connections entries"):
        validate_traceability(payload, project_root=PROJECT)


def test_traceability_rejects_missing_claim_artifact():
    payload = load_paper_audit()
    payload["claims"] = [dict(payload["claims"][0], artifact="output/does-not-exist.json")]
    report = validate_traceability(payload, project_root=PROJECT, check_artifacts=True)
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_artifact_path" for issue in report["issues"])


def test_traceability_rejects_missing_claim_test_anchor():
    payload = load_paper_audit()
    payload["claims"] = [dict(payload["claims"][0], tests=["tests/does_not_exist.py"])]
    report = validate_traceability(payload, project_root=PROJECT)
    assert report["status"] == "fail"
    assert any(issue["kind"] == "missing_test_path" for issue in report["issues"])


def test_traceability_rejects_unsafe_code_anchor():
    payload = load_paper_audit()
    payload["formalisms"] = [dict(payload["formalisms"][0], implementation="../outside.py::thing")]
    report = validate_traceability(payload, project_root=PROJECT)
    assert report["status"] == "fail"
    assert any(issue["kind"] == "unsafe_code_path" for issue in report["issues"])
