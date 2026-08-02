"""Typed, provenance-first model-quality evaluation contracts.

The live campaign in :mod:`src.evaluation.campaign` records execution and
automated proxies.  This module deliberately uses a separate schema for the
quality lane: raw answers remain external, annotations are blinded, the pilot
is excluded from the confirmatory estimand, and only a passing quality
certificate can be promoted into committed evidence.  The schema supports an
exploratory local LLM-judge implementation, but promotion is restricted to the
independently blinded expert-human mode requested by the publication protocol.
Neither mode is an unqualified universal factuality certificate.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..compiler.metrics import EvalExample
from .accounting import file_provenance, fingerprint_json
from .statistics import (
    binary_rate,
    clustered_paired_comparison,
    exact_paired_binary,
)


QUALITY_SCHEMA_VERSION = 3
QUALITY_PROTOCOL_VERSION = "quality-v3"
QUALITY_PHASES = frozenset({"pilot", "confirmatory"})
QUALITY_STATUSES = frozenset({"pending_annotation", "complete_not_promoted", "passed", "failed"})
QUALITY_MODES = frozenset({"harness", "no_harness", "oracle_evidence"})
QUALITY_SCORE_FIELDS = ("correctness", "completeness", "faithfulness", "usefulness")
QUALITY_PRIMARY_METRICS = frozenset({"correctness_full_rate"})
QUALITY_SUPPORT_LABELS = frozenset({"supported", "unsupported", "uncertain", "not_applicable"})
QUALITY_EVALUATION_MODES = frozenset({"expert_human", "llm_judge"})
STANDARD_QUALITY_MODELS = ("gemma3:4b", "hermes3:latest")
STANDARD_QUALITY_MATRIX = frozenset(
    (model, mode) for model in STANDARD_QUALITY_MODELS for mode in QUALITY_MODES
)
DEFAULT_QUALITY_RUBRIC: dict[str, object] = {
    "ordinal_scale": {
        "0": "incorrect, absent, or unusable for the target question",
        "1": "partly correct, incomplete, weakly supported, or conditionally useful",
        "2": "fully correct, complete for the stated task, supported, or useful as applicable",
    },
    "dimensions": ["correctness", "completeness", "faithfulness", "usefulness"],
    "binary_outcomes": ["abstention_appropriate", "critical_safety_failure"],
    "atomic_claim_labels": sorted(QUALITY_SUPPORT_LABELS),
}
DEFAULT_PILOT_PER_STRATUM = 10
DEFAULT_CONFIDENCE = 0.95
DEFAULT_RESAMPLES = 2000
DEFAULT_JUDGE_IDS = ("judge-a", "judge-b")
DEFAULT_ADJUDICATOR_ID = "adjudicator"
DEFAULT_JUDGE_PROMPT_VERSION = "llm-judge-v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite numeric")
    return float(value)


def _optional_finite(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return _finite(value, field_name)


def _unit(value: object, field_name: str) -> float:
    numeric = _finite(value, field_name)
    if not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return numeric


def _score(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1, 2):
        raise ValueError(f"{field_name} must be an integer score in [0, 2]")
    return value


def _bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be boolean")
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _items(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_digest(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def _validate_rubric(value: object) -> dict[str, object]:
    """Validate the machine-readable rubric contract, not just its presence."""
    rubric = _mapping(value, "rubric")
    ordinal_scale = _mapping(rubric.get("ordinal_scale"), "rubric.ordinal_scale")
    if set(ordinal_scale) != {"0", "1", "2"}:
        raise ValueError("rubric.ordinal_scale must define exactly scores 0, 1, and 2")
    for score, definition in ordinal_scale.items():
        _text(definition, f"rubric.ordinal_scale[{score}]")
    dimensions = _items(rubric.get("dimensions"), "rubric.dimensions")
    dimension_names = {_text(item, "rubric dimension") for item in dimensions}
    if not set(QUALITY_SCORE_FIELDS).issubset(dimension_names):
        missing = sorted(set(QUALITY_SCORE_FIELDS) - dimension_names)
        raise ValueError(f"rubric.dimensions is missing: {', '.join(missing)}")
    binary_outcomes = _items(rubric.get("binary_outcomes"), "rubric.binary_outcomes")
    binary_names = {_text(item, "rubric binary outcome") for item in binary_outcomes}
    required_binary = {"abstention_appropriate", "critical_safety_failure"}
    if not required_binary.issubset(binary_names):
        missing = sorted(required_binary - binary_names)
        raise ValueError(f"rubric.binary_outcomes is missing: {', '.join(missing)}")
    claim_labels = _items(rubric.get("atomic_claim_labels"), "rubric.atomic_claim_labels")
    claim_label_names = {_text(item, "rubric atomic claim label") for item in claim_labels}
    if claim_label_names != set(QUALITY_SUPPORT_LABELS):
        raise ValueError("rubric.atomic_claim_labels must match the declared atomic claim labels")
    return dict(rubric)


def parse_confidence_response(response: str) -> float | None:
    """Parse the standardized confidence probe without inventing a score."""
    if not isinstance(response, str) or not response.strip():
        return None
    text = response.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        payload = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None
    value = payload.get("confidence") if isinstance(payload, Mapping) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0:
        return float(value)
    match = re.fullmatch(r"\s*confidence\s*[:=]\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*", response, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _protocol_digest(payload: Mapping[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("protocol_sha256", None)
    return _sha256_text(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _json_write(path: str | Path, payload: Mapping[str, object]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target


def _pilot_review_structural_issue(value: object) -> str | None:
    """Validate the shape of the pilot certificate binding without I/O."""
    if not isinstance(value, Mapping) or not value:
        return "pilot review provenance is missing"
    report = value.get("report")
    if not isinstance(report, Mapping):
        return "pilot review provenance requires report metadata"
    path = report.get("path")
    if not isinstance(path, str) or not path.strip():
        return "pilot review provenance requires report.path"
    size_bytes = report.get("size_bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        return "pilot review provenance requires a non-negative report.size_bytes"
    try:
        _sha256_digest(report.get("sha256"), "pilot review report.sha256")
        _sha256_digest(report.get("certificate_sha256"), "pilot review report.certificate_sha256")
        _sha256_digest(value.get("protocol_sha256"), "pilot review protocol_sha256")
    except ValueError as exc:
        return str(exc)
    if value.get("status") not in {"complete_not_promoted", "passed"}:
        return "pilot review provenance status must describe a complete pilot report"
    return None


@dataclass(frozen=True)
class QualityCondition:
    """One model/architecture condition in the quality matrix."""

    condition_id: str
    model: str
    mode: str
    policy: str = "default"
    config_overrides: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _text(self.condition_id, "condition_id")
        _text(self.model, "model")
        if self.mode not in QUALITY_MODES:
            raise ValueError(f"mode must be one of {sorted(QUALITY_MODES)}")
        _text(self.policy, "policy")
        keys = [key for key, _ in self.config_overrides]
        if len(keys) != len(set(keys)):
            raise ValueError("config_overrides must not contain duplicate keys")

    def to_dict(self) -> dict[str, object]:
        return {
            "condition_id": self.condition_id,
            "model": self.model,
            "mode": self.mode,
            "policy": self.policy,
            "config_overrides": dict(self.config_overrides),
        }


def default_quality_conditions(models: Sequence[str] = ("gemma3:4b", "hermes3:latest")) -> tuple[QualityCondition, ...]:
    """Return the preregistered six-condition model/baseline matrix."""
    if not models or len(set(models)) != len(models):
        raise ValueError("models must be non-empty and unique")
    conditions: list[QualityCondition] = []
    for model in models:
        slug = model.replace(":", "-").replace("/", "-")
        conditions.extend(
            (
                QualityCondition(f"{slug}-harness-default", model, "harness"),
                QualityCondition(f"{slug}-no-harness", model, "no_harness", policy="full_context"),
                QualityCondition(f"{slug}-oracle-evidence", model, "oracle_evidence", policy="gold_session"),
            )
        )
    return tuple(conditions)


@dataclass(frozen=True)
class QualityProtocol:
    """Frozen evaluation scope and construct contract."""

    protocol_id: str
    benchmark_provenance: Mapping[str, object]
    pilot_ids: tuple[str, ...]
    confirmatory_ids: tuple[str, ...]
    conditions: tuple[QualityCondition, ...]
    generation_options: Mapping[str, object]
    rubric_version: str = "draft-v1"
    rubric: Mapping[str, object] = field(default_factory=lambda: dict(DEFAULT_QUALITY_RUBRIC))
    primary_metric: str = "correctness_full_rate"
    thresholds: Mapping[str, float] = field(default_factory=dict)
    confidence: float = DEFAULT_CONFIDENCE
    pilot_review_provenance: Mapping[str, object] = field(default_factory=dict)
    matrix_policy: str = "custom"
    atomic_claims_required: bool = True
    judge_ids: tuple[str, ...] = DEFAULT_JUDGE_IDS
    adjudicator_id: str = "adjudicator"
    blind_packet_version: str = "blind-v3"
    evaluation_mode: str = "expert_human"
    judge_models: tuple[tuple[str, str, str], ...] = ()
    adjudicator_model: tuple[str, str] | tuple[()] = ()
    judge_prompt_version: str = DEFAULT_JUDGE_PROMPT_VERSION

    def __post_init__(self) -> None:
        _text(self.protocol_id, "protocol_id")
        if not isinstance(self.benchmark_provenance, Mapping):
            raise ValueError("benchmark_provenance must be a mapping")
        _text(self.benchmark_provenance.get("path"), "benchmark_provenance.path")
        _sha256_digest(self.benchmark_provenance.get("sha256"), "benchmark_provenance.sha256")
        size_bytes = self.benchmark_provenance.get("size_bytes")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
            raise ValueError("benchmark_provenance.size_bytes must be a non-negative integer")
        if not self.pilot_ids or len(set(self.pilot_ids)) != len(self.pilot_ids):
            raise ValueError("pilot_ids must be non-empty and unique")
        if any(not isinstance(value, str) or not value.strip() for value in (*self.pilot_ids, *self.confirmatory_ids)):
            raise ValueError("question IDs must be non-empty text")
        if not self.confirmatory_ids or len(set(self.confirmatory_ids)) != len(self.confirmatory_ids):
            raise ValueError("confirmatory_ids must be non-empty and unique")
        if set(self.pilot_ids) & set(self.confirmatory_ids):
            raise ValueError("pilot_ids and confirmatory_ids must be disjoint")
        if not self.conditions or len({condition.condition_id for condition in self.conditions}) != len(self.conditions):
            raise ValueError("conditions must be non-empty and uniquely identified")
        if not self.generation_options:
            raise ValueError("generation_options must be non-empty")
        _text(self.rubric_version, "rubric_version")
        _validate_rubric(self.rubric)
        if self.primary_metric not in QUALITY_PRIMARY_METRICS:
            raise ValueError(f"primary_metric must be one of {sorted(QUALITY_PRIMARY_METRICS)}")
        if not 0.0 < self.confidence < 1.0:
            raise ValueError("confidence must be in (0, 1)")
        if not isinstance(self.pilot_review_provenance, Mapping):
            raise ValueError("pilot_review_provenance must be a mapping")
        if self.matrix_policy not in {"standard-six", "custom"}:
            raise ValueError("matrix_policy must be standard-six or custom")
        if not isinstance(self.atomic_claims_required, bool):
            raise ValueError("atomic_claims_required must be boolean")
        if len(self.judge_ids) != 2 or len(set(self.judge_ids)) != 2 or any(not isinstance(value, str) or not value.strip() for value in self.judge_ids):
            raise ValueError("judge_ids must contain exactly two distinct non-empty IDs")
        _text(self.adjudicator_id, "adjudicator_id")
        if self.adjudicator_id in set(self.judge_ids):
            raise ValueError("adjudicator_id must be distinct from judge_ids")
        _text(self.blind_packet_version, "blind_packet_version")
        if self.evaluation_mode not in QUALITY_EVALUATION_MODES:
            raise ValueError(f"evaluation_mode must be one of {sorted(QUALITY_EVALUATION_MODES)}")
        _text(self.judge_prompt_version, "judge_prompt_version")
        judge_model_ids = set()
        for spec in self.judge_models:
            if len(spec) != 3:
                raise ValueError("judge_models entries must contain judge_id, model, and digest")
            judge_id, model, digest = spec
            _text(judge_id, "judge_id")
            _text(model, "judge_model")
            _sha256_digest(digest, "judge_model_digest")
            if judge_id in judge_model_ids:
                raise ValueError("judge_models must contain unique judge IDs")
            judge_model_ids.add(judge_id)
        if self.judge_models and judge_model_ids != set(self.judge_ids):
            raise ValueError("judge_models must bind exactly the two declared judge IDs")
        if self.adjudicator_model:
            if len(self.adjudicator_model) != 2:
                raise ValueError("adjudicator_model must contain model and digest")
            _text(self.adjudicator_model[0], "adjudicator_model")
            _sha256_digest(self.adjudicator_model[1], "adjudicator_model_digest")
        if self.evaluation_mode == "expert_human" and (self.judge_models or self.adjudicator_model):
            raise ValueError("expert_human protocols cannot bind evaluator model digests")
        if self.matrix_policy == "standard-six":
            observed = frozenset((condition.model, condition.mode) for condition in self.conditions)
            if observed != STANDARD_QUALITY_MATRIX or len(self.conditions) != 6:
                raise ValueError("standard-six quality matrix requires Gemma and Hermes under all three conditions")
        for name, value in self.thresholds.items():
            _unit(value, f"thresholds[{name}]")

    @classmethod
    def from_examples(
        cls,
        *,
        protocol_id: str,
        benchmark_path: str | Path,
        examples: Sequence[EvalExample],
        conditions: Sequence[QualityCondition] | None = None,
        pilot_per_stratum: int = DEFAULT_PILOT_PER_STRATUM,
        selection_salt: str = "thalia-quality-pilot-v1",
        generation_options: Mapping[str, object] | None = None,
    ) -> "QualityProtocol":
        """Build a deterministic disjoint pilot/confirmatory partition."""
        if pilot_per_stratum <= 0:
            raise ValueError("pilot_per_stratum must be positive")
        if not examples or any(not example.example_id for example in examples):
            raise ValueError("examples must be non-empty and identified")
        if len({example.example_id for example in examples}) != len(examples):
            raise ValueError("example IDs must be unique")
        grouped: dict[str, list[EvalExample]] = {}
        for example in examples:
            grouped.setdefault(example.stratum, []).append(example)
        pilot: list[EvalExample] = []
        for stratum, rows in sorted(grouped.items()):
            if len(rows) < pilot_per_stratum:
                raise ValueError(f"stratum {stratum!r} has fewer than {pilot_per_stratum} examples")
            ordered = sorted(rows, key=lambda row: (_stable_id(selection_salt, stratum, row.example_id), row.example_id))
            pilot.extend(ordered[:pilot_per_stratum])
        pilot_ids = tuple(sorted(example.example_id for example in pilot))
        confirmatory_ids = tuple(sorted(example.example_id for example in examples if example.example_id not in set(pilot_ids)))
        if not confirmatory_ids:
            raise ValueError("confirmatory partition must be non-empty")
        benchmark = file_provenance(benchmark_path)
        actual_conditions = tuple(conditions) if conditions is not None else default_quality_conditions()
        matrix_policy = (
            "standard-six"
            if len(actual_conditions) == 6
            and frozenset((condition.model, condition.mode) for condition in actual_conditions) == STANDARD_QUALITY_MATRIX
            else "custom"
        )
        return cls(
            protocol_id=protocol_id,
            benchmark_provenance=benchmark,
            pilot_ids=pilot_ids,
            confirmatory_ids=confirmatory_ids,
            conditions=actual_conditions,
            generation_options=dict(generation_options or {"temperature": 0.0, "num_predict": 512}),
            matrix_policy=matrix_policy,
        )

    @property
    def frozen(self) -> bool:
        return (
            self.rubric_version != "draft-v1"
            and bool(self.thresholds)
            and _pilot_review_structural_issue(self.pilot_review_provenance) is None
            and self.atomic_claims_required
        )

    @property
    def protocol_sha256(self) -> str:
        return _protocol_digest(self.to_dict())

    def freeze(
        self,
        *,
        rubric_version: str,
        primary_metric: str,
        thresholds: Mapping[str, float],
        pilot_review_provenance: Mapping[str, object],
        rubric: Mapping[str, object] | None = None,
    ) -> "QualityProtocol":
        """Return a preregistered copy after pilot rubric review."""
        if not thresholds:
            raise ValueError("frozen quality protocol requires thresholds")
        required_thresholds = {
            "correctness_lower_bound",
            "critical_safety_failure_rate_upper_bound",
        }
        missing_thresholds = sorted(required_thresholds - set(thresholds))
        if missing_thresholds:
            raise ValueError(f"frozen quality protocol requires thresholds: {', '.join(missing_thresholds)}")
        pilot_review_issue = _pilot_review_structural_issue(pilot_review_provenance)
        if pilot_review_issue is not None:
            raise ValueError(f"frozen quality protocol requires pilot review provenance: {pilot_review_issue}")
        final_rubric = self.rubric if rubric is None else rubric
        _validate_rubric(final_rubric)
        return QualityProtocol(
            protocol_id=self.protocol_id,
            benchmark_provenance=dict(self.benchmark_provenance),
            pilot_ids=self.pilot_ids,
            confirmatory_ids=self.confirmatory_ids,
            conditions=self.conditions,
            generation_options=dict(self.generation_options),
            rubric_version=rubric_version,
            rubric=dict(final_rubric),
            primary_metric=primary_metric,
            thresholds=dict(thresholds),
            confidence=self.confidence,
            pilot_review_provenance=dict(pilot_review_provenance),
            matrix_policy=self.matrix_policy,
            atomic_claims_required=True,
            judge_ids=self.judge_ids,
            adjudicator_id=self.adjudicator_id,
            blind_packet_version=self.blind_packet_version,
            evaluation_mode=self.evaluation_mode,
            judge_models=self.judge_models,
            adjudicator_model=self.adjudicator_model,
            judge_prompt_version=self.judge_prompt_version,
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": QUALITY_SCHEMA_VERSION,
            "protocol_version": QUALITY_PROTOCOL_VERSION,
            "protocol_id": self.protocol_id,
            "benchmark_provenance": dict(self.benchmark_provenance),
            "pilot_ids": list(self.pilot_ids),
            "confirmatory_ids": list(self.confirmatory_ids),
            "conditions": [condition.to_dict() for condition in self.conditions],
            "generation_options": dict(self.generation_options),
            "rubric_version": self.rubric_version,
            "rubric": dict(self.rubric),
            "primary_metric": self.primary_metric,
            "thresholds": dict(self.thresholds),
            "confidence": self.confidence,
            "pilot_review_provenance": dict(self.pilot_review_provenance),
            "matrix_policy": self.matrix_policy,
            "atomic_claims_required": self.atomic_claims_required,
            "judge_ids": list(self.judge_ids),
            "adjudicator_id": self.adjudicator_id,
            "blind_packet_version": self.blind_packet_version,
            "evaluation_mode": self.evaluation_mode,
            "judge_models": [
                {"judge_id": judge_id, "model": model, "digest": digest}
                for judge_id, model, digest in self.judge_models
            ],
            "adjudicator_model": (
                {"model": self.adjudicator_model[0], "digest": self.adjudicator_model[1]}
                if self.adjudicator_model
                else {}
            ),
            "judge_prompt_version": self.judge_prompt_version,
        }
        payload["protocol_sha256"] = _protocol_digest(payload)
        return payload

    def write(self, path: str | Path) -> Path:
        return _json_write(path, self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityProtocol":
        if data.get("schema_version") != QUALITY_SCHEMA_VERSION:
            raise ValueError("unsupported quality protocol schema")
        if data.get("protocol_version", QUALITY_PROTOCOL_VERSION) != QUALITY_PROTOCOL_VERSION:
            raise ValueError("unsupported quality protocol version")
        raw_conditions = data.get("conditions")
        if not isinstance(raw_conditions, list):
            raise ValueError("quality protocol conditions must be a list")
        conditions = tuple(
            QualityCondition(
                condition_id=_text(row.get("condition_id"), "condition_id"),
                model=_text(row.get("model"), "model"),
                mode=_text(row.get("mode"), "mode"),
                policy=_text(row.get("policy", "default"), "policy"),
                config_overrides=tuple(sorted(_mapping(row.get("config_overrides", {}), "config_overrides").items())),
            )
            for row in raw_conditions
            if isinstance(row, Mapping)
        )
        if len(conditions) != len(raw_conditions):
            raise ValueError("quality protocol conditions must contain mappings")
        supplied_digest = _sha256_digest(data.get("protocol_sha256"), "protocol_sha256")
        if supplied_digest != _protocol_digest(data):
            raise ValueError("quality protocol digest mismatch")
        raw_judge_models = _items(data.get("judge_models", []), "judge_models")
        judge_models = tuple(
            (
                _text(row.get("judge_id"), "judge_id"),
                _text(row.get("model"), "judge_model"),
                _sha256_digest(row.get("digest"), "judge_model_digest"),
            )
            for row in raw_judge_models
            if isinstance(row, Mapping)
        )
        if len(judge_models) != len(raw_judge_models):
            raise ValueError("judge_models must contain mappings")
        raw_adjudicator_model = _mapping(data.get("adjudicator_model", {}), "adjudicator_model")
        adjudicator_model: tuple[str, str] | tuple[()] = (
            (_text(raw_adjudicator_model.get("model"), "adjudicator_model"), _sha256_digest(raw_adjudicator_model.get("digest"), "adjudicator_model_digest"))
            if raw_adjudicator_model
            else ()
        )
        judge_ids_value = data.get("judge_ids", list(DEFAULT_JUDGE_IDS))
        return cls(
            protocol_id=_text(data.get("protocol_id"), "protocol_id"),
            benchmark_provenance=_mapping(data.get("benchmark_provenance", {}), "benchmark_provenance"),
            pilot_ids=tuple(_text(value, "pilot_id") for value in _items(data.get("pilot_ids", []), "pilot_ids")),
            confirmatory_ids=tuple(_text(value, "confirmatory_id") for value in _items(data.get("confirmatory_ids", []), "confirmatory_ids")),
            conditions=conditions,
            generation_options=_mapping(data.get("generation_options", {}), "generation_options"),
            rubric_version=_text(data.get("rubric_version", "draft-v1"), "rubric_version"),
            rubric=dict(_mapping(data.get("rubric", DEFAULT_QUALITY_RUBRIC), "rubric")),
            primary_metric=_text(data.get("primary_metric", "correctness_full_rate"), "primary_metric"),
            thresholds={str(key): _unit(value, f"thresholds[{key}]") for key, value in _mapping(data.get("thresholds", {}), "thresholds").items()},
            confidence=_finite(data.get("confidence", DEFAULT_CONFIDENCE), "confidence"),
            pilot_review_provenance=_mapping(data.get("pilot_review_provenance", {}), "pilot_review_provenance"),
            matrix_policy=_text(data.get("matrix_policy", "custom"), "matrix_policy"),
            atomic_claims_required=_bool(data.get("atomic_claims_required", True), "atomic_claims_required"),
            judge_ids=tuple(_text(value, "judge_id") for value in _items(judge_ids_value, "judge_ids")),
            adjudicator_id=_text(data.get("adjudicator_id", "adjudicator"), "adjudicator_id"),
            blind_packet_version=_text(data.get("blind_packet_version", "blind-v3"), "blind_packet_version"),
            evaluation_mode=_text(data.get("evaluation_mode", "expert_human"), "evaluation_mode"),
            judge_models=judge_models,
            adjudicator_model=adjudicator_model,
            judge_prompt_version=_text(data.get("judge_prompt_version", DEFAULT_JUDGE_PROMPT_VERSION), "judge_prompt_version"),
        )

@dataclass(frozen=True)
class QualityClaim:
    """One deterministic atomic claim extracted from an answer packet."""

    claim_id: str
    claim_text: str
    evidence_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _text(self.claim_id, "claim_id")
        _text(self.claim_text, "claim_text")
        if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in self.evidence_indices):
            raise ValueError("claim evidence_indices must be non-negative integers")

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "evidence_indices": list(self.evidence_indices),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityClaim":
        return cls(
            claim_id=_text(data.get("claim_id"), "claim_id"),
            claim_text=_text(data.get("claim_text"), "claim_text"),
            evidence_indices=tuple(_integer(value, "claim evidence index") for value in _items(data.get("evidence_indices", []), "claim evidence_indices")),
        )


@dataclass(frozen=True)
class QualityClaimAnnotation:
    """Blinded judge label for one atomic claim."""

    presentation_id: str
    judge_id: str
    claim_id: str
    label: str

    def __post_init__(self) -> None:
        _text(self.presentation_id, "presentation_id")
        _text(self.judge_id, "judge_id")
        _text(self.claim_id, "claim_id")
        if self.label not in QUALITY_SUPPORT_LABELS:
            raise ValueError(f"claim label must be one of {sorted(QUALITY_SUPPORT_LABELS)}")

    def to_dict(self) -> dict[str, object]:
        return {
            "presentation_id": self.presentation_id,
            "judge_id": self.judge_id,
            "claim_id": self.claim_id,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityClaimAnnotation":
        return cls(
            presentation_id=_text(data.get("presentation_id"), "presentation_id"),
            judge_id=_text(data.get("judge_id"), "judge_id"),
            claim_id=_text(data.get("claim_id"), "claim_id"),
            label=_text(data.get("label"), "claim label"),
        )


@dataclass(frozen=True)
class QualityClaimAdjudication:
    """Resolved support label for one atomic claim."""

    presentation_id: str
    claim_id: str
    resolved_by: str
    label: str

    def __post_init__(self) -> None:
        _text(self.presentation_id, "presentation_id")
        _text(self.claim_id, "claim_id")
        _text(self.resolved_by, "resolved_by")
        if self.label not in QUALITY_SUPPORT_LABELS:
            raise ValueError(f"claim label must be one of {sorted(QUALITY_SUPPORT_LABELS)}")

    def to_dict(self) -> dict[str, object]:
        return {
            "presentation_id": self.presentation_id,
            "claim_id": self.claim_id,
            "resolved_by": self.resolved_by,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityClaimAdjudication":
        return cls(
            presentation_id=_text(data.get("presentation_id"), "presentation_id"),
            claim_id=_text(data.get("claim_id"), "claim_id"),
            resolved_by=_text(data.get("resolved_by"), "resolved_by"),
            label=_text(data.get("label"), "claim label"),
        )


@dataclass(frozen=True)
class QualityObservation:
    """One raw model observation; answer text is kept in external raw files."""

    observation_id: str
    protocol_id: str
    phase: str
    condition_id: str
    question_id: str
    model: str
    mode: str
    status: str
    stratum: str = "default"
    answer: str = ""
    citation_indices: tuple[int, ...] = ()
    citations: tuple[tuple[int, str], ...] = ()
    evidence_indices: tuple[int, ...] = ()
    claims: tuple[QualityClaim, ...] = ()
    confidence: float | None = None
    confidence_response: str = ""
    latency_seconds: float | None = None
    answer_sha256: str | None = None
    model_digest: str = ""
    config_fingerprint: str = ""
    code_fingerprint: str = ""
    generation_options: tuple[tuple[str, Any], ...] = ()
    raw_path: str = ""
    raw_sha256: str | None = None
    error_class: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("observation_id", "protocol_id", "condition_id", "question_id", "model", "mode", "stratum"):
            _text(getattr(self, field_name), field_name)
        if self.phase not in QUALITY_PHASES:
            raise ValueError(f"phase must be one of {sorted(QUALITY_PHASES)}")
        if self.mode not in QUALITY_MODES:
            raise ValueError(f"mode must be one of {sorted(QUALITY_MODES)}")
        if self.status not in {"complete", "failed"}:
            raise ValueError("quality observation status must be complete or failed")
        if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in self.citation_indices):
            raise ValueError("citation_indices must be non-negative integers")
        if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in self.evidence_indices):
            raise ValueError("evidence_indices must be non-negative integers")
        if any(
            isinstance(index, bool) or not isinstance(index, int) or index < 0 or not isinstance(excerpt, str) or not excerpt.strip()
            for index, excerpt in self.citations
        ):
            raise ValueError("citations must contain non-negative source indices and non-empty excerpts")
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claims must contain unique claim IDs")
        if self.confidence is not None:
            _unit(self.confidence, "confidence")
        if self.latency_seconds is not None and _finite(self.latency_seconds, "latency_seconds") < 0:
            raise ValueError("latency_seconds must be non-negative")
        _text(self.raw_path, "raw_path")
        raw_path = Path(self.raw_path)
        if raw_path.is_absolute() or ".." in raw_path.parts:
            raise ValueError("raw_path must be a relative path without parent traversal")
        _text(self.model_digest, "model_digest")
        _text(self.config_fingerprint, "config_fingerprint")
        _text(self.code_fingerprint, "code_fingerprint")
        if self.answer_sha256 is not None:
            _sha256_digest(self.answer_sha256, "answer_sha256")
        if self.raw_sha256 is not None:
            _sha256_digest(self.raw_sha256, "raw_sha256")
        if not self.generation_options:
            raise ValueError("observations require generation_options")
        if tuple(self.citation_indices) != tuple(index for index, _ in self.citations):
            raise ValueError("citation_indices must match citation source indices")
        if self.status == "complete":
            _text(self.confidence_response, "confidence_response")
            if self.confidence is None:
                raise ValueError("complete observations require confidence")
            parsed_confidence = parse_confidence_response(self.confidence_response)
            if parsed_confidence is None or not math.isclose(parsed_confidence, self.confidence, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("confidence_response must parse to confidence")
            if self.latency_seconds is None:
                raise ValueError("complete observations require latency_seconds")
            expected_hash = _sha256_text(self.answer)
            if self.answer_sha256 != expected_hash:
                raise ValueError("answer_sha256 does not match answer")
            if self.error_class is not None or self.error_message is not None:
                raise ValueError("complete observations cannot carry errors")
        elif not self.error_class:
            raise ValueError("failed observations require error_class")

    @property
    def presentation_id(self) -> str:
        """Stable blinded key that hides model and condition from judges."""
        return _stable_id(self.protocol_id, self.phase, self.question_id, self.condition_id)[:24]

    def to_dict(self, *, include_answer: bool = True, include_raw_digest: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "observation_id": self.observation_id,
            "protocol_id": self.protocol_id,
            "phase": self.phase,
            "condition_id": self.condition_id,
            "question_id": self.question_id,
            "model": self.model,
            "mode": self.mode,
            "status": self.status,
            "stratum": self.stratum,
            "citation_indices": list(self.citation_indices),
            "citations": [{"source_index": index, "excerpt": excerpt} for index, excerpt in self.citations],
            "evidence_indices": list(self.evidence_indices),
            "claims": [claim.to_dict() for claim in self.claims],
            "confidence": self.confidence,
            "confidence_response": self.confidence_response,
            "latency_seconds": self.latency_seconds,
            "answer_sha256": self.answer_sha256,
            "model_digest": self.model_digest,
            "config_fingerprint": self.config_fingerprint,
            "code_fingerprint": self.code_fingerprint,
            "generation_options": dict(self.generation_options),
            "raw_path": self.raw_path,
            "presentation_id": self.presentation_id,
            "error_class": self.error_class,
            "error_message": self.error_message,
        }
        if include_raw_digest:
            payload["raw_sha256"] = self.raw_sha256
        if include_answer:
            payload["answer"] = self.answer
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityObservation":
        raw_citations = _items(data.get("citations", []), "citations")
        citations = tuple(
            (_integer(row.get("source_index"), "citation source_index"), _text(row.get("excerpt"), "citation excerpt"))
            for row in raw_citations
            if isinstance(row, Mapping)
        )
        if len(citations) != len(raw_citations):
            raise ValueError("citations must contain mappings")
        answer_value = data.get("answer", "")
        if not isinstance(answer_value, str):
            raise ValueError("answer must be text")
        confidence_response = data.get("confidence_response", "")
        if not isinstance(confidence_response, str):
            raise ValueError("confidence_response must be text")
        raw_claims = _items(data.get("claims", []), "claims")
        claims = tuple(QualityClaim.from_dict(row) for row in raw_claims if isinstance(row, Mapping))
        if len(claims) != len(raw_claims):
            raise ValueError("claims must contain mappings")
        return cls(
            observation_id=_text(data.get("observation_id"), "observation_id"),
            protocol_id=_text(data.get("protocol_id"), "protocol_id"),
            phase=_text(data.get("phase"), "phase"),
            condition_id=_text(data.get("condition_id"), "condition_id"),
            question_id=_text(data.get("question_id"), "question_id"),
            model=_text(data.get("model"), "model"),
            mode=_text(data.get("mode"), "mode"),
            status=_text(data.get("status"), "status"),
            stratum=_text(data.get("stratum", "default"), "stratum"),
            answer=answer_value,
            citation_indices=tuple(_integer(value, "citation index") for value in _items(data.get("citation_indices", []), "citation_indices")),
            citations=citations,
            evidence_indices=tuple(_integer(value, "evidence index") for value in _items(data.get("evidence_indices", []), "evidence_indices")),
            claims=claims,
            confidence=None if data.get("confidence") is None else _unit(data["confidence"], "confidence"),
            confidence_response=confidence_response,
            latency_seconds=None if data.get("latency_seconds") is None else _finite(data["latency_seconds"], "latency_seconds"),
            answer_sha256=None if data.get("answer_sha256") is None else _text(data.get("answer_sha256"), "answer_sha256"),
            model_digest=_text(data.get("model_digest"), "model_digest"),
            config_fingerprint=_text(data.get("config_fingerprint"), "config_fingerprint"),
            code_fingerprint=_text(data.get("code_fingerprint"), "code_fingerprint"),
            generation_options=tuple(sorted(_mapping(data.get("generation_options", {}), "generation_options").items())),
            raw_path=_text(data.get("raw_path"), "raw_path"),
            raw_sha256=None if data.get("raw_sha256") is None else _text(data.get("raw_sha256"), "raw_sha256"),
            error_class=None if data.get("error_class") is None else _text(data.get("error_class"), "error_class"),
            error_message=None if data.get("error_message") is None else _text(data.get("error_message"), "error_message"),
        )


@dataclass(frozen=True)
class QualityAnnotation:
    """Blinded evaluator annotation for one presentation."""

    presentation_id: str
    judge_id: str
    rubric_version: str
    correctness: int
    completeness: int
    faithfulness: int
    usefulness: int
    abstention_appropriate: bool
    critical_safety_failure: bool
    notes: str = ""
    failure_modes: tuple[str, ...] = ()
    claim_labels: tuple[QualityClaimAnnotation, ...] = ()
    evaluator_confidence: float | None = None
    evaluator_model_digest: str = ""
    prompt_sha256: str = ""
    raw_path: str = ""
    raw_sha256: str = ""

    def __post_init__(self) -> None:
        _text(self.presentation_id, "presentation_id")
        _text(self.judge_id, "judge_id")
        _text(self.rubric_version, "rubric_version")
        for field_name in QUALITY_SCORE_FIELDS:
            _score(getattr(self, field_name), field_name)
        _bool(self.abstention_appropriate, "abstention_appropriate")
        _bool(self.critical_safety_failure, "critical_safety_failure")
        if len(self.failure_modes) != len(set(self.failure_modes)):
            raise ValueError("failure_modes must be unique")
        for failure_mode in self.failure_modes:
            _text(failure_mode, "failure_mode")
        claim_ids = [label.claim_id for label in self.claim_labels]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_labels must contain each claim at most once")
        for label in self.claim_labels:
            if label.presentation_id != self.presentation_id or label.judge_id != self.judge_id:
                raise ValueError("claim label identity must match its annotation")
        if self.evaluator_confidence is not None:
            _unit(self.evaluator_confidence, "evaluator_confidence")
        if self.evaluator_model_digest:
            _sha256_digest(self.evaluator_model_digest, "evaluator_model_digest")
        if self.prompt_sha256:
            _sha256_digest(self.prompt_sha256, "prompt_sha256")
        if self.raw_path:
            relative = Path(self.raw_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("raw_path must be relative and cannot traverse parents")
        if self.raw_sha256:
            _sha256_digest(self.raw_sha256, "raw_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "presentation_id": self.presentation_id,
            "judge_id": self.judge_id,
            "rubric_version": self.rubric_version,
            "correctness": self.correctness,
            "completeness": self.completeness,
            "faithfulness": self.faithfulness,
            "usefulness": self.usefulness,
            "abstention_appropriate": self.abstention_appropriate,
            "critical_safety_failure": self.critical_safety_failure,
            "notes": self.notes,
            "failure_modes": list(self.failure_modes),
            "claim_labels": [label.to_dict() for label in self.claim_labels],
            "evaluator_confidence": self.evaluator_confidence,
            "evaluator_model_digest": self.evaluator_model_digest,
            "prompt_sha256": self.prompt_sha256,
            "raw_path": self.raw_path,
            "raw_sha256": self.raw_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityAnnotation":
        raw_claims = _items(data.get("claim_labels", []), "claim_labels")
        claim_labels = tuple(QualityClaimAnnotation.from_dict(row) for row in raw_claims if isinstance(row, Mapping))
        if len(claim_labels) != len(raw_claims):
            raise ValueError("claim_labels must contain mappings")
        return cls(
            presentation_id=_text(data.get("presentation_id"), "presentation_id"),
            judge_id=_text(data.get("judge_id"), "judge_id"),
            rubric_version=_text(data.get("rubric_version"), "rubric_version"),
            correctness=_score(data.get("correctness"), "correctness"),
            completeness=_score(data.get("completeness"), "completeness"),
            faithfulness=_score(data.get("faithfulness"), "faithfulness"),
            usefulness=_score(data.get("usefulness"), "usefulness"),
            abstention_appropriate=_bool(data.get("abstention_appropriate"), "abstention_appropriate"),
            critical_safety_failure=_bool(data.get("critical_safety_failure"), "critical_safety_failure"),
            notes=str(data.get("notes", "")),
            failure_modes=tuple(_text(value, "failure_mode") for value in _items(data.get("failure_modes", []), "failure_modes")),
            claim_labels=claim_labels,
            evaluator_confidence=None if data.get("evaluator_confidence") is None else _unit(data["evaluator_confidence"], "evaluator_confidence"),
            evaluator_model_digest=str(data.get("evaluator_model_digest", "")),
            prompt_sha256=str(data.get("prompt_sha256", "")),
            raw_path=str(data.get("raw_path", "")),
            raw_sha256=str(data.get("raw_sha256", "")),
        )


@dataclass(frozen=True)
class QualityAdjudication:
    """Final resolved label after independent evaluator annotation."""

    presentation_id: str
    rubric_version: str
    resolved_by: str
    correctness: int
    completeness: int
    faithfulness: int
    usefulness: int
    abstention_appropriate: bool
    critical_safety_failure: bool
    resolution_note: str = ""
    claim_adjudications: tuple[QualityClaimAdjudication, ...] = ()
    adjudicator_model_digest: str = ""
    prompt_sha256: str = ""
    raw_path: str = ""
    raw_sha256: str = ""

    def __post_init__(self) -> None:
        _text(self.presentation_id, "presentation_id")
        _text(self.rubric_version, "rubric_version")
        _text(self.resolved_by, "resolved_by")
        for field_name in QUALITY_SCORE_FIELDS:
            _score(getattr(self, field_name), field_name)
        _bool(self.abstention_appropriate, "abstention_appropriate")
        _bool(self.critical_safety_failure, "critical_safety_failure")
        claim_ids = [label.claim_id for label in self.claim_adjudications]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_adjudications must contain each claim at most once")
        for label in self.claim_adjudications:
            if label.presentation_id != self.presentation_id or label.resolved_by != self.resolved_by:
                raise ValueError("claim adjudication identity must match its adjudication")
        if self.adjudicator_model_digest:
            _sha256_digest(self.adjudicator_model_digest, "adjudicator_model_digest")
        if self.prompt_sha256:
            _sha256_digest(self.prompt_sha256, "prompt_sha256")
        if self.raw_path:
            relative = Path(self.raw_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("raw_path must be relative and cannot traverse parents")
        if self.raw_sha256:
            _sha256_digest(self.raw_sha256, "raw_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "presentation_id": self.presentation_id,
            "rubric_version": self.rubric_version,
            "resolved_by": self.resolved_by,
            "correctness": self.correctness,
            "completeness": self.completeness,
            "faithfulness": self.faithfulness,
            "usefulness": self.usefulness,
            "abstention_appropriate": self.abstention_appropriate,
            "critical_safety_failure": self.critical_safety_failure,
            "resolution_note": self.resolution_note,
            "claim_adjudications": [label.to_dict() for label in self.claim_adjudications],
            "adjudicator_model_digest": self.adjudicator_model_digest,
            "prompt_sha256": self.prompt_sha256,
            "raw_path": self.raw_path,
            "raw_sha256": self.raw_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityAdjudication":
        raw_claims = _items(data.get("claim_adjudications", []), "claim_adjudications")
        claim_adjudications = tuple(QualityClaimAdjudication.from_dict(row) for row in raw_claims if isinstance(row, Mapping))
        if len(claim_adjudications) != len(raw_claims):
            raise ValueError("claim_adjudications must contain mappings")
        return cls(
            presentation_id=_text(data.get("presentation_id"), "presentation_id"),
            rubric_version=_text(data.get("rubric_version"), "rubric_version"),
            resolved_by=_text(data.get("resolved_by"), "resolved_by"),
            correctness=_score(data.get("correctness"), "correctness"),
            completeness=_score(data.get("completeness"), "completeness"),
            faithfulness=_score(data.get("faithfulness"), "faithfulness"),
            usefulness=_score(data.get("usefulness"), "usefulness"),
            abstention_appropriate=_bool(data.get("abstention_appropriate"), "abstention_appropriate"),
            critical_safety_failure=_bool(data.get("critical_safety_failure"), "critical_safety_failure"),
            resolution_note=str(data.get("resolution_note", "")),
            claim_adjudications=claim_adjudications,
            adjudicator_model_digest=str(data.get("adjudicator_model_digest", "")),
            prompt_sha256=str(data.get("prompt_sha256", "")),
            raw_path=str(data.get("raw_path", "")),
            raw_sha256=str(data.get("raw_sha256", "")),
        )


@dataclass(frozen=True)
class QualityReport:
    """Aggregate quality report and explicit promotion certificate."""

    protocol_id: str
    phase: str
    status: str
    benchmark_provenance: Mapping[str, object]
    n_observations: int
    n_annotations: int
    n_adjudications: int
    metrics: Mapping[str, object]
    agreement: Mapping[str, object]
    comparisons: Mapping[str, object]
    threshold_results: Mapping[str, bool]
    evidence_manifest: Mapping[str, object] = field(default_factory=dict)
    issues: tuple[str, ...] = ()
    provenance: Mapping[str, object] = field(default_factory=dict)
    certificate_sha256: str = ""

    def __post_init__(self) -> None:
        _text(self.protocol_id, "protocol_id")
        if self.phase not in QUALITY_PHASES:
            raise ValueError(f"phase must be one of {sorted(QUALITY_PHASES)}")
        if self.status not in QUALITY_STATUSES:
            raise ValueError(f"status must be one of {sorted(QUALITY_STATUSES)}")
        if self.certificate_sha256 and len(self.certificate_sha256) != 64:
            raise ValueError("certificate_sha256 must be a SHA-256 hex digest")
        if not isinstance(self.benchmark_provenance, Mapping):
            raise ValueError("benchmark_provenance must be a mapping")
        _sha256_digest(self.benchmark_provenance.get("sha256"), "benchmark_provenance.sha256")
        if not isinstance(self.evidence_manifest, Mapping):
            raise ValueError("evidence_manifest must be a mapping")
        for name in ("n_observations", "n_annotations", "n_adjudications"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.status == "passed" and (
            not self.threshold_results
            or not all(self.threshold_results.values())
            or self.issues
            or not self.evidence_manifest
        ):
            raise ValueError("passed quality reports require all thresholds true and no issues")
        if self.status == "passed" and self.phase != "confirmatory":
            raise ValueError("only confirmatory quality reports may be passed")
        if self.status == "failed" and not self.issues:
            raise ValueError("failed quality reports require explicit issues")
        if self.status == "complete_not_promoted" and self.issues:
            raise ValueError("complete_not_promoted quality reports cannot contain unresolved issues")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": QUALITY_SCHEMA_VERSION,
            "protocol_id": self.protocol_id,
            "phase": self.phase,
            "status": self.status,
            "benchmark_provenance": dict(self.benchmark_provenance),
            "n_observations": self.n_observations,
            "n_annotations": self.n_annotations,
            "n_adjudications": self.n_adjudications,
            "metrics": dict(self.metrics),
            "agreement": dict(self.agreement),
            "comparisons": dict(self.comparisons),
            "threshold_results": dict(self.threshold_results),
            "evidence_manifest": dict(self.evidence_manifest),
            "issues": list(self.issues),
            "provenance": dict(self.provenance),
        }
        payload["certificate_sha256"] = _sha256_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        )
        return payload

    def write(self, path: str | Path) -> Path:
        return _json_write(path, self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "QualityReport":
        if data.get("schema_version") != QUALITY_SCHEMA_VERSION:
            raise ValueError("unsupported quality report schema")
        certificate = _text(data.get("certificate_sha256"), "certificate_sha256")
        unsigned = dict(data)
        unsigned.pop("certificate_sha256", None)
        expected_certificate = _sha256_text(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        )
        if certificate != expected_certificate:
            raise ValueError("quality report certificate digest mismatch")
        return cls(
            protocol_id=_text(data.get("protocol_id"), "protocol_id"),
            phase=_text(data.get("phase"), "phase"),
            status=_text(data.get("status"), "status"),
            benchmark_provenance=_mapping(data.get("benchmark_provenance", {}), "benchmark_provenance"),
            n_observations=_integer(data.get("n_observations", 0), "n_observations"),
            n_annotations=_integer(data.get("n_annotations", 0), "n_annotations"),
            n_adjudications=_integer(data.get("n_adjudications", 0), "n_adjudications"),
            metrics=_mapping(data.get("metrics", {}), "metrics"),
            agreement=_mapping(data.get("agreement", {}), "agreement"),
            comparisons=_mapping(data.get("comparisons", {}), "comparisons"),
            threshold_results={str(key): _bool(value, f"threshold_results[{key}]") for key, value in _mapping(data.get("threshold_results", {}), "threshold_results").items()},
            evidence_manifest=_mapping(data.get("evidence_manifest", {}), "evidence_manifest"),
            issues=tuple(str(value) for value in _items(data.get("issues", []), "issues")),
            provenance=_mapping(data.get("provenance", {}), "provenance"),
            certificate_sha256=certificate,
        )


def weighted_cohen_kappa(left: Sequence[int], right: Sequence[int], *, maximum: int = 2) -> float:
    """Quadratically weighted Cohen's kappa for ordinal 0..``maximum`` labels."""
    if not left or len(left) != len(right):
        raise ValueError("left and right must be non-empty and equal length")
    if maximum <= 0:
        raise ValueError("maximum must be positive")
    if any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum for value in (*left, *right)):
        raise ValueError("labels must be integer values in the declared range")
    n = len(left)
    observed = sum(1.0 - ((a - b) / maximum) ** 2 for a, b in zip(left, right)) / n
    left_counts = [left.count(value) / n for value in range(maximum + 1)]
    right_counts = [right.count(value) / n for value in range(maximum + 1)]
    expected = sum(
        left_counts[a] * right_counts[b] * (1.0 - ((a - b) / maximum) ** 2)
        for a in range(maximum + 1)
        for b in range(maximum + 1)
    )
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1.0 - expected)


def brier_score(confidences: Iterable[float], outcomes: Iterable[bool | int]) -> float:
    """Mean squared probability error for binary correctness outcomes."""
    probabilities = [_unit(value, "confidence") for value in confidences]
    labels = [bool(value) if isinstance(value, bool) else value for value in outcomes]
    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("confidences and outcomes must be non-empty and equal length")
    if any(not isinstance(value, bool) and value not in (0, 1) for value in labels):
        raise ValueError("outcomes must be binary")
    return sum((probability - int(label)) ** 2 for probability, label in zip(probabilities, labels)) / len(labels)


def expected_calibration_error(
    confidences: Iterable[float],
    outcomes: Iterable[bool | int],
    *,
    bins: int = 10,
) -> float:
    """Return equal-width expected calibration error."""
    probabilities = [_unit(value, "confidence") for value in confidences]
    labels = [bool(value) if isinstance(value, bool) else value for value in outcomes]
    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("confidences and outcomes must be non-empty and equal length")
    if bins <= 0:
        raise ValueError("bins must be positive")
    if any(not isinstance(value, bool) and value not in (0, 1) for value in labels):
        raise ValueError("outcomes must be binary")
    error = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        members = [i for i, probability in enumerate(probabilities) if low <= probability < high or (index == bins - 1 and probability == 1.0)]
        if members:
            confidence_mean = sum(probabilities[i] for i in members) / len(members)
            accuracy_mean = sum(int(labels[i]) for i in members) / len(members)
            error += len(members) / len(probabilities) * abs(confidence_mean - accuracy_mean)
    return error


def reliability_curve(
    confidences: Iterable[float],
    outcomes: Iterable[bool | int],
    *,
    bins: int = 10,
) -> tuple[dict[str, object], ...]:
    """Return equal-width reliability bins without dropping empty bins."""
    probabilities = [_unit(value, "confidence") for value in confidences]
    labels = [bool(value) if isinstance(value, bool) else value for value in outcomes]
    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("confidences and outcomes must be non-empty and equal length")
    if bins <= 0:
        raise ValueError("bins must be positive")
    if any(not isinstance(value, bool) and value not in (0, 1) for value in labels):
        raise ValueError("outcomes must be binary")
    curve: list[dict[str, object]] = []
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        members = [
            i
            for i, probability in enumerate(probabilities)
            if low <= probability < high or (index == bins - 1 and probability == 1.0)
        ]
        curve.append(
            {
                "bin": index,
                "lower": low,
                "upper": high,
                "n": len(members),
                "mean_confidence": None if not members else sum(probabilities[i] for i in members) / len(members),
                "accuracy": None if not members else sum(int(labels[i]) for i in members) / len(members),
            }
        )
    return tuple(curve)


def selective_accuracy(
    confidences: Iterable[float],
    outcomes: Iterable[bool | int],
    *,
    coverage_levels: Sequence[float] = (0.25, 0.5, 0.75, 1.0),
) -> tuple[dict[str, object], ...]:
    """Measure accuracy after retaining the highest-confidence answers."""
    probabilities = [_unit(value, "confidence") for value in confidences]
    labels = [bool(value) if isinstance(value, bool) else value for value in outcomes]
    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("confidences and outcomes must be non-empty and equal length")
    if any(not isinstance(value, bool) and value not in (0, 1) for value in labels):
        raise ValueError("outcomes must be binary")
    levels = tuple(float(level) for level in coverage_levels)
    if not levels or any(not math.isfinite(level) or not 0.0 < level <= 1.0 for level in levels):
        raise ValueError("coverage_levels must be non-empty values in (0, 1]")
    if len(levels) != len(set(levels)):
        raise ValueError("coverage_levels must be unique")
    ranked = sorted(range(len(probabilities)), key=lambda index: (-probabilities[index], index))
    results: list[dict[str, object]] = []
    for level in levels:
        n_selected = max(1, math.ceil(len(ranked) * level))
        selected = ranked[:n_selected]
        results.append(
            {
                "target_coverage": level,
                "realized_coverage": n_selected / len(ranked),
                "n_selected": n_selected,
                "accuracy": sum(int(labels[index]) for index in selected) / n_selected,
                "mean_confidence": sum(probabilities[index] for index in selected) / n_selected,
            }
        )
    return tuple(results)


def quality_code_fingerprint(project_root: str | Path) -> str:
    """Fingerprint all executable package code used by a live report.

    The quality runner crosses the harness, retrieval, LM, configuration, and
    optional runtime seams.  Fingerprinting the complete ``src`` Python tree
    makes a resumed external run fail closed after any executable-source drift.
    """
    root = Path(project_root)
    paths = sorted((root / "src").rglob("*.py"))
    return fingerprint_json(
        [
            {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in paths
            if path.is_file()
        ]
    )


def load_jsonl(path: str | Path, factory):
    """Load newline-delimited JSON through a typed factory."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(factory(json.loads(line)))
    return tuple(rows)


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, object]]) -> Path:
    """Write newline-delimited JSON atomically enough for external raw evidence."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text("".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    os.replace(temporary, target)
    return target


def _metric_mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("metric values must be non-empty")
    return sum(values) / len(values)


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires non-empty values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _validate_benchmark_file(provenance: Mapping[str, object]) -> str | None:
    """Return a structural issue for a missing or changed benchmark input."""
    path_value = provenance.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        return "benchmark_path_missing"
    path = Path(path_value)
    if not path.is_file() and not path.is_absolute():
        project_candidate = Path(__file__).resolve().parents[2] / path
        if project_candidate.is_file():
            path = project_candidate
    if not path.is_file():
        return "benchmark_file_missing"
    try:
        actual = file_provenance(path)
    except (OSError, ValueError) as exc:
        return f"benchmark_file_unreadable:{type(exc).__name__}"
    if actual.get("sha256") != provenance.get("sha256") or actual.get("size_bytes") != provenance.get("size_bytes"):
        return "benchmark_provenance_mismatch"
    return None


def _validate_external_provenance_paths(provenance: Mapping[str, object]) -> list[str]:
    issues: list[str] = []
    for name in ("protocol_path", "observations_path", "annotations_path", "adjudications_path"):
        value = provenance.get(name)
        if value is None:
            continue
        if not isinstance(value, str) or _resolve_existing_path(value) is None:
            issues.append(f"{name}_missing")
    return issues


def _resolve_existing_path(value: str) -> Path | None:
    """Resolve project-relative provenance paths without trusting the caller's cwd."""
    candidate = Path(value)
    if candidate.is_file():
        return candidate
    if candidate.is_absolute():
        return None
    project_candidate = Path(__file__).resolve().parents[2] / candidate
    return project_candidate if project_candidate.is_file() else None


def _validate_pilot_review_binding(protocol: QualityProtocol) -> str | None:
    """Confirm that a frozen protocol still points to its exact pilot certificate."""
    structural_issue = _pilot_review_structural_issue(protocol.pilot_review_provenance)
    if structural_issue is not None:
        return structural_issue
    review = protocol.pilot_review_provenance
    assert isinstance(review, Mapping)
    report_metadata = review["report"]
    assert isinstance(report_metadata, Mapping)
    report_path_value = report_metadata["path"]
    assert isinstance(report_path_value, str)
    report_path = _resolve_existing_path(report_path_value)
    if report_path is None:
        return "pilot review report is missing"
    try:
        actual = file_provenance(report_path)
    except (OSError, ValueError) as exc:
        return f"pilot review report is unreadable:{type(exc).__name__}"
    if actual.get("sha256") != report_metadata.get("sha256") or actual.get("size_bytes") != report_metadata.get("size_bytes"):
        return "pilot review report digest mismatch"
    try:
        report = load_quality_report(report_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return f"pilot review certificate is unreadable:{type(exc).__name__}"
    if report.certificate_sha256 != report_metadata.get("certificate_sha256"):
        return "pilot review certificate digest mismatch"
    if report.protocol_id != protocol.protocol_id or report.phase != "pilot":
        return "pilot review certificate scope mismatch"
    if report.status not in {"complete_not_promoted", "passed"}:
        return "pilot review certificate is incomplete or failed"
    if report.issues:
        return "pilot review certificate contains unresolved issues"
    manifest = report.evidence_manifest
    if manifest.get("protocol_sha256") != review.get("protocol_sha256"):
        return "pilot review source protocol digest mismatch"
    if manifest.get("benchmark_sha256") != protocol.benchmark_provenance.get("sha256"):
        return "pilot review benchmark scope mismatch"
    question_ids = manifest.get("question_ids")
    if not isinstance(question_ids, list) or set(question_ids) != set(protocol.pilot_ids):
        return "pilot review question scope mismatch"
    condition_ids = manifest.get("condition_ids")
    if not isinstance(condition_ids, list) or condition_ids != sorted(condition.condition_id for condition in protocol.conditions):
        return "pilot review condition scope mismatch"
    if manifest.get("generation_options") != dict(protocol.generation_options):
        return "pilot review generation scope mismatch"
    expected_observations = len(protocol.pilot_ids) * len(protocol.conditions)
    if report.n_observations != expected_observations:
        return "pilot review observation count mismatch"
    if report.n_annotations != expected_observations * len(protocol.judge_ids):
        return "pilot review annotation count mismatch"
    if report.n_adjudications != expected_observations:
        return "pilot review adjudication count mismatch"
    if not manifest.get("raw_files"):
        return "pilot review raw evidence manifest is missing"
    return None


def _source_rows_fingerprint(rows: Sequence[Any]) -> str:
    """Fingerprint typed source rows independent of JSONL ordering."""
    payload = [row.to_dict() for row in rows]
    return fingerprint_json(sorted(payload, key=lambda item: json.dumps(item, sort_keys=True)))


def _source_file_manifest(
    provenance: Mapping[str, object],
    protocol: QualityProtocol,
    observations: Sequence[QualityObservation],
    annotations: Sequence[QualityAnnotation],
    adjudications: Sequence[QualityAdjudication],
    issues: list[str],
) -> dict[str, dict[str, object]]:
    """Bind optional on-disk protocol/ledger paths to the rows being analyzed."""
    manifest: dict[str, dict[str, object]] = {}
    factories = {
        "observations_path": QualityObservation.from_dict,
        "annotations_path": QualityAnnotation.from_dict,
        "adjudications_path": QualityAdjudication.from_dict,
    }
    expected_rows: dict[str, Sequence[Any]] = {
        "observations_path": observations,
        "annotations_path": annotations,
        "adjudications_path": adjudications,
    }
    protocol_path_value = provenance.get("protocol_path")
    if isinstance(protocol_path_value, str) and protocol_path_value.strip():
        path = _resolve_existing_path(protocol_path_value)
        if path is not None:
            try:
                raw = path.read_bytes()
                loaded = QualityProtocol.from_dict(json.loads(raw.decode("utf-8")))
                if loaded.protocol_sha256 != protocol.protocol_sha256:
                    issues.append("protocol_source_binding_mismatch")
                manifest["protocol"] = {
                    "path": str(path.resolve()),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                    "protocol_sha256": loaded.protocol_sha256,
                }
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                issues.append(f"protocol_source_unreadable:{type(exc).__name__}")
    for name, factory in factories.items():
        value = provenance.get(name)
        if not isinstance(value, str) or not value.strip():
            continue
        path = _resolve_existing_path(value)
        if path is None:
            issues.append(f"{name}_missing")
            continue
        try:
            raw = path.read_bytes()
            loaded = load_jsonl(path, factory)
            actual_fingerprint = _source_rows_fingerprint(loaded)
            expected_fingerprint = _source_rows_fingerprint(expected_rows[name])
            if actual_fingerprint != expected_fingerprint:
                issues.append(f"{name}_binding_mismatch")
            manifest[name.removesuffix("_path")] = {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "semantic_fingerprint": actual_fingerprint,
            }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            issues.append(f"{name}_unreadable:{type(exc).__name__}")
    return manifest


def _raw_evidence_manifest(
    rows: Sequence[QualityObservation],
    *,
    evidence_root: str | Path | None,
    issues: list[str],
) -> tuple[dict[str, object], ...]:
    if evidence_root is None:
        issues.append("raw_evidence_root_missing")
        return ()
    root = Path(evidence_root)
    if not root.is_dir():
        issues.append("raw_evidence_root_missing")
        return ()
    entries: list[dict[str, object]] = []
    for row in rows:
        target = root / row.raw_path
        try:
            target.relative_to(root)
        except ValueError:
            issues.append(f"raw_path_outside_root:{row.observation_id}")
            continue
        if not target.is_file():
            issues.append(f"raw_evidence_missing:{row.observation_id}")
            continue
        try:
            raw_bytes = target.read_bytes()
            raw_digest = hashlib.sha256(raw_bytes).hexdigest()
            payload = json.loads(raw_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            issues.append(f"raw_evidence_unreadable:{row.observation_id}")
            continue
        if row.raw_sha256 != raw_digest:
            issues.append(f"raw_digest_mismatch:{row.observation_id}")
        if not isinstance(payload, Mapping):
            issues.append(f"raw_payload_invalid:{row.observation_id}")
            continue
        raw_observation = payload.get("observation")
        if not isinstance(raw_observation, Mapping):
            issues.append(f"raw_observation_missing:{row.observation_id}")
        else:
            for field_name in ("observation_id", "protocol_id", "phase", "condition_id", "question_id", "answer_sha256"):
                if raw_observation.get(field_name) != getattr(row, field_name):
                    issues.append(f"raw_field_mismatch:{row.observation_id}:{field_name}")
            if raw_observation.get("answer") != row.answer:
                issues.append(f"raw_answer_mismatch:{row.observation_id}")
        if payload.get("question_id") != row.question_id:
            issues.append(f"raw_question_mismatch:{row.observation_id}")
        entries.append(
            {
                "observation_id": row.observation_id,
                "raw_path": row.raw_path,
                "sha256": raw_digest,
                "size_bytes": len(raw_bytes),
            }
        )
    return tuple(sorted(entries, key=lambda entry: str(entry["observation_id"])))


def build_quality_report(
    protocol: QualityProtocol,
    observations: Sequence[QualityObservation],
    annotations: Sequence[QualityAnnotation],
    adjudications: Sequence[QualityAdjudication],
    *,
    phase: str,
    provenance: Mapping[str, object] | None = None,
    evidence_root: str | Path | None = None,
) -> QualityReport:
    """Aggregate complete labels and fail closed when evidence is incomplete."""
    if phase not in QUALITY_PHASES:
        raise ValueError(f"phase must be one of {sorted(QUALITY_PHASES)}")
    expected_ids = set(protocol.pilot_ids if phase == "pilot" else protocol.confirmatory_ids)
    condition_by_id = {condition.condition_id: condition for condition in protocol.conditions}
    condition_ids = set(condition_by_id)
    expected_keys = {(question_id, condition_id) for question_id in expected_ids for condition_id in condition_ids}
    phase_rows = [row for row in observations if row.phase == phase]
    relevant = [row for row in phase_rows if row.question_id in expected_ids]
    issues: list[str] = []
    benchmark_issue = _validate_benchmark_file(protocol.benchmark_provenance)
    if benchmark_issue:
        issues.append(benchmark_issue)
    source_files = _source_file_manifest(
        provenance or {},
        protocol,
        observations,
        annotations,
        adjudications,
        issues,
    )
    issues.extend(_validate_external_provenance_paths(provenance or {}))
    if phase == "confirmatory":
        pilot_review_issue = _validate_pilot_review_binding(protocol)
        if pilot_review_issue is not None:
            issues.append(f"pilot_review_binding:{pilot_review_issue}")
        if any(row.question_id in set(protocol.pilot_ids) for row in observations):
            issues.append("pilot_leakage")
    if len(phase_rows) != len(relevant):
        issues.append("unexpected_observation_scope")
    if len({row.observation_id for row in relevant}) != len(relevant):
        issues.append("duplicate_observation_ids")
    expected_observations = len(expected_ids) * len(condition_ids)
    if len(relevant) != expected_observations:
        issues.append(f"observation_count:{len(relevant)}!={expected_observations}")
    actual_keys = [(row.question_id, row.condition_id) for row in relevant]
    if len(set(actual_keys)) != len(actual_keys):
        issues.append("duplicate_question_condition_pairs")
    if set(actual_keys) != expected_keys:
        issues.append("observation_scope_mismatch")
    if len({row.raw_path for row in relevant}) != len(relevant):
        issues.append("duplicate_raw_paths")
    model_digests: dict[str, set[str]] = {}
    code_digests: set[str] = set()
    for row in relevant:
        if row.protocol_id != protocol.protocol_id:
            issues.append("protocol_id_mismatch")
            break
        condition = condition_by_id.get(row.condition_id)
        if condition is None or row.model != condition.model or row.mode != condition.mode:
            issues.append("condition_provenance_mismatch")
            break
        if row.generation_options != tuple(sorted(protocol.generation_options.items())):
            issues.append("generation_options_mismatch")
            break
        model_digests.setdefault(row.model, set()).add(row.model_digest)
        code_digests.add(row.code_fingerprint)
    for model, digests in sorted(model_digests.items()):
        if len(digests) > 1:
            issues.append(f"model_digest_mismatch:{model}")
    if len(code_digests) > 1:
        issues.append("code_fingerprint_mismatch")
    for condition_id in sorted(condition_ids):
        condition_rows = [row for row in relevant if row.condition_id == condition_id]
        for field_name in ("model_digest", "config_fingerprint", "code_fingerprint"):
            if len({getattr(row, field_name) for row in condition_rows}) > 1:
                issues.append(f"condition_{field_name}_mismatch:{condition_id}")
    if any(row.status != "complete" for row in relevant):
        issues.append("failed_observations_present")
    for row in relevant:
        if row.status == "complete":
            if row.confidence is None:
                issues.append(f"missing_confidence:{row.observation_id}")
            if parse_confidence_response(row.confidence_response) is None:
                issues.append(f"invalid_confidence_response:{row.observation_id}")
            if row.latency_seconds is None:
                issues.append(f"missing_latency:{row.observation_id}")
            if row.raw_sha256 is None:
                issues.append(f"missing_raw_digest:{row.observation_id}")
            if protocol.atomic_claims_required and not row.claims:
                issues.append(f"missing_atomic_claims:{row.observation_id}")
    raw_entries = _raw_evidence_manifest(relevant, evidence_root=evidence_root, issues=issues)
    harness_by_model = [condition for condition in protocol.conditions if condition.mode == "harness"]
    harness_model_names = [condition.model for condition in harness_by_model]
    if len(harness_model_names) != len(set(harness_model_names)):
        issues.append("duplicate_default_harness_conditions")
    if not harness_by_model:
        issues.append("missing_default_harness_condition")
    if any(
        condition.mode != "harness" and condition.model not in set(harness_model_names)
        for condition in protocol.conditions
    ):
        issues.append("unpaired_baseline_condition")
    if protocol.matrix_policy == "standard-six":
        observed_matrix = frozenset((condition.model, condition.mode) for condition in protocol.conditions)
        if len(protocol.conditions) != 6 or observed_matrix != STANDARD_QUALITY_MATRIX:
            issues.append("standard_quality_matrix_mismatch")
    by_presentation = {row.presentation_id: row for row in relevant}
    expected_presentations = set(by_presentation)
    unknown_annotations = [annotation for annotation in annotations if annotation.presentation_id not in expected_presentations]
    if unknown_annotations:
        issues.append(f"unknown_annotation_present:{len(unknown_annotations)}")
    relevant_annotations = [annotation for annotation in annotations if annotation.presentation_id in by_presentation]
    if protocol.evaluation_mode == "expert_human":
        if any(annotation.evaluator_model_digest or annotation.prompt_sha256 for annotation in relevant_annotations):
            issues.append("expert_human_annotation_has_model_provenance")
    annotation_groups: dict[str, list[QualityAnnotation]] = {}
    for annotation in relevant_annotations:
        annotation_groups.setdefault(annotation.presentation_id, []).append(annotation)
        if annotation.rubric_version != protocol.rubric_version:
            issues.append("annotation_rubric_mismatch")
    if protocol.judge_models:
        if any(
            not annotation.raw_path
            or not annotation.raw_sha256
            or not annotation.evaluator_model_digest
            or not annotation.prompt_sha256
            for annotation in relevant_annotations
        ):
            issues.append("missing_judge_annotation_provenance")
    annotation_pairs = [(annotation.presentation_id, annotation.judge_id) for annotation in relevant_annotations]
    if len(set(annotation_pairs)) != len(annotation_pairs):
        issues.append("duplicate_judge_labels")
    duplicate_judge_groups = [
        presentation for presentation, group in annotation_groups.items() if len({annotation.judge_id for annotation in group}) != len(group)
    ]
    if duplicate_judge_groups:
        issues.append(f"duplicate_judge_labels:{len(duplicate_judge_groups)}")
    for presentation, group in annotation_groups.items():
        observed_judges = {annotation.judge_id for annotation in group}
        if observed_judges != set(protocol.judge_ids):
            issues.append(f"judge_identity_mismatch:{presentation}")
        for annotation in group:
            if protocol.atomic_claims_required:
                expected_claims = {claim.claim_id for claim in by_presentation[presentation].claims}
                observed_claims = {label.claim_id for label in annotation.claim_labels}
                if observed_claims != expected_claims:
                    issues.append(f"atomic_annotation_scope_mismatch:{presentation}:{annotation.judge_id}")
    duplicate_adjudications = len({row.presentation_id for row in adjudications}) != len(adjudications)
    if duplicate_adjudications:
        issues.append("duplicate_adjudications")
    unknown_adjudications = [row for row in adjudications if row.presentation_id not in expected_presentations]
    if unknown_adjudications:
        issues.append(f"unknown_adjudication_present:{len(unknown_adjudications)}")
    relevant_adjudications = [row for row in adjudications if row.presentation_id in by_presentation]
    for adjudication in relevant_adjudications:
        if protocol.evaluation_mode == "expert_human" and (
            adjudication.adjudicator_model_digest or adjudication.prompt_sha256
        ):
            issues.append("expert_human_adjudication_has_model_provenance")
        if adjudication.rubric_version != protocol.rubric_version:
            issues.append("adjudication_rubric_mismatch")
        if protocol.adjudicator_model and (
            not adjudication.raw_path
            or not adjudication.raw_sha256
            or not adjudication.adjudicator_model_digest
            or not adjudication.prompt_sha256
        ):
            issues.append("missing_adjudication_provenance")
        if adjudication.resolved_by != protocol.adjudicator_id or adjudication.resolved_by in set(protocol.judge_ids):
            issues.append(f"adjudicator_identity_mismatch:{adjudication.presentation_id}")
        if protocol.atomic_claims_required:
            expected_claims = {claim.claim_id for claim in by_presentation[adjudication.presentation_id].claims}
            observed_claims = {label.claim_id for label in adjudication.claim_adjudications}
            if observed_claims != expected_claims:
                issues.append(f"atomic_adjudication_scope_mismatch:{adjudication.presentation_id}")
    adjudication_by_id = {row.presentation_id: row for row in relevant_adjudications}
    missing_labels = [presentation for presentation in by_presentation if len(annotation_groups.get(presentation, [])) != 2]
    missing_adjudication = [presentation for presentation in by_presentation if presentation not in adjudication_by_id]
    if missing_labels:
        issues.append(f"missing_two_judge_labels:{len(missing_labels)}")
    if missing_adjudication:
        issues.append(f"missing_adjudication:{len(missing_adjudication)}")

    metrics: dict[str, object] = {
        "n_expected_observations": expected_observations,
        "n_completed_observations": sum(row.status == "complete" for row in relevant),
        "n_failed_observations": sum(row.status == "failed" for row in relevant),
        "failure_rate": sum(row.status == "failed" for row in relevant) / expected_observations
        if expected_observations
        else 1.0,
    }
    agreement: dict[str, object] = {}
    comparisons: dict[str, object] = {}
    threshold_results: dict[str, bool] = {}
    if not issues:
        per_condition: dict[str, dict[str, object]] = {}
        for condition in protocol.conditions:
            rows = [row for row in relevant if row.condition_id == condition.condition_id]
            labels = [adjudication_by_id[row.presentation_id] for row in rows]
            primary = [label.correctness == 2 for label in labels]
            correctness = [label.correctness / 2 for label in labels]
            confidence_rows = [(row.confidence, success) for row, success in zip(rows, primary)]
            atomic_labels = [
                claim_label
                for label in labels
                for claim_label in label.claim_adjudications
                if claim_label.label != "not_applicable"
            ]
            atomic_supported = [claim_label.label == "supported" for claim_label in atomic_labels]
            condition_metrics: dict[str, object] = {
                "n": len(rows),
                "correctness_full_rate": binary_rate(sum(primary), len(primary)).to_dict(),
                "correctness_mean": _metric_mean(correctness),
                "completeness_mean": _metric_mean([label.completeness / 2 for label in labels]),
                "faithfulness_mean": _metric_mean([label.faithfulness / 2 for label in labels]),
                "usefulness_mean": _metric_mean([label.usefulness / 2 for label in labels]),
                "abstention_rate": _metric_mean([float(label.abstention_appropriate) for label in labels]),
                "critical_safety_failure_rate": _metric_mean([float(label.critical_safety_failure) for label in labels]),
                "latency_mean": _metric_mean([row.latency_seconds for row in rows if row.latency_seconds is not None]),
                "latency_p95": _percentile([row.latency_seconds for row in rows if row.latency_seconds is not None], 0.95),
                "latency_p99": _percentile([row.latency_seconds for row in rows if row.latency_seconds is not None], 0.99),
                "confidence_coverage": len(confidence_rows) / len(rows),
                "atomic_claim_count": len(atomic_labels),
                "atomic_claim_support_rate": (sum(atomic_supported) / len(atomic_supported)) if atomic_supported else None,
                "atomic_claim_label_distribution": {
                    label: sum(claim_label.label == label for claim_label in atomic_labels)
                    for label in sorted(QUALITY_SUPPORT_LABELS)
                },
                "difficult_case_rate": _metric_mean([float(label.correctness < 2) for label in labels]),
                "label_distribution": {
                    field_name: {
                        str(score): sum(getattr(label, field_name) == score for label in labels)
                        for score in range(3)
                    }
                    for field_name in QUALITY_SCORE_FIELDS
                },
            }
            if confidence_rows and all(confidence is not None for confidence, _ in confidence_rows):
                probabilities, outcomes = zip(*confidence_rows)
                condition_metrics["brier_score"] = brier_score(probabilities, outcomes)
                condition_metrics["expected_calibration_error"] = expected_calibration_error(probabilities, outcomes)
                condition_metrics["reliability_curve"] = reliability_curve(probabilities, outcomes)
                condition_metrics["selective_accuracy"] = selective_accuracy(probabilities, outcomes)
            else:
                condition_metrics["brier_score"] = None
                condition_metrics["expected_calibration_error"] = None
                condition_metrics["reliability_curve"] = ()
                condition_metrics["selective_accuracy"] = ()
            by_stratum: dict[str, dict[str, object]] = {}
            for stratum in sorted({row.stratum for row in rows}):
                stratum_rows = [row for row in rows if row.stratum == stratum]
                stratum_labels = [adjudication_by_id[row.presentation_id] for row in stratum_rows]
                stratum_success = [label.correctness == 2 for label in stratum_labels]
                by_stratum[stratum] = {
                    "n": len(stratum_rows),
                    "correctness_full_rate": binary_rate(sum(stratum_success), len(stratum_success)).to_dict(),
                    "correctness_mean": _metric_mean([label.correctness / 2 for label in stratum_labels]),
                    "faithfulness_mean": _metric_mean([label.faithfulness / 2 for label in stratum_labels]),
                    "usefulness_mean": _metric_mean([label.usefulness / 2 for label in stratum_labels]),
                    "critical_safety_failure_rate": _metric_mean(
                        [float(label.critical_safety_failure) for label in stratum_labels]
                    ),
                }
            condition_metrics["by_stratum"] = by_stratum
            per_condition[condition.condition_id] = condition_metrics
        metrics["conditions"] = per_condition

        for field_name in QUALITY_SCORE_FIELDS:
            left = []
            right = []
            for group in annotation_groups.values():
                ordered = sorted(group, key=lambda annotation: annotation.judge_id)
                left.append(getattr(ordered[0], field_name))
                right.append(getattr(ordered[1], field_name))
            agreement[field_name] = weighted_cohen_kappa(left, right)
            disagreement_count = sum(a != b for a, b in zip(left, right))
            agreement[f"{field_name}_disagreement"] = {
                "n": disagreement_count,
                "rate": disagreement_count / len(left),
            }
        agreement["n_double_rated"] = len(annotation_groups)
        abstention_disagreement = sum(
            group[0].abstention_appropriate != group[1].abstention_appropriate
            for group in annotation_groups.values()
        )
        agreement["abstention_disagreement"] = {
            "n": abstention_disagreement,
            "rate": abstention_disagreement / len(annotation_groups),
        }
        agreement["critical_safety_disagreement"] = {
            "n": sum(group[0].critical_safety_failure != group[1].critical_safety_failure for group in annotation_groups.values()),
            "rate": sum(group[0].critical_safety_failure != group[1].critical_safety_failure for group in annotation_groups.values())
            / len(annotation_groups),
        }
        agreement["critical_safety_raw_agreement"] = _metric_mean(
            [float(group[0].critical_safety_failure == group[1].critical_safety_failure) for group in annotation_groups.values()]
        )
        failure_modes: dict[str, int] = {}
        for annotation in relevant_annotations:
            for failure_mode in annotation.failure_modes:
                failure_modes[failure_mode] = failure_modes.get(failure_mode, 0) + 1
        agreement["failure_mode_counts"] = dict(sorted(failure_modes.items()))

        default_by_model = {
            condition.model: condition.condition_id
            for condition in protocol.conditions
            if condition.mode == "harness"
        }
        for condition in protocol.conditions:
            if condition.mode == "harness":
                continue
            baseline_id = default_by_model[condition.model]
            left_rows = {row.question_id: row for row in relevant if row.condition_id == condition.condition_id}
            right_rows = {row.question_id: row for row in relevant if row.condition_id == baseline_id}
            keys = sorted(set(left_rows) & set(right_rows))
            left_success = [adjudication_by_id[left_rows[key].presentation_id].correctness == 2 for key in keys]
            right_success = [adjudication_by_id[right_rows[key].presentation_id].correctness == 2 for key in keys]
            # Each question is the paired resampling cluster.  This keeps the
            # primary unit explicit even when a question has multiple model rows.
            clusters = {
                key: [float(adjudication_by_id[left_rows[key].presentation_id].correctness == 2)]
                for key in keys
            }
            cluster_right = {
                key: [float(adjudication_by_id[right_rows[key].presentation_id].correctness == 2)]
                for key in keys
            }
            stratified: dict[str, dict[str, object]] = {}
            for stratum in sorted({left_rows[key].stratum for key in keys}):
                stratum_keys = [key for key in keys if left_rows[key].stratum == stratum]
                stratified[stratum] = {
                    "n": len(stratum_keys),
                    "exact_mcnemar": exact_paired_binary(
                        [adjudication_by_id[left_rows[key].presentation_id].correctness == 2 for key in stratum_keys],
                        [adjudication_by_id[right_rows[key].presentation_id].correctness == 2 for key in stratum_keys],
                    ).to_dict(),
                }
            comparisons[f"{condition.condition_id}_vs_{baseline_id}"] = {
                "n": len(keys),
                "exact_mcnemar": exact_paired_binary(left_success, right_success).to_dict(),
                "clustered_delta": clustered_paired_comparison(
                    clusters,
                    cluster_right,
                    resamples=DEFAULT_RESAMPLES,
                    permutations=DEFAULT_RESAMPLES,
                    confidence=protocol.confidence,
                ).to_dict(),
                "by_stratum": stratified,
            }
        metrics["n_primary_questions"] = len(expected_ids)
        metrics["n_conditions"] = len(condition_ids)
        primary_condition = next(condition for condition in protocol.conditions if condition.mode == "harness")
        metrics["primary_condition_id"] = primary_condition.condition_id
        metrics["primary_metric"] = protocol.primary_metric
        primary_metrics = per_condition[primary_condition.condition_id]
        if protocol.thresholds:
            threshold_results = _evaluate_thresholds(protocol.thresholds, primary_metrics, agreement)
    else:
        pass

    evidence_manifest: dict[str, object] = {
        "protocol_sha256": protocol.protocol_sha256,
        "benchmark_sha256": protocol.benchmark_provenance["sha256"],
        "benchmark_size_bytes": protocol.benchmark_provenance["size_bytes"],
        "rubric_version": protocol.rubric_version,
        "rubric": dict(protocol.rubric),
        "judge_ids": list(protocol.judge_ids),
        "adjudicator_id": protocol.adjudicator_id,
        "blind_packet_version": protocol.blind_packet_version,
        "evaluation_mode": protocol.evaluation_mode,
        "judge_models": [
            {"judge_id": judge_id, "model": model, "digest": digest}
            for judge_id, model, digest in protocol.judge_models
        ],
        "adjudicator_model": (
            {"model": protocol.adjudicator_model[0], "digest": protocol.adjudicator_model[1]}
            if protocol.adjudicator_model
            else {}
        ),
        "judge_prompt_version": protocol.judge_prompt_version,
        "generation_options": dict(protocol.generation_options),
        "condition_ids": sorted(condition_ids),
        "question_ids": sorted(expected_ids),
        "model_digests": {
            model: sorted(digests) for model, digests in sorted(model_digests.items())
        },
        "config_fingerprints": {
            condition_id: sorted({row.config_fingerprint for row in relevant if row.condition_id == condition_id})
            for condition_id in sorted(condition_ids)
        },
        "code_fingerprints": sorted(code_digests),
        "answer_digests": {
            row.observation_id: row.answer_sha256
            for row in sorted(relevant, key=lambda item: item.observation_id)
        },
        "source_files": source_files,
        "expected_observations": expected_observations,
        "observed_observations": len(relevant),
        "raw_files": list(raw_entries),
        "raw_ledger_sha256": fingerprint_json(list(raw_entries)),
        "judge_raw_files": [
            {
                "path": annotation.raw_path,
                "sha256": annotation.raw_sha256,
                "model_digest": annotation.evaluator_model_digest,
                "prompt_sha256": annotation.prompt_sha256,
            }
            for annotation in sorted(relevant_annotations, key=lambda row: (row.presentation_id, row.judge_id))
            if annotation.raw_path
        ],
        "adjudication_raw_files": [
            {
                "path": adjudication.raw_path,
                "sha256": adjudication.raw_sha256,
                "model_digest": adjudication.adjudicator_model_digest,
                "prompt_sha256": adjudication.prompt_sha256,
            }
            for adjudication in sorted(relevant_adjudications, key=lambda row: row.presentation_id)
            if adjudication.raw_path
        ],
        "annotations_sha256": fingerprint_json(
            [annotation.to_dict() for annotation in sorted(relevant_annotations, key=lambda row: (row.presentation_id, row.judge_id))]
        ),
        "adjudications_sha256": fingerprint_json(
            [adjudication.to_dict() for adjudication in sorted(relevant_adjudications, key=lambda row: row.presentation_id)]
        ),
    }
    report_provenance = dict(provenance or {})
    report_provenance.setdefault("protocol_sha256", protocol.protocol_sha256)
    report_provenance.setdefault("benchmark_provenance", dict(protocol.benchmark_provenance))
    if evidence_root is not None:
        report_provenance.setdefault("evidence_root", str(Path(evidence_root).resolve()))

    if not issues and phase == "confirmatory" and not protocol.frozen:
        issues.append("thresholds_not_frozen")
    status = "failed" if issues else "complete_not_promoted"
    if not issues and phase == "confirmatory" and protocol.frozen and threshold_results and all(threshold_results.values()):
        status = "passed"
    return QualityReport(
        protocol_id=protocol.protocol_id,
        phase=phase,
        status=status,
        benchmark_provenance=dict(protocol.benchmark_provenance),
        n_observations=len(relevant),
        n_annotations=len(relevant_annotations),
        n_adjudications=len([key for key in adjudication_by_id if key in by_presentation]),
        metrics=metrics,
        agreement=agreement,
        comparisons=comparisons,
        threshold_results=threshold_results,
        evidence_manifest=evidence_manifest,
        issues=tuple(issues),
        provenance=report_provenance,
    )


def _evaluate_thresholds(
    thresholds: Mapping[str, float],
    primary_metrics: Mapping[str, object],
    agreement: Mapping[str, object],
) -> dict[str, bool]:
    """Evaluate only declared thresholds; unknown keys fail closed."""
    results: dict[str, bool] = {}
    for name, threshold in thresholds.items():
        if name == "correctness_lower_bound":
            measured = _finite(_mapping(primary_metrics.get("correctness_full_rate"), "correctness_full_rate").get("low"), "correctness lower bound")
            results[name] = measured >= threshold
        elif name == "faithfulness_mean":
            results[name] = _finite(primary_metrics.get("faithfulness_mean"), name) >= threshold
        elif name == "critical_safety_failure_rate_upper_bound":
            measured = _finite(primary_metrics.get("critical_safety_failure_rate"), name)
            results[name] = measured <= threshold
        elif name == "brier_score_upper_bound":
            brier_measured = _optional_finite(primary_metrics.get("brier_score"), name)
            results[name] = brier_measured is not None and brier_measured <= threshold
        elif name == "expected_calibration_error_upper_bound":
            ece_measured = _optional_finite(primary_metrics.get("expected_calibration_error"), name)
            results[name] = ece_measured is not None and ece_measured <= threshold
        elif name == "confidence_coverage_lower_bound":
            measured = _finite(primary_metrics.get("confidence_coverage"), name)
            results[name] = measured >= threshold
        elif name == "atomic_claim_support_lower_bound":
            support_measured = _optional_finite(primary_metrics.get("atomic_claim_support_rate"), name)
            results[name] = support_measured is not None and support_measured >= threshold
        elif name == "inter_judge_kappa_lower_bound":
            measured = min(_finite(agreement.get(field), f"agreement[{field}]") for field in QUALITY_SCORE_FIELDS)
            results[name] = measured >= threshold
        else:
            results[name] = False
    return results


def load_quality_report(path: str | Path) -> QualityReport:
    """Load and validate a quality report."""
    return QualityReport.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def promote_quality_report(
    source_path: str | Path,
    target_path: str | Path,
    *,
    overwrite: bool = False,
    acceptance_path: str | Path | None = None,
) -> Path:
    """Promote only a passed quality certificate, never a merely complete run."""
    report = load_quality_report(source_path)
    if report.status != "passed":
        raise ValueError("only a passed quality certificate may be promoted")
    if not report.evidence_manifest or not report.provenance.get("protocol_sha256"):
        raise ValueError("quality promotion requires protocol and evidence provenance")
    required_manifest_keys = {
        "protocol_sha256",
        "benchmark_sha256",
        "benchmark_size_bytes",
        "rubric_version",
        "rubric",
        "evaluation_mode",
        "blind_packet_version",
        "judge_ids",
        "adjudicator_id",
        "generation_options",
        "condition_ids",
        "question_ids",
        "model_digests",
        "config_fingerprints",
        "code_fingerprints",
        "answer_digests",
        "raw_files",
        "source_files",
    }
    if not required_manifest_keys.issubset(report.evidence_manifest):
        missing = sorted(required_manifest_keys - set(report.evidence_manifest))
        raise ValueError(f"quality promotion requires complete evidence manifest: {', '.join(missing)}")
    if report.evidence_manifest.get("evaluation_mode") != "expert_human":
        raise ValueError(
            "quality promotion requires independently blinded expert-human annotations; "
            "the local LLM-judge lane is exploratory and non-promotable"
        )
    benchmark_issue = _validate_benchmark_file(report.benchmark_provenance)
    if benchmark_issue:
        raise ValueError(f"quality promotion benchmark provenance is not current: {benchmark_issue}")
    evidence_root_value = report.provenance.get("evidence_root")
    if not isinstance(evidence_root_value, str) or not Path(evidence_root_value).is_dir():
        raise ValueError("quality promotion requires an existing raw evidence root")
    raw_files = report.evidence_manifest.get("raw_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("quality promotion requires raw evidence entries")
    raw_root = Path(evidence_root_value)
    for entry in raw_files:
        if not isinstance(entry, Mapping):
            raise ValueError("quality promotion raw evidence manifest is invalid")
        raw_path_value = entry.get("raw_path")
        raw_sha_value = entry.get("sha256")
        size_value = entry.get("size_bytes")
        if not isinstance(raw_path_value, str) or Path(raw_path_value).is_absolute() or ".." in Path(raw_path_value).parts:
            raise ValueError("quality promotion raw evidence path is unsafe")
        raw_path = raw_root / raw_path_value
        if not raw_path.is_file():
            raise ValueError(f"quality promotion raw evidence is missing: {raw_path_value}")
        raw_bytes = raw_path.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != raw_sha_value or len(raw_bytes) != size_value:
            raise ValueError(f"quality promotion raw evidence digest mismatch: {raw_path_value}")
    source_files = report.evidence_manifest.get("source_files")
    if not isinstance(source_files, Mapping) or not source_files:
        raise ValueError("quality promotion source-file manifest is invalid")
    required_source_names = {"protocol", "observations", "annotations", "adjudications"}
    missing_source_names = sorted(required_source_names - set(source_files))
    if missing_source_names:
        raise ValueError(
            "quality promotion requires bound protocol and ledger source files: "
            + ", ".join(missing_source_names)
        )
    protocol_source = source_files.get("protocol")
    if not isinstance(protocol_source, Mapping):
        raise ValueError("quality promotion requires the bound protocol source file")
    protocol_source_path = protocol_source.get("path")
    if not isinstance(protocol_source_path, str) or not Path(protocol_source_path).is_file():
        raise ValueError("quality promotion protocol source file is missing")
    try:
        bound_protocol = QualityProtocol.from_dict(
            json.loads(Path(protocol_source_path).read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("quality promotion protocol source file is unreadable") from exc
    if bound_protocol.protocol_sha256 != report.evidence_manifest.get("protocol_sha256"):
        raise ValueError("quality promotion protocol source digest mismatch")
    if bound_protocol.evaluation_mode != "expert_human":
        raise ValueError(
            "quality promotion requires an expert_human protocol; local LLM-judge evidence is non-promotable"
        )
    if bound_protocol.judge_models:
        judge_raw_files = report.evidence_manifest.get("judge_raw_files")
        adjudication_raw_files = report.evidence_manifest.get("adjudication_raw_files")
        expected_judge_files = report.n_observations * len(bound_protocol.judge_ids)
        if not isinstance(judge_raw_files, list) or len(judge_raw_files) != expected_judge_files:
            raise ValueError("quality promotion requires complete judge raw evidence")
        if not isinstance(adjudication_raw_files, list) or len(adjudication_raw_files) != report.n_adjudications:
            raise ValueError("quality promotion requires complete adjudication raw evidence")
        for entry in [*judge_raw_files, *adjudication_raw_files]:
            if not isinstance(entry, Mapping):
                raise ValueError("quality promotion judge evidence manifest is invalid")
            relative_value = entry.get("path")
            digest_value = entry.get("sha256")
            if not isinstance(relative_value, str) or Path(relative_value).is_absolute() or ".." in Path(relative_value).parts:
                raise ValueError("quality promotion judge evidence path is unsafe")
            evidence_path = raw_root / relative_value
            if not evidence_path.is_file():
                raise ValueError(f"quality promotion judge evidence is missing: {relative_value}")
            if hashlib.sha256(evidence_path.read_bytes()).hexdigest() != digest_value:
                raise ValueError(f"quality promotion judge evidence digest mismatch: {relative_value}")
    pilot_review_issue = _validate_pilot_review_binding(bound_protocol)
    if pilot_review_issue is not None:
        raise ValueError(f"quality promotion pilot review binding failed: {pilot_review_issue}")
    for source in source_files.values():
        if not isinstance(source, Mapping):
            raise ValueError("quality promotion source-file manifest is invalid")
        source_path_value = source.get("path")
        if not isinstance(source_path_value, str) or not Path(source_path_value).is_file():
            raise ValueError("quality promotion source file is missing")
        source_bytes = Path(source_path_value).read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != source.get("sha256") or len(source_bytes) != source.get("size_bytes"):
            raise ValueError("quality promotion source-file digest mismatch")
    if report.evidence_manifest.get("protocol_sha256") != report.provenance.get("protocol_sha256"):
        raise ValueError("quality promotion protocol digest mismatch")
    if acceptance_path is None:
        raise ValueError("quality promotion requires explicit acceptance")
    acceptance_file = Path(acceptance_path)
    if not acceptance_file.is_file():
        raise ValueError("quality promotion acceptance record is missing")
    try:
        acceptance = json.loads(acceptance_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("quality promotion acceptance record is unreadable") from exc
    if not isinstance(acceptance, Mapping) or acceptance.get("accepted") is not True:
        raise ValueError("quality promotion requires accepted=true")
    if acceptance.get("report_certificate_sha256") != report.certificate_sha256:
        raise ValueError("quality promotion acceptance does not bind this certificate")
    if not isinstance(acceptance.get("accepted_by"), str) or not str(acceptance["accepted_by"]).strip():
        raise ValueError("quality promotion acceptance requires accepted_by")
    target = Path(target_path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing quality aggregate: {target}")
    return _json_write(target, report.to_dict())


__all__ = [
    "QUALITY_SCHEMA_VERSION",
    "QUALITY_PROTOCOL_VERSION",
    "QUALITY_EVALUATION_MODES",
    "QUALITY_SUPPORT_LABELS",
    "DEFAULT_QUALITY_RUBRIC",
    "QualityCondition",
    "QualityProtocol",
    "QualityClaim",
    "QualityClaimAnnotation",
    "QualityClaimAdjudication",
    "QualityObservation",
    "QualityAnnotation",
    "QualityAdjudication",
    "QualityReport",
    "default_quality_conditions",
    "parse_confidence_response",
    "weighted_cohen_kappa",
    "brier_score",
    "expected_calibration_error",
    "reliability_curve",
    "selective_accuracy",
    "quality_code_fingerprint",
    "load_jsonl",
    "write_jsonl",
    "build_quality_report",
    "load_quality_report",
    "promote_quality_report",
]
