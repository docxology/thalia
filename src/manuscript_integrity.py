"""Manuscript reproducibility gates: token coverage and cross-reference integrity."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

_TOKEN_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
_REF_RE = re.compile(r"@((?:fig|sec|tbl|eq):[A-Za-z0-9_-]+)")
_DEF_BRACE_RE = re.compile(r"\{#((?:fig|sec|tbl|eq):[A-Za-z0-9_-]+)[^}]*\}")
_DEF_LABEL_RE = re.compile(r"\\label\{((?:fig|sec|tbl|eq):[A-Za-z0-9_-]+)\}")
_BIB_ENTRY_RE = re.compile(
    r"^@(?:article|inproceedings|misc|book|incollection|techreport|phdthesis)\{([^,\s]+),",
    re.MULTILINE | re.IGNORECASE,
)
_CITATION_KEY_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_:-]*)")
_NUMERIC_RE = re.compile(r"(?<![A-Za-z@])(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:%|[×x])?")
_RESULT_CONTEXT_RE = re.compile(
    r"(?:accuracy|token[- ]?f1|coverage|tests?|examples?|probes?|questions?|passes?|composite|"
    r"grounding|efficiency|budget|top[_ -]?k|max[_ -]?evidence|temperature|max[_ -]?tokens|"
    r"bootstrap|confidence|interval|p[- ]?value|recall|seeds?|strata|categories?|method rows|"
    r"sample|distractor|bytes?|digest|poison|audit|weight)",
    re.IGNORECASE,
)


def _strip_inline_math(text: str) -> str:
    """Remove inline/display math while preserving prose outside math regions."""
    # A line can contain both an equation and a hard-coded result. Remove only
    # math spans so the numeric lint remains fail-closed for the prose outside
    # those spans.
    text = re.sub(r"\$\$.*?\$\$", " ", text)
    text = re.sub(r"\$[^$\n]*\$", " ", text)
    text = re.sub(r"\\\([^\n]*?\\\)", " ", text)
    text = re.sub(r"\\\[[^\n]*?\\\]", " ", text)
    return text

_INJECTION_MARKER = Path("infrastructure") / "rendering" / "manuscript_injection.py"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CLAIM_REQUIRED_FIELDS = {"claim_id", "kind", "value", "source", "source_tier", "freshness", "artifact_path"}


def find_template_root(starts: tuple[Path, ...] | None = None) -> Path | None:
    """Return the template repo root containing ``infrastructure/rendering/``.

    Walks ancestors from each start path until the injection module exists. For
    private sidecar checkouts, also checks for a sibling ``template/`` checkout
    next to the ``projects/`` repo. Returns ``None`` when THALIA runs standalone
    outside any template tree.
    """
    seen: set[Path] = set()
    origins = starts if starts is not None else (Path.cwd(),)
    for start in origins:
        for candidate in (start, *start.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / _INJECTION_MARKER).exists():
                return candidate
            sibling_template = candidate / "template"
            if sibling_template not in seen and (sibling_template / _INJECTION_MARKER).exists():
                return sibling_template
    return None


def numbered_sections(manuscript_dir: Path) -> list[Path]:
    """Return numbered manuscript body files (``00_*.md`` … ``99_*.md``)."""
    return sorted(manuscript_dir.glob("[0-9]*.md"))


def tokens_used_in_manuscript(manuscript_dir: Path) -> set[str]:
    """Collect every ``{{TOKEN}}`` referenced in numbered body sections."""
    used: set[str] = set()
    for md in numbered_sections(manuscript_dir):
        used.update(_TOKEN_RE.findall(md.read_text()))
    return used


def check_crossref_integrity(manuscript_dir: Path) -> None:
    """Raise ValueError if any cross-reference lacks a definition anchor."""
    defined: set[str] = set()
    referenced: set[str] = set()
    for md in numbered_sections(manuscript_dir):
        body = md.read_text()
        defined.update(_DEF_BRACE_RE.findall(body))
        defined.update(_DEF_LABEL_RE.findall(body))
        referenced.update(_REF_RE.findall(body))
    dangling = sorted(referenced - defined)
    if dangling:
        raise ValueError(
            f"manuscript has {len(dangling)} dangling cross-reference(s): {dangling}"
        )


def bibliography_keys(path: str | Path) -> set[str]:
    """Return citation keys declared by a BibTeX bibliography."""
    source = Path(path)
    try:
        return set(_BIB_ENTRY_RE.findall(source.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"bibliography unreadable: {exc}") from exc


def citation_keys_in_manuscript(manuscript_dir: Path) -> set[str]:
    """Return bibliographic keys used in numbered manuscript sections.

    Pandoc cross-references also use ``@`` inside square brackets.  The known
    figure/section/table/equation namespaces are excluded so this check only
    reports bibliography citations.
    """
    keys: set[str] = set()
    for md in numbered_sections(manuscript_dir):
        body = md.read_text(encoding="utf-8")
        # Capture both bracketed Pandoc citations (``[@key]``) and narrative
        # citations (``@key``).  Cross-reference namespaces are excluded below.
        for key in _CITATION_KEY_RE.findall(body):
            if not key.startswith(("fig:", "sec:", "tbl:", "eq:")):
                keys.add(key)
    return keys


def check_bibliography_integrity(
    manuscript_dir: Path,
    bibliography_path: str | Path,
) -> tuple[set[str], set[str]]:
    """Raise on citations absent from the bibliography and return both sets."""
    used = citation_keys_in_manuscript(manuscript_dir)
    declared = bibliography_keys(bibliography_path)
    missing = used - declared
    if missing:
        raise ValueError(f"manuscript has {len(missing)} citation(s) missing from bibliography: {sorted(missing)}")
    return used, declared


def verify_token_coverage(
    variables: dict[str, str],
    manuscript_dir: Path,
) -> tuple[set[str], list[str]]:
    """Return (tokens used, sorted missing tokens not in ``variables``)."""
    used = tokens_used_in_manuscript(manuscript_dir)
    missing = sorted(used - set(variables))
    return used, missing


def find_hardcoded_numeric_claims(manuscript_dir: Path) -> list[tuple[str, int, str]]:
    """Find result-bearing numeric literals that bypass manuscript variables.

    This is intentionally a narrow lint rather than a ban on all digits: years,
    equations, citations, layout widths, and code examples are legitimate. A
    numeric literal on prose containing result/accounting vocabulary is not. The
    returned tuples are ``(relative_path, line_number, line)`` so CI can report a
    useful edit location without mutating the manuscript.
    """
    findings: list[tuple[str, int, str]] = []
    for path in numbered_sections(manuscript_dir):
        if path.name == "99_references.md":
            continue
        in_fence = False
        in_block_math = False
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if re.search(r"\\begin\{(?:equation|equation\*|align|align\*)\}|^\\\[|^\$\$", stripped):
                in_block_math = True
            if in_block_math:
                if re.search(r"\\end\{(?:equation|equation\*|align|align\*)\}|^\\\]|^\$\$", stripped):
                    in_block_math = False
                continue
            if in_fence or not _RESULT_CONTEXT_RE.search(raw_line):
                continue
            # Remove generated placeholders before scanning; their values are the
            # allowed source of the numeric claim after hydration.
            candidate = _TOKEN_RE.sub("", raw_line)
            candidate = re.sub(r"\[@[^\]]+\]", "", candidate)
            candidate = re.sub(r"@\d+", "", candidate)
            candidate = re.sub(r"\b[A-Za-z][A-Za-z0-9_-]*\d[A-Za-z0-9_-]*\b", "", candidate)
            candidate = re.sub(r"width\s*=\s*\d+%", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\b20\d{2}\b", "", candidate)  # citation/publication years
            candidate = re.sub(r"\b\d+-based\b", "", candidate)
            if ".md" in candidate and not re.search(r"(?:=|\d+%)", candidate):
                continue  # section paths are structural references, not result claims
            candidate = _strip_inline_math(candidate)
            if _NUMERIC_RE.search(candidate):
                findings.append((path.relative_to(manuscript_dir).as_posix(), line_number, raw_line.strip()))
    return findings


def load_paper_audit(path: str | Path | None = None) -> dict[str, object]:
    """Load the machine-readable claim/formalism audit ledger."""
    source = Path(path) if path is not None else _PROJECT_ROOT / "data" / "paper_audit.yaml"
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - project dependency is pinned
        raise ValueError("PyYAML is required to load the paper audit ledger") from exc
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"paper audit ledger unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("paper audit ledger must contain a mapping")
    return payload


def load_claim_ledger(path: str | Path | None = None) -> dict[str, object]:
    """Load the machine-readable numeric/source claim registry."""
    source = Path(path) if path is not None else _PROJECT_ROOT / "data" / "claim_ledger.yaml"
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - project dependency is pinned
        raise ValueError("PyYAML is required to load the claim ledger") from exc
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"claim ledger unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("claim ledger must contain a mapping")
    return payload


def validate_claim_ledger(
    payload: dict[str, object],
    *,
    project_root: str | Path = _PROJECT_ROOT,
    check_artifacts: bool = False,
) -> None:
    """Validate claim identity, value types, safe anchors, and optional JSON values.

    This is a source/registry contract, not a proof of scientific validity.  When
    ``check_artifacts`` is enabled, claims with ``artifact_field`` are also checked
    against the generated JSON artifact named by ``artifact_path``.
    """
    entries = payload.get("claims")
    if not isinstance(entries, list) or not entries:
        raise ValueError("claim ledger claims must be a non-empty list")
    root = Path(project_root).resolve()
    seen: set[str] = set()
    issues: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"claim {index} must be a mapping")
            continue
        missing = sorted(_CLAIM_REQUIRED_FIELDS - set(entry))
        if missing:
            issues.append(f"claim {index} missing fields: {missing}")
            continue
        claim_id = entry["claim_id"]
        if not isinstance(claim_id, str) or not claim_id.strip():
            issues.append(f"claim {index} requires a non-empty claim_id")
            continue
        if claim_id in seen:
            issues.append(f"duplicate claim_id: {claim_id}")
        seen.add(claim_id)
        kind = entry["kind"]
        value = entry["value"]
        if kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                issues.append(f"claim {claim_id} number value must be finite")
        elif kind == "string":
            if not isinstance(value, str) or not value.strip():
                issues.append(f"claim {claim_id} string value must be non-empty text")
        else:
            issues.append(f"claim {claim_id} has unsupported kind: {kind!r}")
        for field in ("source", "source_tier", "freshness"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                issues.append(f"claim {claim_id}.{field} must be non-empty text")
        artifact = entry["artifact_path"]
        if not isinstance(artifact, str) or not artifact.strip():
            issues.append(f"claim {claim_id}.artifact_path must be non-empty text")
            continue
        artifact_path = Path(artifact)
        if artifact_path.is_absolute() or ".." in artifact_path.parts:
            issues.append(f"claim {claim_id} has unsafe artifact path: {artifact}")
            continue
        resolved = root / artifact_path
        if not check_artifacts:
            continue
        if not resolved.is_file() or resolved.is_symlink():
            issues.append(f"claim {claim_id} artifact missing or symlinked: {artifact}")
            continue
        field_path = entry.get("artifact_field")
        if field_path is None:
            continue
        if not isinstance(field_path, str) or not field_path.strip():
            issues.append(f"claim {claim_id}.artifact_field must be non-empty text")
            continue
        try:
            artifact_payload = json.loads(resolved.read_text(encoding="utf-8"))
            actual: object = artifact_payload
            for component in field_path.split("."):
                if not isinstance(actual, dict) or component not in actual:
                    raise KeyError(component)
                actual = actual[component]
            tolerance = float(entry.get("artifact_value_tolerance", 0.0))
            if not math.isfinite(tolerance) or tolerance < 0:
                raise ValueError("artifact_value_tolerance must be finite and non-negative")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(float(actual)):
                    raise ValueError("artifact value is not a finite number")
                if abs(float(actual) - float(value)) > tolerance:
                    raise ValueError(f"artifact value {actual!r} differs from claim {value!r}")
            elif actual != value:
                raise ValueError(f"artifact value {actual!r} differs from claim {value!r}")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            issues.append(f"claim {claim_id} artifact field {field_path!r} invalid: {exc}")
    if issues:
        raise ValueError("claim ledger validation failed: " + "; ".join(issues))


def validate_paper_audit(payload: dict[str, object]) -> None:
    """Validate required fields and unique identifiers in the audit ledger.

    The ledger is deliberately stricter than a bibliography: a formal object must
    declare its unit, estimand, code/test anchors, and manuscript section, while a
    connection must state the relation that composes source and target objects.
    This keeps prose, equations, implementation, and evidence auditable as one
    contract.
    """
    for key in ("schema_version", "scope", "evidence_boundary", "interpretation_policy", "formalisms", "connections", "claims"):
        if key not in payload:
            raise ValueError(f"paper audit ledger missing {key!r}")
    for section in ("formalisms", "claims"):
        entries = payload[section]
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"paper audit {section} must be a non-empty list")
        ids: set[str] = set()
        required = (
            {"id", "strength", "implementation", "artifact", "token_source", "evidence_tier", "limitation"}
            if section == "claims"
            else {
                "id", "equation", "implementation", "tests", "evidence_tier", "limitation",
                "unit", "estimand", "inputs", "outputs", "dependencies", "invariants", "manuscript_sections",
            }
        )
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"paper audit {section} entries must be mappings")
            identifier = entry.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"paper audit {section} entries require non-empty id")
            if identifier in ids:
                raise ValueError(f"duplicate paper audit id: {identifier}")
            ids.add(identifier)
            missing = sorted(required - set(entry))
            if missing:
                raise ValueError(f"paper audit {identifier} missing fields: {missing}")
            if section == "claims":
                for field in ("strength", "artifact", "token_source", "evidence_tier", "limitation"):
                    value = entry.get(field)
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(f"paper audit {identifier}.{field} must be non-empty text")
            fields_to_validate = (
                ("implementation", "tests", "inputs", "outputs", "dependencies", "invariants", "manuscript_sections")
                if section == "formalisms"
                else ("implementation", "tests")
            )
            for field in fields_to_validate:
                value = entry.get(field)
                if isinstance(value, str):
                    continue
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise ValueError(f"paper audit {identifier}.{field} must be a string or list of strings")

    connections = payload["connections"]
    if not isinstance(connections, list):
        raise ValueError("paper audit connections must be a list")
    connection_ids: set[str] = set()
    for connection in connections:
        if not isinstance(connection, dict):
            raise ValueError("paper audit connections entries must be mappings")
        identifier = connection.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("paper audit connections require non-empty id")
        if identifier in connection_ids:
            raise ValueError(f"duplicate paper audit connection id: {identifier}")
        connection_ids.add(identifier)
        required = {"id", "sources", "targets", "relation", "implementation", "tests", "manuscript_anchor"}
        missing = sorted(required - set(connection))
        if missing:
            raise ValueError(f"paper audit connection {identifier} missing fields: {missing}")
        for field in ("sources", "targets", "implementation", "tests"):
            value = connection[field]
            if isinstance(value, str):
                continue
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"paper audit connection {identifier}.{field} must be a string or list of strings")


def write_paper_audit_json(
    output_path: str | Path,
    source_path: str | Path | None = None,
) -> Path:
    """Validate and serialize the audit ledger as a deterministic artifact."""
    payload = load_paper_audit(source_path)
    validate_paper_audit(payload)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


__all__ = [
    "find_template_root",
    "numbered_sections",
    "tokens_used_in_manuscript",
    "check_crossref_integrity",
    "bibliography_keys",
    "citation_keys_in_manuscript",
    "check_bibliography_integrity",
    "verify_token_coverage",
    "find_hardcoded_numeric_claims",
    "load_claim_ledger",
    "validate_claim_ledger",
    "load_paper_audit",
    "validate_paper_audit",
    "write_paper_audit_json",
]
