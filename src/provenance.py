"""Deterministic provenance helpers for THALIA generated outputs.

The template validator consumes project-local registries from ``output/``.  These
helpers write those registries from source code so the files are regenerable and
the manuscript/render gates do not depend on hand-edited output artifacts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable

from .figures.manifest import FIGURE_LABELS

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
            "uv run --project working/thalia pytest working/thalia/tests/ "
            "--cov=working/thalia/src --cov-report=term-missing --cov-fail-under=90"
        ),
        coverage_gate=_coverage_gate(),
        render_command="uv run python scripts/03_render_pdf.py --project working/thalia",
        validation_command="uv run python scripts/04_validate_output.py --project working/thalia",
    )


def write_verification_summary(
    output_path: str | Path = OUTPUT_ROOT / "reports" / "verification_summary.json",
    *,
    summary: VerificationSummary | None = None,
) -> Path:
    """Write the verification summary and return its path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (summary or default_verification_summary()).to_dict()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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
    root = Path(project_root)
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
    root = Path(project_root)
    source = Path(manifest_path) if manifest_path else root / "output" / "reports" / "artifact_manifest.json"
    issues: list[str] = []
    if not source.exists():
        return ArtifactValidation(False, 0, 0, (f"manifest missing: {source}",))
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

    required = tuple(required_paths) if required_paths is not None else _profile_artifact_expectations(root)
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

        payload = yaml.safe_load(profile.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    values = payload.get("artifact_expectations", []) if isinstance(payload, dict) else []
    return tuple(value for value in values if isinstance(value, str))


def _stable_artifacts(project_root: Path) -> list[Path]:
    candidates: list[Path] = []
    output = project_root / "output"
    for subdir in ("data", "figures"):
        folder = output / subdir
        if folder.exists():
            candidates.extend(path for path in folder.glob("*") if path.is_file())
    for path in (
        output / "dashboard.html",
        output / "reports" / "verification_summary.json",
    ):
        if path.exists():
            candidates.append(path)
    return sorted(
        {
            path
            for path in candidates
            if path.name not in _MANIFEST_EXCLUDE_NAMES and not path.name.startswith(".")
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
    try:
        import tomllib  # Python >= 3.11
    except ModuleNotFoundError:  # pragma: no cover - exercised only on 3.10
        import tomli as tomllib  # type: ignore[no-redef]

    pyproject = PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return int(data["tool"]["coverage"]["report"]["fail_under"])


__all__ = [
    "FIGURE_LABELS",
    "VerificationSummary",
    "ArtifactValidation",
    "default_verification_summary",
    "load_verification_summary",
    "write_artifact_manifest",
    "validate_artifact_manifest",
    "write_figure_registry",
    "write_verification_summary",
]
