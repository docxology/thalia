"""Deterministic evaluation ledgers and provenance records.

The aggregate JSON is useful for figures, but it is not sufficient to audit a
failed or partially completed run.  This module keeps one stable JSON object per
example/method and a small ordered event stream.  Runtime metadata is deliberately
separate: it can describe a machine or model without contaminating deterministic
rerun identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LEDGER_STATUSES = {"complete", "failed"}
_EVENT_NAMES = {"run_started", "sample_evaluated", "run_finished", "run_failed"}


def _strict_int(value: object) -> bool:
    """Return whether ``value`` is an integer, excluding booleans."""
    return isinstance(value, int) and not isinstance(value, bool)


def fingerprint_json(value: object) -> str:
    """Return a stable SHA-256 fingerprint for JSON-compatible data."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fingerprint_examples(examples: Iterable[object]) -> str:
    """Fingerprint the identity-bearing fields of evaluation examples."""
    rows = []
    for example in examples:
        rows.append(_example_fingerprint_payload(example, include_id=True))
    return fingerprint_json(rows)


def fingerprint_example_content(example: object) -> str:
    """Fingerprint observable example content independently of its stable ID."""
    return fingerprint_json(_example_fingerprint_payload(example, include_id=False))


def _example_fingerprint_payload(example: object, *, include_id: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_history": getattr(example, "session_history", ""),
        "query": getattr(example, "query", ""),
        "expected_answer": getattr(example, "expected_answer", ""),
        "expected_source_indices": list(getattr(example, "expected_source_indices", ()) or ()),
        "task_category": getattr(getattr(example, "task_category", None), "value", None),
        "stratum": getattr(example, "stratum", "default"),
        "seed": getattr(example, "seed", None),
        "metadata": dict(getattr(example, "metadata", ()) or ()),
    }
    if include_id:
        payload["example_id"] = getattr(example, "example_id", "")
    return payload


def fingerprint_config(config: object) -> str:
    """Fingerprint a config object using its public ``to_dict`` contract."""
    value = config.to_dict() if hasattr(config, "to_dict") else config
    return fingerprint_json(value)


def file_provenance(path: str | Path) -> dict[str, object]:
    """Return size and SHA-256 metadata for an external input file."""
    source = Path(path)
    resolved = source.resolve()
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    try:
        display_path = resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        # External files remain identifiable, while project-local provenance is
        # portable across machines and does not leak an absolute checkout path.
        display_path = str(resolved)
    return {"path": display_path, "size_bytes": resolved.stat().st_size, "sha256": digest.hexdigest()}


def fingerprint_files(paths: Iterable[str | Path]) -> str:
    """Fingerprint named source files by path and bytes, in sorted order."""
    rows = []
    for path in sorted((Path(value) for value in paths), key=lambda item: str(item)):
        rows.append({"path": str(path), "sha256": file_provenance(path)["sha256"], "size_bytes": path.stat().st_size})
    return fingerprint_json(rows)


def runtime_provenance(*, models: Mapping[str, object] | None = None, benchmark: Mapping[str, object] | None = None) -> dict[str, object]:
    """Capture intentionally non-deterministic machine/model context."""
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "models": dict(models or {}),
        "benchmark": dict(benchmark or {}),
    }


@dataclass(frozen=True)
class EvaluationLedgerRow:
    """One example/method observation, including failure accounting."""

    sequence: int
    example_id: str
    category: str
    stratum: str
    seed: int | None
    method: str
    metrics: Mapping[str, float]
    status: str
    error_class: str | None
    config_fingerprint: str
    dataset_fingerprint: str
    content_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def ledger_row(
    *,
    sequence: int,
    example: object,
    method: str,
    metrics: Mapping[str, float] | None,
    status: str,
    config_fingerprint: str,
    dataset_fingerprint: str,
    error: BaseException | None = None,
) -> dict[str, object]:
    """Construct a JSON-ready row with a stable error class, never an traceback."""
    if not _strict_int(sequence) or sequence <= 0:
        raise ValueError(f"sequence must be positive, got {sequence}")
    example_id = str(getattr(example, "example_id", ""))
    if not example_id:
        raise ValueError("example must have a stable example_id")
    if not method:
        raise ValueError("method must be non-empty")
    if status not in _LEDGER_STATUSES:
        raise ValueError(f"status must be one of {sorted(_LEDGER_STATUSES)}, got {status!r}")
    if status == "complete" and error is not None:
        raise ValueError("complete ledger rows cannot carry an error")
    if status == "failed" and error is None:
        raise ValueError("failed ledger rows must carry an error")
    category = getattr(getattr(example, "task_category", None), "value", "unknown")
    normalized_metrics: dict[str, float] = {}
    for key, value in (metrics or {}).items():
        if not isinstance(key, str) or not key:
            raise ValueError("metric names must be non-empty strings")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("ledger metrics must be finite numbers")
        normalized_metrics[key] = numeric
    row = EvaluationLedgerRow(
        sequence=sequence,
        example_id=example_id,
        category=str(category),
        stratum=str(getattr(example, "stratum", "default")),
        seed=getattr(example, "seed", None),
        method=method,
        metrics=normalized_metrics,
        status=status,
        error_class=type(error).__name__ if error else None,
        config_fingerprint=config_fingerprint,
        dataset_fingerprint=dataset_fingerprint,
        content_fingerprint=fingerprint_example_content(example),
    )
    return row.to_dict()


def validate_ledger(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Validate and materialize a complete, ordered evaluation ledger.

    ``sequence`` is global to a run, not merely local to a method or seed.  Example
    IDs may repeat across methods because that is how paired comparisons are
    represented, but every row sequence must be unique and contiguous.
    """
    materialized = [dict(row) for row in rows]
    if not materialized:
        raise ValueError("ledger must contain at least one row")
    sequences = [row.get("sequence") for row in materialized]
    if not all(_strict_int(value) for value in sequences) or sequences != list(range(1, len(materialized) + 1)):
        raise ValueError("ledger sequence values must be contiguous starting at one")
    for row in materialized:
        if not isinstance(row.get("example_id"), str) or not row["example_id"]:
            raise ValueError("ledger rows require a stable example_id")
        for field in ("category", "stratum", "method", "config_fingerprint", "dataset_fingerprint", "content_fingerprint"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError(f"ledger rows require a non-empty {field}")
        if row.get("seed") is not None and not _strict_int(row.get("seed")):
            raise ValueError("ledger row seed must be an integer or null")
        if not isinstance(row.get("method"), str) or not row["method"]:
            raise ValueError("ledger rows require a non-empty method")
        status = row.get("status")
        if status not in _LEDGER_STATUSES:
            raise ValueError(f"ledger row has invalid status: {status!r}")
        metrics = row.get("metrics")
        if not isinstance(metrics, Mapping):
            raise ValueError("ledger row metrics must be a mapping")
        if status == "complete" and not metrics:
            raise ValueError("complete ledger rows require metrics")
        if status == "failed" and not row.get("error_class"):
            raise ValueError("failed ledger rows require error_class")
        if row.get("error_class") is not None and (
            not isinstance(row.get("error_class"), str) or not row["error_class"]
        ):
            raise ValueError("ledger error_class must be a non-empty string or null")
        if status == "complete" and row.get("error_class") is not None:
            raise ValueError("complete ledger rows cannot carry error_class")
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in metrics.values()):
            raise ValueError("ledger row metrics must be finite numbers")
    return materialized


def validate_event_stream(
    events: Iterable[Mapping[str, object]],
    ledger: Iterable[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Validate event structure and, when supplied, its exact ledger projection."""
    materialized = [dict(event) for event in events]
    if not materialized:
        raise ValueError("events must contain at least one record")
    sequences = [event.get("sequence") for event in materialized]
    if not all(_strict_int(value) for value in sequences) or sequences != list(range(1, len(materialized) + 1)):
        raise ValueError("event sequence values must be contiguous starting at one")
    if any(event.get("event") not in _EVENT_NAMES for event in materialized):
        raise ValueError("events contain an unknown event name")
    first, last = materialized[0], materialized[-1]
    if first.get("event") != "run_started":
        raise ValueError("event stream must start with run_started")
    if last.get("event") not in {"run_finished", "run_failed"}:
        raise ValueError("event stream must end with run_finished or run_failed")
    run_id = first.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("event stream requires a non-empty run_id")
    if any(event.get("run_id") != run_id for event in materialized):
        raise ValueError("all events must belong to the same run_id")

    if ledger is None:
        return materialized

    rows = validate_ledger(ledger)
    if len(materialized) != len(rows) + 2:
        raise ValueError("event stream must contain one event per ledger row plus start and finish")
    if first.get("n_requested") != len(rows) or first.get("n_requested_evaluations") != len(rows):
        raise ValueError("run_started counts do not match ledger length")
    if first.get("n_unique_examples") != len({row["example_id"] for row in rows}):
        raise ValueError("run_started unique-example count does not match ledger")
    sample_events = materialized[1:-1]
    for event, row in zip(sample_events, rows):
        expected_event = "sample_evaluated" if row["status"] == "complete" else "run_failed"
        if event.get("event") != expected_event:
            raise ValueError("sample event status does not match ledger")
        for field in ("example_id", "method", "status", "error_class"):
            if event.get(field) != row.get(field):
                raise ValueError(f"sample event {field} does not match ledger")
    failures = sum(row["status"] != "complete" for row in rows)
    expected_finish = "run_finished" if failures == 0 else "run_failed"
    if last.get("event") != expected_finish:
        raise ValueError("run finish event does not match ledger failures")
    if last.get("n_evaluated") != len(rows) - failures or last.get("n_failed") != failures:
        raise ValueError("run finish counts do not match ledger")
    if last.get("n_unique_examples") != len({row["example_id"] for row in rows if row["status"] == "complete"}):
        raise ValueError("run finish unique-example count does not match ledger")
    return materialized


def deterministic_events(
    ledger: Iterable[Mapping[str, object]],
    *,
    experiment: str,
    dataset_fingerprint: str,
    config_fingerprint: str,
    run_id: str,
) -> list[dict[str, object]]:
    """Create deterministic start/sample/finish or failed events."""
    rows = validate_ledger(ledger)
    events: list[dict[str, object]] = [
        {
            "sequence": 1,
            "event": "run_started",
            "run_id": run_id,
            "experiment": experiment,
            "dataset_fingerprint": dataset_fingerprint,
            "config_fingerprint": config_fingerprint,
            "n_requested": len(rows),
            "n_requested_evaluations": len(rows),
            "n_unique_examples": len({row.get("example_id") for row in rows}),
            "methods": sorted({str(row.get("method")) for row in rows}),
        }
    ]
    for offset, row in enumerate(rows, start=2):
        events.append(
            {
                "sequence": offset,
                "event": "sample_evaluated" if row.get("status") == "complete" else "run_failed",
                "run_id": run_id,
                "example_id": row.get("example_id"),
                "method": row.get("method"),
                "status": row.get("status"),
                "error_class": row.get("error_class"),
                "dataset_fingerprint": dataset_fingerprint,
                "config_fingerprint": config_fingerprint,
            }
        )
    failures = sum(row.get("status") != "complete" for row in rows)
    events.append(
        {
            "sequence": len(events) + 1,
            "event": "run_finished" if not failures else "run_failed",
            "run_id": run_id,
            "experiment": experiment,
            "n_evaluated": len(rows) - failures,
            "n_failed": failures,
            "n_unique_examples": len({row.get("example_id") for row in rows if row.get("status") == "complete"}),
            "dataset_fingerprint": dataset_fingerprint,
            "config_fingerprint": config_fingerprint,
        }
    )
    return events


def write_jsonl(records: Iterable[Mapping[str, object]], path: str | Path) -> Path:
    """Write stable JSONL records and create the parent directory."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(dict(record), sort_keys=True) + "\n" for record in records)
    _atomic_write_text(target, payload)
    return target


def _atomic_write_text(target: Path, payload: str) -> None:
    """Replace a generated text artifact atomically within its parent directory."""
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)


def write_ledger_and_events(
    ledger: Iterable[Mapping[str, object]],
    events: Iterable[Mapping[str, object]],
    ledger_path: str | Path,
    events_path: str | Path,
) -> tuple[Path, Path]:
    """Write the per-example ledger and its deterministic event stream."""
    rows = validate_ledger(ledger)
    event_rows = validate_event_stream(events, rows)
    return write_jsonl(rows, ledger_path), write_jsonl(event_rows, events_path)


__all__ = [
    "EvaluationLedgerRow",
    "fingerprint_json",
    "fingerprint_examples",
    "fingerprint_example_content",
    "fingerprint_config",
    "file_provenance",
    "fingerprint_files",
    "runtime_provenance",
    "ledger_row",
    "validate_ledger",
    "validate_event_stream",
    "deterministic_events",
    "write_jsonl",
    "write_ledger_and_events",
]
