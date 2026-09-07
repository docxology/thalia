"""Machine-checkable connections between paper formalisms and executable code.

The publication red-team treats a formalism as a contract, not decoration.  Each
registry node names an equation (or explicitly says that it is non-equational),
an implementation anchor, tests, a unit/estimand, and the manuscript section in
which the contract is stated.  Connections describe how nodes compose.  This
module validates those references with the Python AST and emits a deterministic
report suitable for artifact validation.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, cast

from .manuscript_integrity import load_paper_audit, validate_paper_audit


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class TraceabilityIssue:
    """One actionable registry validation issue."""

    kind: str
    identifier: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.identifier, "detail": self.detail}


def _as_list(value: object, *, field: str, identifier: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ValueError(f"{identifier}.{field} must be a string or list of strings")


def _as_mapping_list(value: object, *, field: str) -> list[Mapping[str, object]]:
    """Narrow a validated YAML sequence to mappings for static type checkers."""
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ValueError(f"{field} must be a list of mappings")
    return [cast(Mapping[str, object], item) for item in value]


def _source_names(path: Path) -> set[str]:
    """Return top-level and nested class/function names from a Python module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    def visit(body: Iterable[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = f"{prefix}.{node.name}" if prefix else node.name
                names.add(qualified)
                if isinstance(node, ast.ClassDef):
                    visit(node.body, qualified)

    visit(tree.body)
    return names


def _check_code_anchor(anchor: str, root: Path, identifier: str) -> TraceabilityIssue | None:
    path_text, separator, symbol = anchor.partition("::")
    relative_path = Path(path_text)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return TraceabilityIssue("unsafe_code_path", identifier, path_text)
    path = root / relative_path
    if not path.exists():
        return TraceabilityIssue("missing_code_path", identifier, path_text)
    if not separator:
        return None
    if not path.is_file() or path.suffix != ".py":
        return TraceabilityIssue("code_anchor_not_python_file", identifier, anchor)
    try:
        names = _source_names(path)
    except (OSError, SyntaxError) as exc:
        return TraceabilityIssue("unreadable_code_anchor", identifier, f"{anchor}: {exc}")
    if symbol not in names:
        return TraceabilityIssue("missing_code_symbol", identifier, anchor)
    return None


def _check_test_anchor(anchor: str, root: Path, identifier: str) -> TraceabilityIssue | None:
    """Resolve test files and optional ``::symbol`` selectors, not just paths."""
    path_text, separator, symbol = anchor.partition("::")
    relative_path = Path(path_text)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return TraceabilityIssue("unsafe_test_path", identifier, path_text)
    path = root / relative_path
    if not path.is_file():
        return TraceabilityIssue("missing_test_path", identifier, path_text)
    if not separator:
        return None
    if path.suffix != ".py":
        return TraceabilityIssue("test_anchor_not_python_file", identifier, anchor)
    try:
        names = _source_names(path)
    except (OSError, SyntaxError) as exc:
        return TraceabilityIssue("unreadable_test_anchor", identifier, f"{anchor}: {exc}")
    if symbol not in names:
        return TraceabilityIssue("missing_test_symbol", identifier, anchor)
    return None


def _all_manuscript_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "docs" / "manuscript").glob("[0-9]*.md"))
    )


def _has_manuscript_anchor(text: str, anchor: str) -> bool:
    """Recognize Pandoc/LaTeX anchors, including attributes on figures."""
    if f"{{{anchor}}}" in text or f"\\label{{{anchor}}}" in text:
        return True
    return re.search(r"\{#" + re.escape(anchor) + r"(?=[\s}])", text) is not None


def _validate_entry_paths(
    entry: Mapping[str, object],
    *,
    root: Path,
    manuscript_text: str,
    issues: list[TraceabilityIssue],
) -> None:
    identifier = str(entry.get("id", ""))
    implementation = _as_list(entry.get("implementation"), field="implementation", identifier=identifier)
    for anchor in implementation:
        issue = _check_code_anchor(anchor, root, identifier)
        if issue:
            issues.append(issue)
    for test_path in _as_list(entry.get("tests"), field="tests", identifier=identifier):
        issue = _check_test_anchor(test_path, root, identifier)
        if issue:
            issues.append(issue)
    for section in _as_list(entry.get("manuscript_sections"), field="manuscript_sections", identifier=identifier):
        if not (root / section).is_file():
            issues.append(TraceabilityIssue("missing_manuscript_section", identifier, section))
    equation = entry.get("equation")
    if equation != "none" and (not isinstance(equation, str) or not equation):
        issues.append(TraceabilityIssue("invalid_equation", identifier, repr(equation)))
    if isinstance(equation, str) and equation != "none" and not _has_manuscript_anchor(manuscript_text, equation):
        issues.append(TraceabilityIssue("missing_equation_label", identifier, equation))
    invariant_names = _as_list(entry.get("invariants"), field="invariants", identifier=identifier)
    raw_anchors = entry.get("invariant_anchors")
    if not isinstance(raw_anchors, Mapping):
        issues.append(TraceabilityIssue("invalid_invariant_anchors", identifier, repr(raw_anchors)))
        return
    anchor_names = {str(name) for name in raw_anchors}
    for invariant_name in invariant_names:
        if invariant_name not in raw_anchors:
            issues.append(TraceabilityIssue("missing_invariant_anchor", identifier, invariant_name))
            continue
        for anchor in _as_list(
            raw_anchors[invariant_name],
            field=f"invariant_anchors[{invariant_name}]",
            identifier=identifier,
        ):
            issue = _check_code_anchor(anchor, root, f"{identifier}.{invariant_name}")
            if issue:
                issues.append(issue)
    for anchor_name in sorted(anchor_names - set(invariant_names)):
        issues.append(TraceabilityIssue("unknown_invariant_anchor", identifier, anchor_name))


def _validate_claim_code_and_tests(
    claim: Mapping[str, object],
    *,
    root: Path,
    issues: list[TraceabilityIssue],
) -> None:
    """Resolve executable and test anchors declared for a claim."""
    identifier = str(claim.get("id", ""))
    for anchor in _as_list(claim.get("implementation"), field="implementation", identifier=identifier):
        issue = _check_code_anchor(anchor, root, identifier)
        if issue:
            issues.append(issue)
    for test_path in _as_list(claim.get("tests"), field="tests", identifier=identifier):
        issue = _check_test_anchor(test_path, root, identifier)
        if issue:
            issues.append(issue)


def _validate_claim_paths(
    claim: Mapping[str, object],
    *,
    root: Path,
    issues: list[TraceabilityIssue],
) -> None:
    """Resolve every executable, test, and artifact anchor declared for a claim."""
    _validate_claim_code_and_tests(claim, root=root, issues=issues)
    identifier = str(claim.get("id", ""))
    artifact = claim.get("artifact")
    if not isinstance(artifact, str) or not artifact.strip():
        issues.append(TraceabilityIssue("invalid_artifact_path", identifier, repr(artifact)))
    else:
        artifact_path = Path(artifact)
        if artifact_path.is_absolute() or ".." in artifact_path.parts:
            issues.append(TraceabilityIssue("unsafe_artifact_path", identifier, artifact))
        elif not (root / artifact_path).is_file():
            issues.append(TraceabilityIssue("missing_artifact_path", identifier, artifact))


def _validate_statistical_contracts(
    payload: Mapping[str, object],
    *,
    root: Path,
    issues: list[TraceabilityIssue],
) -> None:
    """Resolve the executable/test anchors for the declared statistics methods."""
    contracts = _as_mapping_list(payload.get("statistical_contracts", []), field="statistical_contracts")
    notation = payload.get("notation")
    if not isinstance(notation, Mapping):
        issues.append(TraceabilityIssue("missing_notation_contract", "notation", "notation must be a mapping"))
    else:
        section = notation.get("supplemental_section")
        if not isinstance(section, str) or not (root / section).is_file():
            issues.append(TraceabilityIssue("missing_notation_section", "notation", str(section)))
    for contract in contracts:
        identifier = str(contract.get("id", ""))
        for anchor in _as_list(contract.get("implementation"), field="implementation", identifier=identifier):
            issue = _check_code_anchor(anchor, root, identifier)
            if issue:
                issues.append(issue)
        for test_path in _as_list(contract.get("tests"), field="tests", identifier=identifier):
            issue = _check_test_anchor(test_path, root, identifier)
            if issue:
                issues.append(issue)


def validate_traceability(
    payload: Mapping[str, object],
    *,
    project_root: str | Path = PROJECT_ROOT,
    check_artifacts: bool = False,
) -> dict[str, object]:
    """Validate the formalism graph and return a deterministic audit report.

    Claim artifacts are optional during source-only checks (for example, before
    CI has generated ``output/``); the release report enables ``check_artifacts``
    after the artifact pipeline has materialized them.
    """
    root = Path(project_root).resolve()
    validate_paper_audit(dict(payload))
    issues: list[TraceabilityIssue] = []
    manuscript_text = _all_manuscript_text(root)

    formalisms = _as_mapping_list(payload.get("formalisms", []), field="formalisms")
    formalism_ids = {
        str(entry["id"])
        for entry in formalisms
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
    }
    for entry in formalisms:
        if not isinstance(entry, Mapping):
            continue
        _validate_entry_paths(entry, root=root, manuscript_text=manuscript_text, issues=issues)
        identifier = str(entry["id"])
        for dependency in _as_list(entry.get("dependencies", []), field="dependencies", identifier=identifier):
            if dependency not in formalism_ids:
                issues.append(TraceabilityIssue("unknown_dependency", identifier, dependency))

    _validate_statistical_contracts(payload, root=root, issues=issues)

    connections = _as_mapping_list(payload.get("connections", []), field="connections")
    connection_records: list[dict[str, object]] = []
    for connection in connections:
        identifier = str(connection.get("id", ""))
        sources = _as_list(connection.get("sources"), field="sources", identifier=identifier)
        targets = _as_list(connection.get("targets"), field="targets", identifier=identifier)
        for node in [*sources, *targets]:
            if node not in formalism_ids:
                issues.append(TraceabilityIssue("unknown_connection_node", identifier, node))
        for anchor in _as_list(connection.get("implementation"), field="implementation", identifier=identifier):
            issue = _check_code_anchor(anchor, root, identifier)
            if issue:
                issues.append(issue)
        for test_path in _as_list(connection.get("tests"), field="tests", identifier=identifier):
            issue = _check_test_anchor(test_path, root, identifier)
            if issue:
                issues.append(issue)
        manuscript_anchor = connection.get("manuscript_anchor")
        if isinstance(manuscript_anchor, str) and manuscript_anchor != "none":
            if not _has_manuscript_anchor(manuscript_text, manuscript_anchor):
                issues.append(TraceabilityIssue("missing_manuscript_anchor", identifier, manuscript_anchor))
        connection_records.append(
            {
                "id": identifier,
                "sources": sources,
                "targets": targets,
                "relation": connection.get("relation", ""),
                "implementation": connection.get("implementation", []),
                "tests": connection.get("tests", []),
                "manuscript_anchor": manuscript_anchor,
            }
        )

    formalism_records = [dict(entry) for entry in formalisms]
    claims = _as_mapping_list(payload.get("claims", []), field="claims")
    claim_records: list[dict[str, object]] = []
    for claim in claims:
        if check_artifacts:
            _validate_claim_paths(claim, root=root, issues=issues)
        else:
            _validate_claim_code_and_tests(claim, root=root, issues=issues)
        claim_records.append(dict(claim))
    return {
        "schema_version": 1,
        "status": "pass" if not issues else "fail",
        "n_formalisms": len(formalism_records),
        "n_connections": len(connection_records),
        "n_statistical_contracts": len(_as_mapping_list(payload.get("statistical_contracts", []), field="statistical_contracts")),
        "n_notation_symbols": len(
            _as_mapping_list(cast(Mapping[str, object], payload["notation"]).get("symbols", []), field="notation.symbols")
        ),
        "n_claims": len(claim_records),
        "formalisms": formalism_records,
        "connections": connection_records,
        "claims": claim_records,
        "issues": [issue.to_dict() for issue in issues],
    }


def load_and_validate_traceability(
    path: str | Path | None = None,
    *,
    project_root: str | Path = PROJECT_ROOT,
    check_artifacts: bool = False,
) -> dict[str, object]:
    """Load the project audit ledger and validate its code-paper graph."""
    return validate_traceability(load_paper_audit(path), project_root=project_root, check_artifacts=check_artifacts)


def write_traceability_report(
    output_path: str | Path,
    *,
    source_path: str | Path | None = None,
    project_root: str | Path = PROJECT_ROOT,
    check_artifacts: bool = True,
) -> Path:
    """Validate and serialize the graph, refusing to write a failed report.

    Source-only generation is useful in a clean checkout before ``output/`` has
    been materialized.  The release validator passes ``check_artifacts=True``
    after the canonical artifact chain has run.
    """
    report = load_and_validate_traceability(
        source_path,
        project_root=project_root,
        check_artifacts=check_artifacts,
    )
    if report["status"] != "pass":
        raise ValueError(f"formalism traceability failed: {report['issues']}")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def traceability_markdown(
    payload: Mapping[str, object] | None = None,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> str:
    """Render a compact registry table for direct manuscript injection."""
    data = payload or load_paper_audit()
    report = validate_traceability(data, project_root=project_root)
    if report["status"] != "pass":
        raise ValueError(f"cannot render failed traceability graph: {report['issues']}")
    rows = [
        "| Formal object | Equation | Executable anchor | Test anchor | Invariant anchors | Unit / estimand |",
        "|---|---|---|---|---|---|",
    ]
    for entry in _as_mapping_list(data.get("formalisms", []), field="formalisms"):
        implementation = ", ".join(_as_list(entry["implementation"], field="implementation", identifier=str(entry["id"])))
        tests = ", ".join(_as_list(entry["tests"], field="tests", identifier=str(entry["id"])))
        invariant_anchors = entry["invariant_anchors"]
        if not isinstance(invariant_anchors, Mapping):
            raise ValueError(f"{entry['id']}.invariant_anchors must be a mapping")
        # Keep the manuscript table readable: the machine-readable report carries
        # the full code/test paths, while the table exposes the invariant names
        # whose anchors the validator has resolved.
        anchors = ", ".join(str(name).replace("_", " ") for name in invariant_anchors)
        rows.append(
            f"| `{entry['id']}` | `{entry['equation']}` | `{implementation}` | `{tests}` | "
            f"{anchors} | {entry['unit']} / {entry['estimand']} |"
        )
    return "\n".join(rows)


__all__ = [
    "load_and_validate_traceability",
    "traceability_markdown",
    "validate_traceability",
    "write_traceability_report",
]
