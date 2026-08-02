"""Executable local-service probes for the production-readiness lane.

The runner deliberately stores only digests and lengths for prompts and model
responses.  It measures the configured local deployment profile, retries once
after a failed request, and turns every probe into a typed observation.  A
control probe that was not actually supplied remains false; no operational
control is inferred from model-quality results.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from ..module import LMClient
from .accounting import fingerprint_json
from .production_readiness import (
    ProductionControls,
    ProductionObservation,
    ProductionReadinessProtocol,
    ProductionReadinessReport,
    build_production_readiness_report,
)
from .quality import write_jsonl


@dataclass(frozen=True)
class ProductionWorkloadCase:
    """One synthetic request in the staged operational workload."""

    case_id: str
    prompt: str
    red_team_case: bool = False
    privacy_sentinel: str = ""

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.prompt.strip():
            raise ValueError("production workload cases require non-empty IDs and prompts")
        if self.privacy_sentinel and self.privacy_sentinel in self.prompt:
            raise ValueError("privacy_sentinel must not be embedded in the prompt")


@dataclass(frozen=True)
class ProductionRunSummary:
    """Paths and accounting for one local operational probe."""

    protocol_id: str
    output_root: str
    n_expected: int
    n_observations: int
    n_failed: int
    observations_path: str
    controls_path: str
    protocol_path: str
    report_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol_id": self.protocol_id,
            "output_root": self.output_root,
            "n_expected": self.n_expected,
            "n_observations": self.n_observations,
            "n_failed": self.n_failed,
            "observations_path": self.observations_path,
            "controls_path": self.controls_path,
            "protocol_path": self.protocol_path,
            "report_path": self.report_path,
        }


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_production_probe(
    protocol: ProductionReadinessProtocol,
    cases: Sequence[ProductionWorkloadCase],
    *,
    lm: LMClient,
    output_root: str | Path,
    control_probes: Mapping[str, Callable[[], bool]] | None = None,
    provenance_extra: Mapping[str, object] | None = None,
    max_retries: int = 1,
) -> tuple[ProductionRunSummary, ProductionReadinessReport]:
    """Run a bounded staged workload and write a report bound to its ledger."""
    if not cases:
        raise ValueError("production workload must be non-empty")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("production workload case IDs must be unique")
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative")
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    protocol_path = root / "protocol.json"
    protocol_payload = protocol.to_dict()
    _write_json(protocol_path, protocol_payload)
    observations: list[ProductionObservation] = []
    raw_entries: list[dict[str, object]] = []
    for case in cases:
        observation_id = f"{protocol.protocol_id}:{case.case_id}"
        started = time.perf_counter()
        response = ""
        error: BaseException | None = None
        retries = 0
        for attempt in range(max_retries + 1):
            try:
                response = lm.complete(case.prompt)
                if not isinstance(response, str) or not response.strip():
                    raise ValueError("service returned an empty response")
                error = None
                retries = attempt
                break
            except Exception as exc:  # operational failures become evidence rows
                error = exc
                retries = attempt
        latency = time.perf_counter() - started
        privacy_violation = bool(case.privacy_sentinel and case.privacy_sentinel in response)
        if error is None:
            observation = ProductionObservation(
                observation_id=observation_id,
                protocol_id=protocol.protocol_id,
                status="complete",
                latency_seconds=latency,
                cost_usd=0.0,
                retry_count=retries,
                model_digest=protocol.model_digest,
                config_fingerprint=protocol.config_fingerprint,
                privacy_violation=privacy_violation,
                red_team_case=case.red_team_case,
            )
        else:
            observation = ProductionObservation(
                observation_id=observation_id,
                protocol_id=protocol.protocol_id,
                status="failed",
                latency_seconds=latency,
                cost_usd=0.0,
                retry_count=retries,
                model_digest=protocol.model_digest,
                config_fingerprint=protocol.config_fingerprint,
                privacy_violation=privacy_violation,
                red_team_case=case.red_team_case,
                error_class=type(error).__name__,
            )
        observations.append(observation)
        raw_path = root / "request_ledger" / f"{case.case_id}.json"
        raw_payload = {
            "observation_id": observation_id,
            "case_id": case.case_id,
            "prompt_sha256": _digest_text(case.prompt),
            "response_sha256": _digest_text(response),
            "response_length": len(response),
            "attempts": retries + 1,
            "status": observation.status,
            "error_class": observation.error_class,
            "privacy_violation": privacy_violation,
            "red_team_case": case.red_team_case,
        }
        _write_json(raw_path, raw_payload)
        raw_entries.append(
            {
                "path": str(raw_path.relative_to(root)),
                "sha256": _digest_text(raw_path.read_text(encoding="utf-8")),
                "size_bytes": raw_path.stat().st_size,
            }
        )
    observations_path = root / "observations.jsonl"
    write_jsonl(observations_path, (observation.to_dict() for observation in observations))
    probes = dict(control_probes or {})
    raw_bytes = b"".join(
        (root / str(entry["path"])).read_bytes()
        for entry in raw_entries
        if isinstance(entry.get("path"), str)
    )
    auto_controls = {
        "privacy_controls_verified": all(
            key not in raw_bytes.decode("utf-8") for key in ("\"prompt\":", "\"response\":")
        ) and not any(observation.privacy_violation for observation in observations),
        "data_handling_verified": all(
            not Path(str(entry["path"])).is_absolute() and ".." not in Path(str(entry["path"])).parts
            for entry in raw_entries
        ),
        "monitoring_verified": observations_path.is_file() and bool(raw_entries),
        "drift_detection_verified": all(
            observation.model_digest == protocol.model_digest
            and observation.config_fingerprint == protocol.config_fingerprint
            for observation in observations
        ),
    }
    controls = ProductionControls(
        privacy_controls_verified=bool(probes.get("privacy_controls_verified", lambda: auto_controls["privacy_controls_verified"])())
        if "privacy_controls_verified" in probes
        else auto_controls["privacy_controls_verified"],
        data_handling_verified=bool(probes.get("data_handling_verified", lambda: auto_controls["data_handling_verified"])())
        if "data_handling_verified" in probes
        else auto_controls["data_handling_verified"],
        rollback_verified=bool(probes["rollback_verified"]()) if "rollback_verified" in probes else False,
        monitoring_verified=bool(probes.get("monitoring_verified", lambda: auto_controls["monitoring_verified"])())
        if "monitoring_verified" in probes
        else auto_controls["monitoring_verified"],
        drift_detection_verified=bool(probes.get("drift_detection_verified", lambda: auto_controls["drift_detection_verified"])())
        if "drift_detection_verified" in probes
        else auto_controls["drift_detection_verified"],
        red_team_cases=sum(observation.red_team_case for observation in observations),
    )
    controls_path = root / "controls.json"
    _write_json(controls_path, controls.to_dict())
    observations_sha256 = _digest_text(observations_path.read_text(encoding="utf-8"))
    controls_sha256 = _digest_text(controls_path.read_text(encoding="utf-8"))
    provenance = {
        "scope": "staged_local_single_user_profile",
        "protocol_path": str(protocol_path.resolve()),
        "protocol_sha256": str(protocol_payload["protocol_sha256"]),
        "protocol_file_sha256": _digest_text(protocol_path.read_text(encoding="utf-8")),
        "observations_path": str(observations_path.resolve()),
        "observations_sha256": observations_sha256,
        "controls_path": str(controls_path.resolve()),
        "controls_sha256": controls_sha256,
        "request_ledger": sorted(raw_entries, key=lambda entry: str(entry["path"])),
        "request_ledger_sha256": fingerprint_json(raw_entries),
        "raw_content_policy": "digests_and_lengths_only",
        "max_retries": max_retries,
    }
    if provenance_extra:
        provenance.update(dict(provenance_extra))
    report = build_production_readiness_report(protocol, observations, controls, provenance=provenance)
    report_path = root / "production_report.json"
    report.write(report_path)
    summary = ProductionRunSummary(
        protocol_id=protocol.protocol_id,
        output_root=str(root),
        n_expected=len(cases),
        n_observations=len(observations),
        n_failed=sum(observation.status == "failed" for observation in observations),
        observations_path=str(observations_path),
        controls_path=str(controls_path),
        protocol_path=str(protocol_path),
        report_path=str(report_path),
    )
    _write_json(root / "run_summary.json", summary.to_dict())
    return summary, report


__all__ = ["ProductionRunSummary", "ProductionWorkloadCase", "run_production_probe"]
