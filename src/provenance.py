"""Deterministic provenance helpers for THALIA generated outputs.

The template validator consumes project-local registries from ``output/``.  These
helpers write those registries from source code so the files are regenerable and
the manuscript/render gates do not depend on hand-edited output artifacts.
"""

from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable

from .figures.manifest import FIGURE_CAPTIONS, FIGURE_LABELS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output"

_MANIFEST_EXCLUDE_NAMES = {
    "artifact_manifest.json",
    "diagnostics.json",
    "evidence_registry.json",
    "lessons.jsonl",
    "lessons.md",
    "next_run_context.md",
    "output_statistics.json",
    "output_statistics.txt",
    "pause_recommendations.json",
    "telemetry.json",
    "telemetry.txt",
    "test_results.json",
    "test_results.md",
    "validation_report.json",
    "validation_report.md",
    "coverage.json",
    "pytest.xml",
}


@dataclass(frozen=True)
class VerificationSummary:
    """Small generated record of the live gates THALIA expects reviewers to run."""

    test_command: str
    coverage_gate: int
    render_command: str
    validation_command: str
    status: str = "commands-documented"
    latest_observed_tests: str = ""
    latest_observed_coverage: str = ""
    command_results: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-ready representation."""
        return asdict(self)


@dataclass(frozen=True)
class ArtifactValidation:
    """Result of checking generated artifacts against their manifest."""

    ok: bool
    checked: int
    required: int
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-ready validation report."""
        return {
            "ok": self.ok,
            "checked": self.checked,
            "required": self.required,
            "issues": list(self.issues),
        }


def default_verification_summary() -> VerificationSummary:
    """Return the canonical command summary for this project checkout."""
    return VerificationSummary(
        test_command=(
            "PYTHONWARNINGS=error::ResourceWarning uv run --project . --extra dev python -m pytest tests/ "
            "--cov=src --cov-report=term-missing --cov-report=json:output/reports/coverage.json "
            "--junitxml=output/reports/pytest.xml --cov-fail-under=90"
        ),
        coverage_gate=_coverage_gate(),
        render_command=(
            "EXTERNAL: uv run --project ../template python scripts/render_pdf_external.py "
            "(requires a populated sibling template checkout)"
        ),
        validation_command=(
            "EXTERNAL: uv run --project ../template python scripts/render_pdf_external.py --validate "
            "(requires a populated sibling template checkout)"
        ),
    )


def write_verification_summary(
    output_path: str | Path = OUTPUT_ROOT / "reports" / "verification_summary.json",
    *,
    summary: VerificationSummary | None = None,
) -> Path:
    """Write the verification summary and return its path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if summary is None and path.exists():
        # Artifact-generation scripts run after verification in the canonical
        # workflow.  Preserve observed evidence instead of silently replacing it
        # with a blank command-only record, while refreshing command text from the
        # current source of truth so stale renderer paths cannot persist.
        try:
            payload = load_verification_summary(path).to_dict()
            canonical = default_verification_summary().to_dict()
            for key in ("test_command", "coverage_gate", "render_command", "validation_command"):
                payload[key] = canonical[key]
        except (OSError, ValueError, TypeError):
            payload = default_verification_summary().to_dict()
    else:
        payload = (summary or default_verification_summary()).to_dict()
    if summary is None:
        _refresh_observed_verification(payload, path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _refresh_observed_verification(payload: dict[str, object], reports_dir: Path) -> None:
    """Refresh live test, coverage, and artifact claims from gate reports."""
    junit_path = reports_dir / "pytest.xml"
    coverage_path = reports_dir / "coverage.json"
    results = payload.get("command_results")
    command_results = dict(results) if isinstance(results, dict) else {}

    if junit_path.is_file() and coverage_path.is_file():
        try:
            root = ET.parse(junit_path).getroot()
            suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
            tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
            failures = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
            errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
            skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)
            coverage_payload = json.loads(coverage_path.read_text(encoding="utf-8"))
            totals = coverage_payload.get("totals", {})
            coverage = float(totals["percent_covered"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, ET.ParseError):
            tests = failures = errors = skipped = 0
            coverage = None
        if coverage is not None:
            passed = tests - failures - errors - skipped
            coverage_gate = payload.get("coverage_gate")
            gate = coverage_gate if isinstance(coverage_gate, int) else _coverage_gate()
            command_results["tests"] = {
                "collected": tests,
                "passed": passed,
                "failed": failures + errors,
                "skipped": skipped,
                "coverage_percent": round(coverage, 2),
                "coverage_gate": gate,
                "resource_warnings_as_errors": True,
                "status": "pass" if failures == 0 and errors == 0 and coverage >= gate else "fail",
            }
            payload["latest_observed_tests"] = f"{passed} passed; {tests} collected"
            payload["latest_observed_coverage"] = f"{coverage:.2f}% (src; gate {gate}%)"

    manifest_path = reports_dir / "artifact_manifest.json"
    if manifest_path.is_file():
        artifact_report = validate_artifact_manifest(
            reports_dir.parent.parent,
            manifest_path=manifest_path,
        )
        command_results["artifact_pipeline"] = {
            "checked": artifact_report.checked,
            "required": artifact_report.required,
            "issues": list(artifact_report.issues),
            "status": "pass" if artifact_report.ok else "fail",
        }

    if not command_results:
        return
    payload["command_results"] = command_results
    statuses = [
        value.get("status")
        for value in command_results.values()
        if isinstance(value, dict) and isinstance(value.get("status"), str)
    ]
    if statuses:
        payload["status"] = "pass" if all(status == "pass" for status in statuses) else "fail"


def load_verification_summary(
    path: str | Path = OUTPUT_ROOT / "reports" / "verification_summary.json",
) -> VerificationSummary:
    """Load a generated summary, falling back to canonical commands if absent."""
    source = Path(path)
    if not source.exists():
        return default_verification_summary()
    payload = json.loads(source.read_text(encoding="utf-8"))
    return VerificationSummary(**payload)


def write_figure_registry(
    figure_paths: Iterable[str | Path],
    output_path: str | Path = OUTPUT_ROOT / "figures" / "figure_registry.json",
) -> Path:
    """Write the template-compatible figure registry for generated PNGs."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict[str, object]] = {}
    for figure_path in sorted((Path(p) for p in figure_paths), key=lambda p: p.name):
        stem = figure_path.stem
        label = FIGURE_LABELS.get(stem, f"fig:{stem}")
        entries[label] = {
            "filename": figure_path.name,
            "label": label,
            "caption": FIGURE_CAPTIONS.get(stem, "Generated THALIA figure."),
            "alt": FIGURE_CAPTIONS.get(stem, "Generated THALIA figure."),
            "generated_by": "scripts/generate_figures.py",
            "source": "src/figures/",
        }
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_artifact_manifest(
    project_root: str | Path = PROJECT_ROOT,
    output_path: str | Path | None = None,
) -> Path:
    """Write a current, validator-compatible manifest for stable THALIA outputs."""
    root = Path(project_root).resolve()
    out = Path(output_path) if output_path else root / "output" / "reports" / "artifact_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    for artifact in _stable_artifacts(root):
        entries.append(
            {
                "contract_match": True,
                "path": artifact.relative_to(root).as_posix(),
                "sha256": _sha256(artifact),
                "size_bytes": artifact.stat().st_size,
                "stage_name": "THALIA provenance refresh",
                "stage_num": 0,
                "timestamp": "deterministic",
            }
        )
    payload = {"entries": entries, "issues": []}
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def validate_artifact_manifest(
    project_root: str | Path = PROJECT_ROOT,
    manifest_path: str | Path | None = None,
    required_paths: Iterable[str] | None = None,
) -> ArtifactValidation:
    """Validate manifest paths, hashes, sizes, and required artifact coverage.

    The writer records the current state; this validator is the independent
    refusal boundary that detects a post-generation mutation, missing output, or
    unsafe path. By default, required paths come from ``domain_profile.yaml``'s
    ``artifact_expectations`` list, keeping the research-domain declaration as
    the artifact completeness source of truth.
    """
    root = Path(project_root).resolve()
    source = Path(manifest_path) if manifest_path else root / "output" / "reports" / "artifact_manifest.json"
    issues: list[str] = []
    if not source.exists():
        return ArtifactValidation(False, 0, 0, (f"manifest missing: {source}",))
    if source.is_symlink():
        return ArtifactValidation(False, 0, 0, (f"manifest must not be a symlink: {source}",))
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ArtifactValidation(False, 0, 0, (f"manifest unreadable: {exc}",))

    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return ArtifactValidation(False, 0, 0, ("manifest entries must be a list",))

    paths_seen: set[str] = set()
    checked = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"entry {index} is not a mapping")
            continue
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel:
            issues.append(f"entry {index} has no relative path")
            continue
        normalized = PurePosixPath(rel)
        if normalized.is_absolute() or ".." in normalized.parts:
            issues.append(f"unsafe artifact path: {rel}")
            continue
        if rel in paths_seen:
            issues.append(f"duplicate artifact path: {rel}")
            continue
        paths_seen.add(rel)
        artifact = root.joinpath(*normalized.parts)
        if artifact.is_symlink():
            issues.append(f"artifact must not be a symlink: {rel}")
            continue
        try:
            artifact.resolve(strict=False).relative_to(root)
        except ValueError:
            issues.append(f"unsafe artifact path: {rel}")
            continue
        if not artifact.is_file():
            issues.append(f"artifact missing: {rel}")
            continue
        checked += 1
        if entry.get("contract_match") is not True:
            issues.append(f"contract mismatch: {rel}")
        expected_size = entry.get("size_bytes")
        if expected_size != artifact.stat().st_size:
            issues.append(f"size mismatch: {rel}")
        expected_hash = entry.get("sha256")
        if expected_hash != _sha256(artifact):
            issues.append(f"sha256 mismatch: {rel}")

    if required_paths is not None:
        required = tuple(required_paths)
    else:
        try:
            required = _profile_artifact_expectations(root)
        except ValueError as exc:
            return ArtifactValidation(False, checked, 0, (str(exc),))
    for rel in required:
        if rel not in paths_seen:
            issues.append(f"required artifact absent from manifest: {rel}")

    return ArtifactValidation(not issues, checked, len(required), tuple(issues))


def _profile_artifact_expectations(project_root: Path) -> tuple[str, ...]:
    """Load required generated paths from the optional domain profile."""
    profile = project_root / "domain_profile.yaml"
    if not profile.exists():
        return ()
    try:
        import yaml
    except (ImportError, OSError) as exc:
        raise ValueError(f"domain profile unreadable: {exc}") from exc
    try:
        payload = yaml.safe_load(profile.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"domain profile invalid: {exc}") from exc
    values = payload.get("artifact_expectations", []) if isinstance(payload, dict) else []
    return tuple(value for value in values if isinstance(value, str))


def _stable_artifacts(project_root: Path) -> list[Path]:
    candidates: list[Path] = []
    output = project_root / "output"
    # The integrity screen is a committed analysis aggregate, rather than a
    # disposable output.  Keep its exact JSON alongside the rendered audit figure
    # so the release manifest binds the visual claim to its source record.
    integrity_screen = project_root / "data" / "integrity_advantage.json"
    if integrity_screen.is_file() and not integrity_screen.is_symlink():
        candidates.append(integrity_screen)
    for subdir in ("data", "figures"):
        folder = output / subdir
        if folder.exists():
            candidates.extend(path for path in folder.glob("*") if path.is_file() and not path.is_symlink())
    for path in (
        output / "dashboard.html",
        output / "reports" / "verification_summary.json",
        output / "reports" / "evaluation_accounting.json",
        output / "reports" / "evaluation_events.jsonl",
        output / "reports" / "evaluation_ledger.jsonl",
        output / "reports" / "paper_audit.json",
        output / "reports" / "formalism_traceability.json",
    ):
        if path.exists():
            candidates.append(path)
    return sorted(
        {
            path
            for path in candidates
            if path.name not in _MANIFEST_EXCLUDE_NAMES and not path.name.startswith(".") and not path.is_symlink()
        },
        key=lambda p: p.relative_to(project_root).as_posix(),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _coverage_gate() -> int:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject = PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return int(data["tool"]["coverage"]["report"]["fail_under"])


__all__ = [
    "FIGURE_LABELS",
    "VerificationSummary",
    "ArtifactValidation",
    "default_verification_summary",
    "_refresh_observed_verification",
    "load_verification_summary",
    "write_artifact_manifest",
    "validate_artifact_manifest",
    "write_figure_registry",
    "write_verification_summary",
]
