"""Bind publication consumers to the exact benchmark bytes they selected.

Receipts are consistency evidence, not signatures, scientific acceptance, or
proof of execution. External reports may be rendered, but are not portable
publication inputs until explicitly staged and both consumers regenerated.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .evaluation.backend_benchmark import validate_backend_benchmark

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ARTIFACTS = {
    "dashboard": "output/dashboard.html",
    "manuscript": "output/data/manuscript_variables.json",
}


def _project_path(root: Path, relative: str) -> Path:
    """Refuse noncanonical paths and symlinks at every project-relative level."""
    path = PurePosixPath(relative)
    if (
        not relative or "\\" in relative or ":" in relative or path.is_absolute()
        or ".." in path.parts or path.as_posix() != relative
    ):
        raise ValueError("unsafe project-relative path")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("project input must not contain a symlink")
    return current


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _read_json(raw: bytes) -> Any:
    return json.loads(raw, object_pairs_hook=_json_object, parse_constant=_invalid_constant)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _benchmark_input(report: Path | None, *, selection: str, relative: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "selection": selection,
        "portable": selection != "external",
        "path": relative,
        "sha256": None,
        "report_fingerprint": None,
        "dataset_fingerprint": None,
        "status": "not-recorded",
    }
    if report is not None:
        raw = report.read_bytes()
        payload = _read_json(raw)
        validate_backend_benchmark(payload)
        result.update(
            sha256=_digest(raw),
            report_fingerprint=payload["report_fingerprint"],
            dataset_fingerprint=payload["dataset_fingerprint"],
            status=payload["status"],
        )
    return result


def _artifact_input(root: Path, consumer: str) -> dict[str, str]:
    relative = _ARTIFACTS[consumer]
    return {"path": relative, "sha256": _digest(_project_path(root, relative).read_bytes())}


def write_benchmark_input_receipt(
    consumer: str,
    report_path: str | Path | None,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    """Write a schema-1 receipt after the consumer's final artifact write.

    Relative report selections have the same caller-working-directory semantics
    as the generator CLIs. None means no selected report, never an implicit
    default search. Invalid evidence leaves an existing receipt untouched.
    """
    if consumer not in _ARTIFACTS:
        raise ValueError("consumer must be dashboard or manuscript")
    root = Path(project_root).resolve()
    report = None
    relative = None
    selection = "not-recorded"
    if report_path is not None:
        selected = Path(report_path)
        if ".." in selected.parts:
            raise ValueError("unsafe benchmark report path")
        # absolute() preserves symlink components for the staged safety check.
        selected = selected.absolute()
        try:
            relative = selected.relative_to(root).as_posix()
        except ValueError:
            selection = "external"
            report = selected
        else:
            normalized = PurePosixPath(relative)
            if normalized.parts[:2] != ("output", "data") or len(normalized.parts) < 3:
                raise ValueError("staged benchmark report must be under output/data/")
            report = _project_path(root, relative)
            selection = "staged"
    payload = {
        "schema": 1,
        "consumer": consumer,
        "artifact": _artifact_input(root, consumer),
        "benchmark": _benchmark_input(report, selection=selection, relative=relative),
    }
    destination = _project_path(root, f"output/reports/{consumer}_benchmark_input.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def validate_publication_inputs(project_root: str | Path = PROJECT_ROOT) -> tuple[str, ...]:
    """Return deterministic refusal reasons; empty means byte-consistent inputs.

    Incomplete reports are valid diagnostic inputs and retain that status. This
    gate checks selection and byte integrity, not scientific success. Both
    not-recorded receipts may agree; mixing recorded and absent inputs may not.
    It never stages, repairs, regenerates, or re-seals an artifact or receipt.
    """
    root = Path(project_root).resolve()
    issues: list[str] = []
    selections: list[dict[str, Any]] = []
    for consumer in _ARTIFACTS:
        try:
            source = _project_path(root, f"output/reports/{consumer}_benchmark_input.json")
            receipt = _read_json(source.read_bytes())
            if (
                not isinstance(receipt, dict)
                or set(receipt) != {"schema", "consumer", "artifact", "benchmark"}
                or type(receipt["schema"]) is not int or receipt["schema"] != 1
                or receipt["consumer"] != consumer
            ):
                raise ValueError("invalid receipt schema or consumer")
            if receipt["artifact"] != _artifact_input(root, consumer):
                issues.append(f"{consumer}: artifact receipt mismatch")
            benchmark = receipt["benchmark"]
            if not isinstance(benchmark, dict) or type(benchmark.get("portable")) is not bool:
                raise ValueError("benchmark receipt must be an object with a boolean portable flag")
            selection = benchmark.get("selection")
            if selection == "external":
                issues.append(
                    f"{consumer}: external benchmark input is nonportable; "
                    "explicitly stage and regenerate both consumers"
                )
                continue
            if selection == "not-recorded":
                expected = _benchmark_input(None, selection="not-recorded", relative=None)
            elif selection == "staged":
                relative = benchmark.get("path")
                if not isinstance(relative, str):
                    raise ValueError("staged benchmark input has no relative path")
                parts = PurePosixPath(relative).parts
                if parts[:2] != ("output", "data") or len(parts) < 3:
                    raise ValueError("staged benchmark report must be under output/data/")
                report = _project_path(root, relative)
                expected = _benchmark_input(report, selection="staged", relative=relative)
            else:
                raise ValueError("invalid benchmark input selection")
            if benchmark != expected:
                issues.append(
                    f"{consumer}: benchmark receipt mismatch "
                    "(selection, raw bytes, fingerprints or status)"
                )
            selections.append(benchmark)
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            issues.append(f"{consumer}: publication input unavailable or invalid: {exc}")
    if len(selections) == 2 and selections[0] != selections[1]:
        issues.append("publication consumers selected different benchmark inputs")
    return tuple(issues)


__all__ = ["write_benchmark_input_receipt", "validate_publication_inputs"]
