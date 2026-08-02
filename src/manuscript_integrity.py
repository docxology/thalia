"""Manuscript reproducibility gates: token coverage and cross-reference integrity."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Mapping

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
    r"grounding|support|reachability|efficiency|budget|top[_ -]?k|max[_ -]?evidence|temperature|max[_ -]?tokens|"
    r"bootstrap|confidence|interval|p[- ]?value|recall|seeds?|strata|categories?|method rows|"
    r"sample|distractor|bytes?|digest|poison|audit|weight|quality|faithful|safety|"
    r"adjudicat|judge|pilot|confirmatory)",
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
_INTEGRITY_ADVANTAGE_PATH = Path("data") / "integrity_advantage.json"
_INTEGRITY_ADVANTAGE_CURRENT_IDS = {
    "orchestration_composite",
    "provenance_auditability",
    "poisoning_rate",
    "learned_retrieval_recall",
    "compiler_mipro_holdout",
    "local_neural_answer_f1",
    "adaptive_context_policy",
}
_INTEGRITY_ADVANTAGE_SOURCE_INPUTS = {
    "data/injection_eval.json",
    "data/learned_retrieval.json",
    "data/longmemeval_bottleneck.json",
    "data/neural_eval.json",
    "output/data/compiler_generalization.json",
}
_INTEGRITY_ADVANTAGE_ANALYSIS_CODE = {
    "src/evaluation/ablation.py",
    "src/evaluation/integrity_advantage.py",
    "src/evaluation/statistics.py",
}


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


def _validate_bibliography_records(path: str | Path) -> None:
    """Check duplicate keys and the minimum scholarly metadata contract."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"bibliography unreadable: {exc}") from exc
    entries = list(re.finditer(r"^@(?P<kind>[A-Za-z][A-Za-z0-9_]*)\{(?P<key>[^,\s]+),", text, re.MULTILINE))
    seen: set[str] = set()
    allowed = {"article", "inproceedings", "misc", "book", "incollection", "techreport", "phdthesis", "online"}
    for index, match in enumerate(entries):
        kind = match.group("kind").lower()
        key = match.group("key")
        if key in seen:
            raise ValueError(f"bibliography has duplicate citation key: {key}")
        seen.add(key)
        end = entries[index + 1].start() if index + 1 < len(entries) else len(text)
        body = text[match.end() : end]
        if kind not in allowed:
            continue
        fields = {field.lower() for field in re.findall(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=", body, re.MULTILINE)}
        missing = sorted(field for field in ("title", "author") if field not in fields)
        if "year" not in fields and not ({"doi", "url", "howpublished"} & fields):
            missing.append("year-or-identifier")
        if missing:
            raise ValueError(f"bibliography entry {key} missing scholarly metadata: {missing}")


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
    _validate_bibliography_records(bibliography_path)
    return used, declared


def verify_token_coverage(
    variables: dict[str, str],
    manuscript_dir: Path,
) -> tuple[set[str], list[str]]:
    """Return (tokens used, sorted missing tokens not in ``variables``)."""
    used = tokens_used_in_manuscript(manuscript_dir)
    missing = sorted(used - set(variables))
    return used, missing


def verify_injected_manuscript(
    source_dir: str | Path,
    injected_dir: str | Path,
    variables: Mapping[str, str],
) -> tuple[Path, ...]:
    """Verify that the rendered manuscript is an exact token substitution.

    The external template injector is deliberately treated as a producer
    boundary: this gate independently reconstructs the expected contents from
    the numbered source sections and compares them with output/manuscript.
    It therefore catches missing sections, stale sections, unresolved tokens,
    and silent injector changes rather than merely checking that the output
    directory exists.
    """
    source = Path(source_dir)
    injected = Path(injected_dir)
    if not source.is_dir():
        raise ValueError(f"manuscript source directory is missing: {source}")
    if not injected.is_dir():
        raise ValueError(f"injected manuscript directory is missing: {injected}")

    source_files = numbered_sections(source)
    injected_files = numbered_sections(injected)
    source_names = {path.name for path in source_files}
    injected_names = {path.name for path in injected_files}
    missing = sorted(source_names - injected_names)
    extra = sorted(injected_names - source_names)
    if missing or extra:
        raise ValueError(
            "injected manuscript file set drift: "
            f"missing={missing or []}, extra={extra or []}"
        )

    for source_path in source_files:
        try:
            source_text = source_path.read_text(encoding="utf-8")
            injected_text = (injected / source_path.name).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"could not read manuscript injection pair {source_path.name}: {exc}") from exc
        used = set(_TOKEN_RE.findall(source_text))
        missing_tokens = sorted(used - set(variables))
        if missing_tokens:
            raise ValueError(
                f"source section {source_path.name} uses tokens absent from variables: {missing_tokens}"
            )
        expected = source_text
        for token in sorted(used):
            expected = expected.replace("{{" + token + "}}", variables[token])
        unresolved = sorted(set(_TOKEN_RE.findall(injected_text)))
        if unresolved:
            raise ValueError(
                f"injected section {source_path.name} contains unresolved tokens: {unresolved}"
            )
        if injected_text != expected:
            raise ValueError(
                f"injected section {source_path.name} differs from exact source token substitution"
            )
    return tuple(injected / name for name in sorted(source_names))


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
            candidate = re.sub(r"^\s*\d+\.\s+", "", candidate)  # ordered-list marker
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
    payload: Mapping[str, object],
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


def _sha256(path: Path) -> str:
    """Return a file digest without relying on a mutable manifest entry."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_integrity_fingerprints(
    value: object,
    *,
    root: Path,
    field: str,
    issues: list[str],
) -> set[str]:
    """Refuse a screen whose declared source or analysis fingerprints drifted."""
    if not isinstance(value, list) or not value:
        issues.append(f"integrity advantage {field} must be a non-empty list")
        return set()
    seen: set[str] = set()
    for index, entry in enumerate(value):
        prefix = f"integrity advantage {field}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{prefix} must be a mapping")
            continue
        path_text = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size_bytes")
        if not isinstance(path_text, str) or not path_text:
            issues.append(f"{prefix}.path must be non-empty text")
            continue
        relative_path = Path(path_text)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            issues.append(f"{prefix}.path is unsafe: {path_text}")
            continue
        if path_text in seen:
            issues.append(f"{prefix}.path is duplicated: {path_text}")
            continue
        seen.add(path_text)
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            issues.append(f"{prefix}.sha256 must be a lowercase SHA-256 digest")
            continue
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            issues.append(f"{prefix}.size_bytes must be a non-negative integer")
            continue
        path = root / relative_path
        if not path.is_file() or path.is_symlink():
            issues.append(f"{prefix}.path is missing or symlinked: {path_text}")
            continue
        if path.stat().st_size != size:
            issues.append(f"{prefix}.size_bytes does not match current file: {path_text}")
        if _sha256(path) != digest:
            issues.append(f"{prefix}.sha256 does not match current file: {path_text}")
    return seen


def validate_integrity_advantage_report(
    *,
    project_root: str | Path = _PROJECT_ROOT,
    report_path: str | Path | None = None,
) -> None:
    """Validate the source-bound, explicitly unpromoted integrity screen.

    This is a release-time check, not a P0 evaluator.  It verifies that the
    committed endpoint screen still names the exact input and analysis files it
    was derived from, and that an unexecuted P0 cannot be represented as a
    promoted integrity result.
    """
    root = Path(project_root).resolve()
    source = Path(report_path) if report_path is not None else root / _INTEGRITY_ADVANTAGE_PATH
    if not source.is_absolute():
        source = root / source
    issues: list[str] = []
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"integrity advantage report unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("integrity advantage report must contain a mapping")

    if payload.get("schema_version") != 3:
        issues.append("integrity advantage report requires schema_version 3")
    if payload.get("analysis") != "integrity_advantage_audit_v1":
        issues.append("integrity advantage report has an unexpected analysis identifier")

    comparisons = payload.get("comparisons")
    if not isinstance(comparisons, list) or not comparisons:
        issues.append("integrity advantage report comparisons must be a non-empty list")
    else:
        comparison_ids: list[str] = []
        for index, row in enumerate(comparisons):
            prefix = f"integrity advantage comparison {index}"
            if not isinstance(row, dict):
                issues.append(f"{prefix} must be a mapping")
                continue
            identifier = row.get("id")
            if not isinstance(identifier, str) or not identifier:
                issues.append(f"{prefix}.id must be non-empty text")
                continue
            comparison_ids.append(identifier)
            if row.get("promotion_status") != "screen_only_unpromoted":
                issues.append(f"{prefix} must remain screen_only_unpromoted")
        duplicate_ids = sorted(identifier for identifier in set(comparison_ids) if comparison_ids.count(identifier) > 1)
        if duplicate_ids:
            issues.append(f"integrity advantage report has duplicate comparisons: {duplicate_ids}")
        missing_ids = sorted(_INTEGRITY_ADVANTAGE_CURRENT_IDS - set(comparison_ids))
        if missing_ids:
            issues.append(f"integrity advantage report is missing current comparisons: {missing_ids}")

    promotion = payload.get("promotion")
    if not isinstance(promotion, dict):
        issues.append("integrity advantage report requires promotion metadata")
    else:
        required_flags = (
            "promoted",
            "p0_provenance_confirmation_executed",
            "p0_provenance_poisoning_separation_executed",
            "promotion_gate_passed",
        )
        for field in required_flags:
            if not isinstance(promotion.get(field), bool):
                issues.append(f"integrity advantage promotion.{field} must be boolean")
        status = promotion.get("status")
        reason = promotion.get("reason")
        if status not in {"screen_only_unpromoted", "complete_not_promoted", "promoted"}:
            issues.append("integrity advantage promotion.status is invalid")
        if not isinstance(reason, str) or not reason.strip():
            issues.append("integrity advantage promotion.reason must be non-empty text")
        p0_executed = (
            promotion.get("p0_provenance_confirmation_executed") is True
            and promotion.get("p0_provenance_poisoning_separation_executed") is True
        )
        gate_passed = promotion.get("promotion_gate_passed") is True
        promoted = promotion.get("promoted") is True
        if not p0_executed:
            if status != "screen_only_unpromoted" or promoted or gate_passed:
                issues.append("unexecuted P0 integrity evidence must remain screen_only_unpromoted")
        elif promoted and (status != "promoted" or not gate_passed):
            issues.append("a promoted integrity result requires a passed P0 promotion gate")
        elif not promoted and status == "promoted":
            issues.append("promotion.status cannot be promoted when promoted is false")

    boundaries = payload.get("design_boundaries")
    required_boundaries = {
        "native_units_preserved": True,
        "pooled_effect_size": False,
        "population_inference": False,
        "human_quality_labels": False,
        "paired_rows_required_for_confirmation": True,
    }
    if not isinstance(boundaries, dict):
        issues.append("integrity advantage report requires design_boundaries")
    else:
        for field, expected in required_boundaries.items():
            if boundaries.get(field) is not expected:
                issues.append(f"integrity advantage design_boundaries.{field} must be {expected!r}")

    source_paths = _validate_integrity_fingerprints(
        payload.get("source_provenance"), root=root, field="source_provenance", issues=issues
    )
    analysis_paths = _validate_integrity_fingerprints(
        payload.get("analysis_code"), root=root, field="analysis_code", issues=issues
    )
    missing_source_inputs = sorted(_INTEGRITY_ADVANTAGE_SOURCE_INPUTS - source_paths)
    if missing_source_inputs:
        issues.append(f"integrity advantage report is missing source inputs: {missing_source_inputs}")
    missing_analysis_code = sorted(_INTEGRITY_ADVANTAGE_ANALYSIS_CODE - analysis_paths)
    if missing_analysis_code:
        issues.append(f"integrity advantage report is missing analysis code: {missing_analysis_code}")
    if issues:
        raise ValueError("integrity advantage validation failed: " + "; ".join(issues))


def validate_paper_audit(payload: Mapping[str, object]) -> None:
    """Validate required fields and unique identifiers in the audit ledger.

    The ledger is deliberately stricter than a bibliography: a formal object must
    declare its unit, estimand, code/test anchors, and manuscript section, while a
    connection must state the relation that composes source and target objects.
    This keeps prose, equations, implementation, and evidence auditable as one
    contract.
    """
    for key in (
        "schema_version",
        "scope",
        "evidence_boundary",
        "interpretation_policy",
        "notation",
        "statistical_contracts",
        "formalisms",
        "connections",
        "claims",
    ):
        if key not in payload:
            raise ValueError(f"paper audit ledger missing {key!r}")
    notation = payload["notation"]
    if not isinstance(notation, dict):
        raise ValueError("paper audit notation must be a mapping")
    supplemental_section = notation.get("supplemental_section")
    if not isinstance(supplemental_section, str) or not supplemental_section.strip():
        raise ValueError("paper audit notation requires supplemental_section")
    symbols = notation.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise ValueError("paper audit notation symbols must be a non-empty list")
    symbol_ids: set[str] = set()
    for symbol_entry in symbols:
        if not isinstance(symbol_entry, dict):
            raise ValueError("paper audit notation symbols must be mappings")
        symbol = symbol_entry.get("symbol")
        meaning = symbol_entry.get("meaning")
        if not isinstance(symbol, str) or not symbol.strip() or not isinstance(meaning, str) or not meaning.strip():
            raise ValueError("paper audit notation symbols require non-empty symbol and meaning")
        if symbol in symbol_ids:
            raise ValueError(f"duplicate notation symbol: {symbol}")
        symbol_ids.add(symbol)
    crosswalk = notation.get("crosswalk")
    if not isinstance(crosswalk, list) or not crosswalk:
        raise ValueError("paper audit notation crosswalk must be a non-empty list")
    for entry in crosswalk:
        if not isinstance(entry, dict):
            raise ValueError("paper audit notation crosswalk entries must be mappings")
        if not isinstance(entry.get("formalism"), str) or not entry["formalism"].strip():
            raise ValueError("paper audit notation crosswalk entries require a formalism")
        names = entry.get("symbols")
        if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names):
            raise ValueError("paper audit notation crosswalk symbols must be a non-empty list of strings")
        unknown = sorted(set(names) - symbol_ids)
        if unknown:
            raise ValueError(f"paper audit notation crosswalk has unknown symbols: {unknown}")
    statistical_contracts = payload["statistical_contracts"]
    if not isinstance(statistical_contracts, list) or not statistical_contracts:
        raise ValueError("paper audit statistical_contracts must be a non-empty list")
    statistical_ids: set[str] = set()
    statistical_required = {"id", "implementation", "tests", "method", "estimand", "interval_interpretation", "assumption"}
    for entry in statistical_contracts:
        if not isinstance(entry, dict):
            raise ValueError("paper audit statistical_contracts entries must be mappings")
        missing = sorted(statistical_required - set(entry))
        if missing:
            raise ValueError(f"paper audit statistical contract missing fields: {missing}")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in statistical_ids:
            raise ValueError(f"paper audit statistical contract requires a unique id: {identifier!r}")
        statistical_ids.add(identifier)
        for field in ("method", "estimand", "interval_interpretation", "assumption"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError(f"paper audit statistical contract {identifier}.{field} must be non-empty text")
    formalism_ids: set[str] = set()
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
                "unit", "estimand", "inputs", "outputs", "dependencies", "invariants", "invariant_anchors",
                "manuscript_sections",
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
            if section == "formalisms":
                formalism_ids.add(identifier)
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
            if section == "formalisms":
                invariant_names = [entry["invariants"]] if isinstance(entry["invariants"], str) else entry["invariants"]
                anchors = entry["invariant_anchors"]
                if not isinstance(anchors, dict):
                    raise ValueError(f"paper audit {identifier}.invariant_anchors must be a mapping")
                if not all(isinstance(key, str) and key for key in anchors):
                    raise ValueError(f"paper audit {identifier}.invariant_anchors keys must be non-empty text")
                missing_anchors = sorted(set(invariant_names) - set(anchors))
                extra_anchors = sorted(set(anchors) - set(invariant_names))
                if missing_anchors or extra_anchors:
                    detail = []
                    if missing_anchors:
                        detail.append(f"missing {missing_anchors}")
                    if extra_anchors:
                        detail.append(f"unknown {extra_anchors}")
                    raise ValueError(f"paper audit {identifier}.invariant_anchors: {', '.join(detail)}")
                for invariant_name in invariant_names:
                    anchor = anchors[invariant_name]
                    if isinstance(anchor, str) and anchor.strip():
                        continue
                    if isinstance(anchor, list) and anchor and all(isinstance(item, str) and item.strip() for item in anchor):
                        continue
                    raise ValueError(
                        f"paper audit {identifier}.invariant_anchors[{invariant_name}] "
                        "must be non-empty text or a list of non-empty text"
                    )
    crosswalk_ids = {entry["formalism"] for entry in crosswalk if isinstance(entry, dict)}
    missing_crosswalk = sorted(formalism_ids - crosswalk_ids)
    if missing_crosswalk:
        detail = []
        if missing_crosswalk:
            detail.append(f"missing {missing_crosswalk}")
        raise ValueError("paper audit notation crosswalk formalism ids: " + "; ".join(detail))

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
    "validate_integrity_advantage_report",
    "load_paper_audit",
    "validate_paper_audit",
    "write_paper_audit_json",
]
