"""Separate operational acceptance contracts for production readiness.

Model quality and production readiness answer different questions.  This module
records service-level observations and operational controls without importing the
LLM-judged quality certificate or allowing one to stand in for the other.
It is intentionally usable with a real service log, a local replay, or a staged
acceptance fixture; no network or model SDK is required here.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .accounting import fingerprint_json


PRODUCTION_SCHEMA_VERSION = 1
PRODUCTION_STATUSES = frozenset({"pending_evidence", "complete_not_ready", "ready", "failed"})
DEFAULT_REQUIRED_CONTROLS = (
    "privacy_controls_verified",
    "data_handling_verified",
    "rollback_verified",
    "monitoring_verified",
    "drift_detection_verified",
)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite numeric")
    return float(value)


def _nonnegative(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _items(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _json_write(path: str | Path, payload: Mapping[str, object]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target


def _certificate_digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires non-empty values")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + weight * (ordered[upper] - ordered[lower])


@dataclass(frozen=True)
class ProductionReadinessProtocol:
    """Operational acceptance scope and thresholds for one service deployment."""

    protocol_id: str
    service_name: str
    model_digest: str
    config_fingerprint: str
    expected_observations: int
    thresholds: Mapping[str, float]
    required_controls: tuple[str, ...] = DEFAULT_REQUIRED_CONTROLS

    def __post_init__(self) -> None:
        for name in ("protocol_id", "service_name", "model_digest", "config_fingerprint"):
            _text(getattr(self, name), name)
        _integer(self.expected_observations, "expected_observations")
        if self.expected_observations <= 0:
            raise ValueError("expected_observations must be positive")
        if not self.thresholds:
            raise ValueError("thresholds must be explicit")
        if not self.required_controls or len(set(self.required_controls)) != len(self.required_controls):
            raise ValueError("required_controls must be non-empty and unique")
        for control in self.required_controls:
            _text(control, "required_control")
            if control not in DEFAULT_REQUIRED_CONTROLS:
                raise ValueError(f"unsupported required control: {control}")
        for name, value in self.thresholds.items():
            _nonnegative(value, f"thresholds[{name}]")

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_version": PRODUCTION_SCHEMA_VERSION,
            "protocol_id": self.protocol_id,
            "service_name": self.service_name,
            "model_digest": self.model_digest,
            "config_fingerprint": self.config_fingerprint,
            "expected_observations": self.expected_observations,
            "thresholds": dict(self.thresholds),
            "required_controls": list(self.required_controls),
        }
        payload["protocol_sha256"] = _certificate_digest(payload)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProductionReadinessProtocol":
        if data.get("schema_version") != PRODUCTION_SCHEMA_VERSION:
            raise ValueError("unsupported production-readiness schema")
        protocol_digest = _text(data.get("protocol_sha256"), "protocol_sha256")
        unsigned = dict(data)
        unsigned.pop("protocol_sha256", None)
        if protocol_digest != _certificate_digest(unsigned):
            raise ValueError("production-readiness protocol digest mismatch")
        controls = _items(data.get("required_controls", list(DEFAULT_REQUIRED_CONTROLS)), "required_controls")
        return cls(
            protocol_id=_text(data.get("protocol_id"), "protocol_id"),
            service_name=_text(data.get("service_name"), "service_name"),
            model_digest=_text(data.get("model_digest"), "model_digest"),
            config_fingerprint=_text(data.get("config_fingerprint"), "config_fingerprint"),
            expected_observations=_integer(data.get("expected_observations"), "expected_observations"),
            thresholds={str(key): _nonnegative(value, f"thresholds[{key}]") for key, value in _mapping(data.get("thresholds", {}), "thresholds").items()},
            required_controls=tuple(_text(value, "required_control") for value in controls),
        )


@dataclass(frozen=True)
class ProductionObservation:
    """One request/response observation from an operational acceptance run."""

    observation_id: str
    protocol_id: str
    status: str
    latency_seconds: float
    cost_usd: float
    retry_count: int
    model_digest: str
    config_fingerprint: str
    privacy_violation: bool = False
    red_team_case: bool = False
    error_class: str | None = None

    def __post_init__(self) -> None:
        for name in ("observation_id", "protocol_id", "model_digest", "config_fingerprint"):
            _text(getattr(self, name), name)
        if self.status not in {"complete", "failed"}:
            raise ValueError("status must be complete or failed")
        _nonnegative(self.latency_seconds, "latency_seconds")
        _nonnegative(self.cost_usd, "cost_usd")
        _integer(self.retry_count, "retry_count")
        _boolean(self.privacy_violation, "privacy_violation")
        _boolean(self.red_team_case, "red_team_case")
        if self.status == "failed" and not self.error_class:
            raise ValueError("failed observations require error_class")
        if self.status == "complete" and self.error_class is not None:
            raise ValueError("complete observations cannot carry error_class")

    def to_dict(self) -> dict[str, object]:
        return {
            "observation_id": self.observation_id,
            "protocol_id": self.protocol_id,
            "status": self.status,
            "latency_seconds": self.latency_seconds,
            "cost_usd": self.cost_usd,
            "retry_count": self.retry_count,
            "model_digest": self.model_digest,
            "config_fingerprint": self.config_fingerprint,
            "privacy_violation": self.privacy_violation,
            "red_team_case": self.red_team_case,
            "error_class": self.error_class,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProductionObservation":
        return cls(
            observation_id=_text(data.get("observation_id"), "observation_id"),
            protocol_id=_text(data.get("protocol_id"), "protocol_id"),
            status=_text(data.get("status"), "status"),
            latency_seconds=_nonnegative(data.get("latency_seconds"), "latency_seconds"),
            cost_usd=_nonnegative(data.get("cost_usd"), "cost_usd"),
            retry_count=_integer(data.get("retry_count"), "retry_count"),
            model_digest=_text(data.get("model_digest"), "model_digest"),
            config_fingerprint=_text(data.get("config_fingerprint"), "config_fingerprint"),
            privacy_violation=_boolean(data.get("privacy_violation", False), "privacy_violation"),
            red_team_case=_boolean(data.get("red_team_case", False), "red_team_case"),
            error_class=None if data.get("error_class") is None else _text(data.get("error_class"), "error_class"),
        )


@dataclass(frozen=True)
class ProductionControls:
    """Operational evidence for controls not inferable from request logs."""

    privacy_controls_verified: bool
    data_handling_verified: bool
    rollback_verified: bool
    monitoring_verified: bool
    drift_detection_verified: bool
    red_team_cases: int

    def __post_init__(self) -> None:
        for name in (
            "privacy_controls_verified",
            "data_handling_verified",
            "rollback_verified",
            "monitoring_verified",
            "drift_detection_verified",
        ):
            _boolean(getattr(self, name), name)
        _integer(self.red_team_cases, "red_team_cases")

    def to_dict(self) -> dict[str, object]:
        return {
            "privacy_controls_verified": self.privacy_controls_verified,
            "data_handling_verified": self.data_handling_verified,
            "rollback_verified": self.rollback_verified,
            "monitoring_verified": self.monitoring_verified,
            "drift_detection_verified": self.drift_detection_verified,
            "red_team_cases": self.red_team_cases,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProductionControls":
        return cls(
            privacy_controls_verified=_boolean(data.get("privacy_controls_verified"), "privacy_controls_verified"),
            data_handling_verified=_boolean(data.get("data_handling_verified"), "data_handling_verified"),
            rollback_verified=_boolean(data.get("rollback_verified"), "rollback_verified"),
            monitoring_verified=_boolean(data.get("monitoring_verified"), "monitoring_verified"),
            drift_detection_verified=_boolean(data.get("drift_detection_verified"), "drift_detection_verified"),
            red_team_cases=_integer(data.get("red_team_cases"), "red_team_cases"),
        )


@dataclass(frozen=True)
class ProductionReadinessReport:
    """Operational acceptance result, independent of model-quality status."""

    protocol_id: str
    status: str
    n_observations: int
    metrics: Mapping[str, object]
    controls: Mapping[str, object]
    threshold_results: Mapping[str, bool]
    issues: tuple[str, ...] = ()
    provenance: Mapping[str, object] = field(default_factory=dict)
    certificate_sha256: str = ""

    def __post_init__(self) -> None:
        _text(self.protocol_id, "protocol_id")
        if self.status not in PRODUCTION_STATUSES:
            raise ValueError(f"status must be one of {sorted(PRODUCTION_STATUSES)}")
        _integer(self.n_observations, "n_observations")
        if self.certificate_sha256 and len(self.certificate_sha256) != 64:
            raise ValueError("certificate_sha256 must be a SHA-256 hex digest")
        if self.status == "ready" and (
            self.issues
            or not self.threshold_results
            or not all(self.threshold_results.values())
            or not self.provenance.get("protocol_sha256")
        ):
            raise ValueError("ready reports require all controls and thresholds to pass")
        if self.status == "failed" and not self.issues:
            raise ValueError("failed readiness reports require explicit issues")
        if self.status in {"complete_not_ready", "pending_evidence"} and self.issues:
            raise ValueError("non-failed readiness reports cannot contain unresolved issues")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": PRODUCTION_SCHEMA_VERSION,
            "protocol_id": self.protocol_id,
            "status": self.status,
            "n_observations": self.n_observations,
            "metrics": dict(self.metrics),
            "controls": dict(self.controls),
            "threshold_results": dict(self.threshold_results),
            "issues": list(self.issues),
            "provenance": dict(self.provenance),
        }
        payload["certificate_sha256"] = _certificate_digest(payload)
        return payload

    def write(self, path: str | Path) -> Path:
        return _json_write(path, self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProductionReadinessReport":
        if data.get("schema_version") != PRODUCTION_SCHEMA_VERSION:
            raise ValueError("unsupported production-readiness report schema")
        certificate = _text(data.get("certificate_sha256"), "certificate_sha256")
        unsigned = dict(data)
        unsigned.pop("certificate_sha256", None)
        if certificate != _certificate_digest(unsigned):
            raise ValueError("production-readiness certificate digest mismatch")
        return cls(
            protocol_id=_text(data.get("protocol_id"), "protocol_id"),
            status=_text(data.get("status"), "status"),
            n_observations=_integer(data.get("n_observations"), "n_observations"),
            metrics=_mapping(data.get("metrics", {}), "metrics"),
            controls=_mapping(data.get("controls", {}), "controls"),
            threshold_results={str(key): _boolean(value, f"threshold_results[{key}]") for key, value in _mapping(data.get("threshold_results", {}), "threshold_results").items()},
            issues=tuple(str(value) for value in _items(data.get("issues", []), "issues")),
            provenance=_mapping(data.get("provenance", {}), "provenance"),
            certificate_sha256=certificate,
        )


def _evaluate_threshold(name: str, threshold: float, metrics: Mapping[str, object], controls: ProductionControls) -> bool:
    if name in {"p95_latency_upper_bound", "p99_latency_upper_bound", "failure_rate_upper_bound", "retry_rate_upper_bound", "cost_per_request_upper_bound", "privacy_violation_count_upper_bound"}:
        value = metrics.get(name.removesuffix("_upper_bound"))
        return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) <= threshold
    if name == "throughput_lower_bound":
        value = metrics.get("throughput_requests_per_second")
        return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) >= threshold
    if name == "model_pin_match":
        return bool(metrics.get(name)) and threshold <= 1.0
    if name in {
        "privacy_controls_verified",
        "data_handling_verified",
        "rollback_verified",
        "monitoring_verified",
        "drift_detection_verified",
    }:
        return bool(getattr(controls, name)) and threshold <= 1.0
    if name == "red_team_cases_min":
        return controls.red_team_cases >= threshold
    return False


def build_production_readiness_report(
    protocol: ProductionReadinessProtocol,
    observations: Sequence[ProductionObservation],
    controls: ProductionControls,
    *,
    provenance: Mapping[str, object] | None = None,
) -> ProductionReadinessReport:
    """Aggregate service observations and fail closed on structural corruption."""
    issues: list[str] = []
    if len({row.observation_id for row in observations}) != len(observations):
        issues.append("duplicate_observation_ids")
    if len(observations) != protocol.expected_observations:
        issues.append(f"observation_count:{len(observations)}!={protocol.expected_observations}")
    if any(row.protocol_id != protocol.protocol_id for row in observations):
        issues.append("protocol_id_mismatch")
    if any(row.model_digest != protocol.model_digest for row in observations):
        issues.append("model_pin_mismatch")
    if any(row.config_fingerprint != protocol.config_fingerprint for row in observations):
        issues.append("config_fingerprint_mismatch")

    n = len(observations)
    complete = [row for row in observations if row.status == "complete"]
    failed = [row for row in observations if row.status == "failed"]
    latencies = [row.latency_seconds for row in observations]
    total_latency = sum(latencies)
    metrics: dict[str, object] = {
        "n_complete": len(complete),
        "n_failed": len(failed),
        "failure_rate": len(failed) / n if n else 1.0,
        "retry_rate": sum(row.retry_count > 0 for row in observations) / n if n else 1.0,
        "p95_latency": _percentile(latencies, 0.95) if latencies else None,
        "p99_latency": _percentile(latencies, 0.99) if latencies else None,
        "cost_per_request": sum(row.cost_usd for row in observations) / n if n else None,
        "throughput_requests_per_second": n / total_latency if total_latency > 0 else None,
        "privacy_violation_count": sum(row.privacy_violation for row in observations),
        "model_pin_match": not any(row.model_digest != protocol.model_digest for row in observations),
        "red_team_observations": sum(row.red_team_case for row in observations),
    }
    threshold_results: dict[str, bool] = {}
    if not issues:
        threshold_results = {
            name: _evaluate_threshold(name, threshold, metrics, controls)
            for name, threshold in protocol.thresholds.items()
        }
        for control in protocol.required_controls:
            threshold_results[f"required_control:{control}"] = bool(getattr(controls, control, False))
    if issues:
        status = "failed"
    elif not observations:
        status = "pending_evidence"
    elif threshold_results and all(threshold_results.values()):
        status = "ready"
    else:
        status = "complete_not_ready"
    report_provenance = dict(provenance or {})
    protocol_payload = protocol.to_dict()
    report_provenance.setdefault("protocol_sha256", protocol_payload["protocol_sha256"])
    return ProductionReadinessReport(
        protocol_id=protocol.protocol_id,
        status=status,
        n_observations=n,
        metrics=metrics,
        controls=controls.to_dict(),
        threshold_results=threshold_results,
        issues=tuple(issues),
        provenance=report_provenance,
    )


def load_production_readiness_report(path: str | Path) -> ProductionReadinessReport:
    return ProductionReadinessReport.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _validate_promotable_evidence(report: ProductionReadinessReport) -> None:
    """Validate the external evidence binding emitted by the live runner."""
    provenance = report.provenance
    ledger = provenance.get("request_ledger")
    if ledger is None:
        return
    if not isinstance(ledger, list) or not ledger:
        raise ValueError("production promotion request ledger is missing")
    observations_path = Path(str(provenance.get("observations_path", "")))
    controls_path = Path(str(provenance.get("controls_path", "")))
    protocol_path = Path(str(provenance.get("protocol_path", "")))
    required_files = (
        ("protocol", protocol_path, provenance.get("protocol_file_sha256")),
        ("observations", observations_path, provenance.get("observations_sha256")),
        ("controls", controls_path, provenance.get("controls_sha256")),
    )
    for name, path, expected_digest in required_files:
        if not path.is_file():
            raise ValueError(f"production promotion {name} evidence is missing")
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError(f"production promotion {name} evidence digest mismatch")
    root = observations_path.parent
    actual_entries: list[dict[str, object]] = []
    for entry in ledger:
        if not isinstance(entry, Mapping):
            raise ValueError("production promotion request ledger is invalid")
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("production promotion request ledger path is unsafe")
        target = root / relative
        if not target.is_file():
            raise ValueError(f"production promotion request evidence is missing: {relative}")
        payload = target.read_bytes()
        actual_entries.append(
            {"path": relative, "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
        )
    expected_entries = sorted(
        [dict(entry) for entry in ledger],
        key=lambda entry: str(entry.get("path", "")),
    )
    if sorted(actual_entries, key=lambda entry: str(entry["path"])) != expected_entries:
        raise ValueError("production promotion request ledger digest mismatch")
    if fingerprint_json(actual_entries) != provenance.get("request_ledger_sha256"):
        raise ValueError("production promotion request ledger fingerprint mismatch")


def promote_production_readiness(
    source_path: str | Path,
    target_path: str | Path,
    *,
    overwrite: bool = False,
    acceptance_path: str | Path | None = None,
) -> Path:
    """Promote only an operationally ready report; this is not a quality promotion."""
    report = load_production_readiness_report(source_path)
    if report.status != "ready":
        raise ValueError("only a ready production-readiness report may be promoted")
    _validate_promotable_evidence(report)
    if acceptance_path is None:
        raise ValueError("production promotion requires explicit acceptance")
    acceptance_file = Path(acceptance_path)
    if not acceptance_file.is_file():
        raise ValueError("production promotion acceptance record is missing")
    try:
        acceptance = json.loads(acceptance_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("production promotion acceptance record is unreadable") from exc
    if not isinstance(acceptance, Mapping) or acceptance.get("accepted") is not True:
        raise ValueError("production promotion requires accepted=true")
    if acceptance.get("report_certificate_sha256") != report.certificate_sha256:
        raise ValueError("production acceptance does not bind this certificate")
    if not isinstance(acceptance.get("accepted_by"), str) or not str(acceptance["accepted_by"]).strip():
        raise ValueError("production acceptance requires accepted_by")
    target = Path(target_path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing readiness report: {target}")
    return _json_write(target, report.to_dict())


__all__ = [
    "PRODUCTION_SCHEMA_VERSION",
    "ProductionReadinessProtocol",
    "ProductionObservation",
    "ProductionControls",
    "ProductionReadinessReport",
    "build_production_readiness_report",
    "load_production_readiness_report",
    "promote_production_readiness",
]
