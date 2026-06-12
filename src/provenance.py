"""Deterministic provenance helpers for ATLAS generated outputs.

The template validator consumes project-local registries from ``output/``.  These
helpers write those registries from source code so the files are regenerable and
the manuscript/render gates do not depend on hand-edited output artifacts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output"

FIGURE_LABELS: dict[str, str] = {
    "backend_comparison": "fig:backend_comparison",
    "bottleneck": "fig:bottleneck",
    "category_breakdown": "fig:category_breakdown",
    "compiler_convergence": "fig:compiler_convergence",
    "consolidation_curve": "fig:consolidation",
    "evidence_funnel": "fig:evidence_funnel",
    "injection_resistance": "fig:injection_resistance",
    "longmemeval": "fig:longmemeval",
    "method_ablation": "fig:method_ablation",
    "mmr_tradeoff": "fig:mmr_tradeoff",
    "noise_scaling": "fig:noise_scaling",
    "orchestration_value": "fig:orchestration_value",
    "paraphrase_retrieval": "fig:paraphrase_retrieval",
    "retriever_comparison": "fig:retriever_comparison",
    "rrf_sensitivity": "fig:rrf_sensitivity",
    "scaling_ci": "fig:scaling_ci",
}

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
    """Small generated record of the live gates ATLAS expects reviewers to run."""

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


def default_verification_summary() -> VerificationSummary:
    """Return the canonical command summary for this project checkout."""
    return VerificationSummary(
        test_command=(
            "uv run --project working/atlas pytest working/atlas/tests/ "
            "--cov=working/atlas/src --cov-report=term-missing --cov-fail-under=90"
        ),
        coverage_gate=_coverage_gate(),
        render_command="uv run python scripts/03_render_pdf.py --project working/atlas",
        validation_command="uv run python scripts/04_validate_output.py --project working/atlas",
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
            "source": "src/figures.py",
        }
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_artifact_manifest(
    project_root: str | Path = PROJECT_ROOT,
    output_path: str | Path | None = None,
) -> Path:
    """Write a current, validator-compatible manifest for stable ATLAS outputs."""
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
                "stage_name": "ATLAS provenance refresh",
                "stage_num": 0,
                "timestamp": "deterministic",
            }
        )
    payload = {"entries": entries, "issues": []}
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


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
    import tomllib

    pyproject = PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return int(data["tool"]["coverage"]["report"]["fail_under"])


__all__ = [
    "FIGURE_LABELS",
    "VerificationSummary",
    "default_verification_summary",
    "load_verification_summary",
    "write_artifact_manifest",
    "write_figure_registry",
    "write_verification_summary",
]
