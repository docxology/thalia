"""Resumable, provenance-first live research campaigns.

The deterministic evaluation package owns cohort construction, checkpoint
validation, metric calculation, and promotion safety.  The command-line runner
only supplies I/O and the live Ollama model.  Campaign files are intentionally
separate from the committed aggregate measurements: an interrupted or partial
neural run can never silently become manuscript evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from ..compiler.metrics import EvalExample, answer_score, grounding_score, harness_metric, token_f1
from ..config import HarnessConfig, default_config
from ..harness import AutoHarness
from ..module import LMClient
from ..signatures import HarnessOutput
from .accounting import file_provenance, fingerprint_config, fingerprint_json
from .statistics import binary_rate, bootstrap_mean


CAMPAIGN_SCHEMA_VERSION = 1
CHECKPOINT_SCHEMA_VERSION = 3
_VALID_STATUSES = {"complete", "failed"}
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _require_positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer, got {value!r}")
    return value


def _stable_rank(example_id: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}\0{example_id}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CampaignTier:
    """One nested cohort/policy/model evaluation tier."""

    tier_id: str
    sample_size: int
    model: str
    policy: str = "default"
    config_overrides: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.tier_id.strip():
            raise ValueError("tier_id must be non-empty")
        _require_positive_int(self.sample_size, "sample_size")
        if not self.model.strip():
            raise ValueError("model must be non-empty")
        if not self.policy.strip():
            raise ValueError("policy must be non-empty")
        keys = [key for key, _ in self.config_overrides]
        if len(keys) != len(set(keys)):
            raise ValueError("config_overrides must not contain duplicate keys")

    def config(self, base: HarnessConfig | None = None) -> HarnessConfig:
        """Return the validated harness config for this tier."""
        return (base or default_config()).with_(**dict(self.config_overrides))

    def to_dict(self) -> dict[str, object]:
        return {
            "tier_id": self.tier_id,
            "sample_size": self.sample_size,
            "model": self.model,
            "policy": self.policy,
            "config_overrides": dict(self.config_overrides),
        }


@dataclass(frozen=True)
class CampaignSpec:
    """Validated campaign matrix and deterministic cohort-selection contract."""

    campaign_id: str
    benchmark_path: str | Path
    tiers: tuple[CampaignTier, ...]
    selection_salt: str = "thalia-v2-longmemeval"
    generation_options: tuple[tuple[str, Any], ...] = (("temperature", 0.0), ("num_predict", 512))
    max_consecutive_failures: int = 3
    min_free_bytes: int = 5 * 1024 * 1024 * 1024

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError("campaign_id must be non-empty")
        if not self.selection_salt.strip():
            raise ValueError("selection_salt must be non-empty")
        if not self.tiers:
            raise ValueError("campaign must contain at least one tier")
        if len({tier.tier_id for tier in self.tiers}) != len(self.tiers):
            raise ValueError("campaign tier IDs must be unique")
        _require_positive_int(self.max_consecutive_failures, "max_consecutive_failures")
        _require_positive_int(self.min_free_bytes, "min_free_bytes")
        keys = [key for key, _ in self.generation_options]
        if len(keys) != len(set(keys)):
            raise ValueError("generation_options must not contain duplicate keys")

    @property
    def generation_options_dict(self) -> dict[str, Any]:
        return dict(self.generation_options)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "benchmark_path": str(self.benchmark_path),
            "tiers": [tier.to_dict() for tier in self.tiers],
            "selection_salt": self.selection_salt,
            "generation_options": self.generation_options_dict,
            "max_consecutive_failures": self.max_consecutive_failures,
            "min_free_bytes": self.min_free_bytes,
        }

    def fingerprint(self) -> str:
        return fingerprint_json(self.to_dict())


def select_nested_cohort(
    examples: Sequence[EvalExample],
    sample_size: int,
    *,
    selection_salt: str,
) -> list[EvalExample]:
    """Select a stable, approximately balanced prefix of a deterministic order.

    Each stratum is independently ordered by a SHA-256 of ``selection_salt`` and
    ``example_id``; a round-robin merge makes every smaller cohort a prefix of
    every larger cohort while preserving representation across question types.
    """
    _require_positive_int(sample_size, "sample_size")
    if not examples:
        raise ValueError("examples must be non-empty")
    if not selection_salt:
        raise ValueError("selection_salt must be non-empty")
    if any(not example.example_id for example in examples):
        raise ValueError("all examples require a stable example_id")
    if len({example.example_id for example in examples}) != len(examples):
        raise ValueError("example IDs must be unique")

    grouped: dict[str, list[EvalExample]] = {}
    for example in examples:
        grouped.setdefault(example.stratum, []).append(example)
    ranked = {
        stratum: sorted(rows, key=lambda row: (_stable_rank(row.example_id, selection_salt), row.example_id))
        for stratum, rows in sorted(grouped.items())
    }
    order: list[EvalExample] = []
    cursor = 0
    strata = tuple(ranked)
    while len(order) < len(examples):
        advanced = False
        for stratum in strata:
            rows = ranked[stratum]
            if cursor < len(rows):
                order.append(rows[cursor])
                advanced = True
        if not advanced:
            break
        cursor += 1
    return order[: min(sample_size, len(order))]


def select_nested_cohorts(
    examples: Sequence[EvalExample],
    sizes: Iterable[int],
    *,
    selection_salt: str,
) -> dict[int, list[EvalExample]]:
    """Build nested cohorts and reject accidental non-nested selection."""
    ordered_sizes = tuple(sorted({_require_positive_int(size, "sample_size") for size in sizes}))
    if not ordered_sizes:
        raise ValueError("sizes must be non-empty")
    cohorts = {size: select_nested_cohort(examples, size, selection_salt=selection_salt) for size in ordered_sizes}
    previous: set[str] = set()
    for size in ordered_sizes:
        current = {example.example_id for example in cohorts[size]}
        if not previous.issubset(current):
            raise ValueError("nested cohort construction violated prefix inclusion")
        previous = current
    return cohorts


@dataclass(frozen=True)
class CampaignRow:
    """One live observation or explicitly accounted failure."""

    row_id: str
    tier_id: str
    example_id: str
    model: str
    policy: str
    status: str
    accuracy: float | None = None
    grounding_session: float | None = None
    composite: float | None = None
    citation_precision: float | None = None
    source_recall: float | None = None
    citation_token_f1: float | None = None
    ranked_evidence_count: int | None = None
    latency_seconds: float | None = None
    answer_sha256: str | None = None
    citation_indices: tuple[int, ...] = ()
    error_class: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.row_id or not self.tier_id or not self.example_id or not self.model or not self.policy:
            raise ValueError("campaign rows require non-empty identity fields")
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"campaign row status must be one of {_VALID_STATUSES}")
        metric_values = (
            self.accuracy,
            self.grounding_session,
            self.composite,
            self.citation_precision,
            self.source_recall,
            self.citation_token_f1,
        )
        if any(value is not None and (not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0) for value in metric_values[:4]):
            raise ValueError("campaign quality metrics must be finite values in [0, 1]")
        if any(value is not None and (not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0) for value in metric_values[4:]):
            raise ValueError("campaign quality metrics must be finite values in [0, 1]")
        if self.latency_seconds is not None and (not isinstance(self.latency_seconds, (int, float)) or self.latency_seconds < 0):
            raise ValueError("latency_seconds must be non-negative")
        if self.ranked_evidence_count is not None and (isinstance(self.ranked_evidence_count, bool) or self.ranked_evidence_count < 0):
            raise ValueError("ranked_evidence_count must be non-negative")
        if self.status == "complete" and self.error_class is not None:
            raise ValueError("complete campaign rows cannot carry errors")
        if self.status == "complete":
            required_values = (
                self.accuracy,
                self.grounding_session,
                self.composite,
                self.citation_precision,
                self.source_recall,
                self.citation_token_f1,
                self.ranked_evidence_count,
                self.latency_seconds,
                self.answer_sha256,
            )
            if any(value is None for value in required_values):
                raise ValueError("complete campaign rows require all metrics and answer identity")
        if self.status == "failed" and not self.error_class:
            raise ValueError("failed campaign rows require error_class")

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "row_id": self.row_id,
            "tier_id": self.tier_id,
            "example_id": self.example_id,
            "model": self.model,
            "policy": self.policy,
            "status": self.status,
            "accuracy": self.accuracy,
            "grounding_session": self.grounding_session,
            "composite": self.composite,
            "citation_precision": self.citation_precision,
            "source_recall": self.source_recall,
            "citation_token_f1": self.citation_token_f1,
            "ranked_evidence_count": self.ranked_evidence_count,
            "latency_seconds": self.latency_seconds,
            "answer_sha256": self.answer_sha256,
            "citation_indices": list(self.citation_indices),
            "error_class": self.error_class,
            "error_message": self.error_message,
        }
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "CampaignRow":
        citations = data.get("citation_indices", ())
        if not isinstance(citations, (list, tuple)) or not all(isinstance(value, int) and not isinstance(value, bool) for value in citations):
            raise ValueError("citation_indices must be integer list")
        return cls(
            row_id=str(data.get("row_id", "")),
            tier_id=str(data.get("tier_id", "")),
            example_id=str(data.get("example_id", "")),
            model=str(data.get("model", "")),
            policy=str(data.get("policy", "")),
            status=str(data.get("status", "")),
            accuracy=_optional_float(data.get("accuracy"), "accuracy"),
            grounding_session=_optional_float(data.get("grounding_session"), "grounding_session"),
            composite=_optional_float(data.get("composite"), "composite"),
            citation_precision=_optional_float(data.get("citation_precision"), "citation_precision"),
            source_recall=_optional_float(data.get("source_recall"), "source_recall"),
            citation_token_f1=_optional_float(data.get("citation_token_f1"), "citation_token_f1"),
            ranked_evidence_count=_optional_nonnegative_int(data.get("ranked_evidence_count"), "ranked_evidence_count"),
            latency_seconds=_optional_nonnegative_float(data.get("latency_seconds"), "latency_seconds"),
            answer_sha256=_optional_string(data.get("answer_sha256")),
            citation_indices=tuple(citations),
            error_class=_optional_string(data.get("error_class")),
            error_message=_optional_string(data.get("error_message")),
        )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("optional string must be non-empty text or null")
    return value


def _optional_float(value: object, field: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric or null")
    numeric = float(value)
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        raise ValueError(f"{field} must be finite")
    return numeric


def _optional_nonnegative_float(value: object, field: str) -> float | None:
    numeric = _optional_float(value, field)
    if numeric is not None and numeric < 0:
        raise ValueError(f"{field} must be non-negative")
    return numeric


def _optional_nonnegative_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer or null")
    return value


@dataclass(frozen=True)
class CampaignCheckpoint:
    """Atomic resumable envelope bound to one exact benchmark/model/config scope."""

    campaign_id: str
    tier_id: str
    benchmark_provenance: Mapping[str, object]
    model: str
    model_metadata: Mapping[str, object]
    generation_options: Mapping[str, object]
    config_fingerprint: str
    code_fingerprint: str
    selected_ids: tuple[str, ...]
    rows: tuple[CampaignRow, ...] = ()

    @property
    def model_digest(self) -> object:
        """Return the immutable model digest captured in model metadata."""
        return self.model_metadata.get("digest")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "tier_id": self.tier_id,
            "benchmark_provenance": dict(self.benchmark_provenance),
            "model": self.model,
            "model_metadata": dict(self.model_metadata),
            "model_digest": self.model_digest,
            "generation_options": dict(self.generation_options),
            "config_fingerprint": self.config_fingerprint,
            "code_fingerprint": self.code_fingerprint,
            "selected_ids": list(self.selected_ids),
            "rows": [row.to_dict() for row in self.rows],
        }

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
        temporary = target.with_name(f".{target.name}.tmp")
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return target

    @classmethod
    def read(cls, path: str | Path) -> "CampaignCheckpoint":
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("unsupported campaign checkpoint schema")
        selected = data.get("selected_ids")
        raw_rows = data.get("rows")
        if not isinstance(selected, list) or not selected or not all(isinstance(value, str) and value for value in selected):
            raise ValueError("checkpoint selected_ids must be non-empty strings")
        if len(set(selected)) != len(selected):
            raise ValueError("checkpoint selected_ids must be unique")
        if not isinstance(raw_rows, list):
            raise ValueError("checkpoint rows must be a list")
        campaign_id = _required_text(data, "campaign_id")
        tier_id = _required_text(data, "tier_id")
        benchmark = _required_mapping(data, "benchmark_provenance")
        if not isinstance(benchmark.get("sha256"), str) or not benchmark["sha256"]:
            raise ValueError("checkpoint benchmark provenance requires SHA-256")
        model = _required_text(data, "model")
        generation_options = _required_mapping(data, "generation_options")
        if not generation_options:
            raise ValueError("checkpoint generation_options must be non-empty")
        config_fingerprint = _required_text(data, "config_fingerprint")
        code_fingerprint = _required_text(data, "code_fingerprint")
        rows = tuple(CampaignRow.from_dict(row) for row in raw_rows if isinstance(row, Mapping))
        if len(rows) != len(raw_rows):
            raise ValueError("checkpoint rows must contain mappings")
        if len({row.row_id for row in rows}) != len(rows):
            raise ValueError("checkpoint row IDs must be unique")
        if len({row.example_id for row in rows}) != len(rows):
            raise ValueError("checkpoint example IDs must be unique")
        if any(row.example_id not in selected for row in rows):
            raise ValueError("checkpoint row is outside selected_ids")
        if any(row.tier_id != tier_id or row.model != model for row in rows):
            raise ValueError("checkpoint row provenance mismatches checkpoint scope")
        declared_digest = data.get("model_digest")
        metadata = _required_mapping(data, "model_metadata")
        if not isinstance(declared_digest, str) or not declared_digest or declared_digest != metadata.get("digest"):
            raise ValueError("checkpoint model_digest does not match model_metadata.digest")
        return cls(
            campaign_id=campaign_id,
            tier_id=tier_id,
            benchmark_provenance=benchmark,
            model=model,
            model_metadata=metadata,
            generation_options=generation_options,
            config_fingerprint=config_fingerprint,
            code_fingerprint=code_fingerprint,
            selected_ids=tuple(selected),
            rows=rows,
        )


def _required_text(data: Mapping[str, object], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"checkpoint {field} must be non-empty text")
    return value


def _required_mapping(data: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = data.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"checkpoint {field} must be a mapping")
    return dict(value)


def code_fingerprint(project_root: str | Path = _PROJECT_ROOT) -> str:
    """Fingerprint the live campaign implementation and metric contracts."""
    root = Path(project_root)
    paths = (
        root / "src" / "evaluation" / "campaign.py",
        root / "src" / "evaluation" / "longmemeval.py",
        root / "src" / "compiler" / "metrics.py",
        root / "src" / "harness.py",
    )
    return fingerprint_json(
        [
            {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in paths
            if path.is_file()
        ]
    )


def _row_id(tier_id: str, model: str, example_id: str) -> str:
    return f"{tier_id}:{model}:{example_id}"


def _checkpoint_scope_path(
    root: Path,
    *,
    tier: CampaignTier,
    benchmark: Mapping[str, object],
    config_fingerprint: str,
    code_digest: str,
    model_metadata: Mapping[str, object],
    generation_options: Mapping[str, object],
) -> Path:
    """Return a deterministic sidecar path for a non-default checkpoint scope."""
    scope = fingerprint_json(
        {
            "tier": tier.to_dict(),
            "benchmark": dict(benchmark),
            "config_fingerprint": config_fingerprint,
            "code_fingerprint": code_digest,
            "model_metadata": dict(model_metadata),
            "generation_options": dict(generation_options),
        }
    )[:16]
    return root / "checkpoints" / f"{tier.tier_id}.scope-{scope}.json"


def _citation_precision(output: HarnessOutput, example: EvalExample) -> float:
    cited = {citation.source_index for citation in output.evidence_citations}
    if not cited:
        return 0.0
    if not example.expected_source_indices:
        return 1.0
    return len(cited & set(example.expected_source_indices)) / len(cited)


def _source_recall(output: HarnessOutput, example: EvalExample) -> float:
    expected = set(example.expected_source_indices)
    if not expected:
        return 1.0 if output.evidence_citations else 0.0
    cited = {citation.source_index for citation in output.evidence_citations}
    return len(cited & expected) / len(expected)


def _citation_token_f1(output: HarnessOutput) -> float:
    cited_text = " ".join(citation.excerpt for citation in output.evidence_citations)
    return token_f1(output.answer, cited_text) if cited_text else 0.0


def _make_complete_row(
    *,
    tier: CampaignTier,
    example: EvalExample,
    output: HarnessOutput,
    latency_seconds: float,
) -> CampaignRow:
    return CampaignRow(
        row_id=_row_id(tier.tier_id, tier.model, example.example_id),
        tier_id=tier.tier_id,
        example_id=example.example_id,
        model=tier.model,
        policy=tier.policy,
        status="complete",
        accuracy=answer_score(output, example),
        grounding_session=grounding_score(output, example),
        composite=harness_metric(output, example),
        citation_precision=_citation_precision(output, example),
        source_recall=_source_recall(output, example),
        citation_token_f1=_citation_token_f1(output),
        ranked_evidence_count=len(output.ranked_evidence),
        latency_seconds=latency_seconds,
        answer_sha256=hashlib.sha256(output.answer.encode("utf-8")).hexdigest(),
        citation_indices=tuple(citation.source_index for citation in output.evidence_citations),
    )


def _make_failed_row(*, tier: CampaignTier, example: EvalExample, error: BaseException) -> CampaignRow:
    return CampaignRow(
        row_id=_row_id(tier.tier_id, tier.model, example.example_id),
        tier_id=tier.tier_id,
        example_id=example.example_id,
        model=tier.model,
        policy=tier.policy,
        status="failed",
        error_class=type(error).__name__,
        error_message=str(error)[:500],
    )


def _checkpoint_scope_matches(
    checkpoint: CampaignCheckpoint,
    *,
    spec: CampaignSpec,
    tier: CampaignTier,
    benchmark: Mapping[str, object],
    selected_ids: Sequence[str],
    config_fingerprint: str,
    code_digest: str,
    model_metadata: Mapping[str, object],
) -> bool:
    return (
        checkpoint.campaign_id == spec.campaign_id
        and checkpoint.tier_id == tier.tier_id
        and checkpoint.benchmark_provenance == dict(benchmark)
        and checkpoint.model == tier.model
        and checkpoint.model_metadata == dict(model_metadata)
        and checkpoint.generation_options == spec.generation_options_dict
        and checkpoint.config_fingerprint == config_fingerprint
        and checkpoint.code_fingerprint == code_digest
        and checkpoint.selected_ids == tuple(selected_ids)
    )


@dataclass(frozen=True)
class CampaignReport:
    """Promotion-ready campaign aggregate and complete accounting."""

    campaign_id: str
    status: str
    benchmark_provenance: Mapping[str, object]
    campaign_fingerprint: str
    code_fingerprint: str
    tiers: Mapping[str, Mapping[str, object]]
    rows: tuple[CampaignRow, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "status": self.status,
            "benchmark_provenance": dict(self.benchmark_provenance),
            "campaign_fingerprint": self.campaign_fingerprint,
            "code_fingerprint": self.code_fingerprint,
            "tiers": {key: dict(value) for key, value in self.tiers.items()},
            "rows": [row.to_dict() for row in self.rows],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "CampaignReport":
        """Parse and validate a serialized campaign report."""
        if data.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
            raise ValueError("unsupported campaign report schema")
        raw_tiers = data.get("tiers")
        raw_rows = data.get("rows")
        if not isinstance(raw_tiers, Mapping) or not raw_tiers or not isinstance(raw_rows, list):
            raise ValueError("campaign report requires tiers mapping and rows list")
        rows = tuple(CampaignRow.from_dict(row) for row in raw_rows if isinstance(row, Mapping))
        if len(rows) != len(raw_rows):
            raise ValueError("campaign report rows must contain mappings")
        if len({row.row_id for row in rows}) != len(rows):
            raise ValueError("campaign report row IDs must be unique")
        if not all(isinstance(value, Mapping) for value in raw_tiers.values()):
            raise ValueError("campaign report tiers must contain mappings")
        status = data.get("status")
        if status not in {"complete", "partial"}:
            raise ValueError("campaign report status must be complete or partial")
        tiers = {str(key): dict(value) for key, value in raw_tiers.items()}
        row_groups: dict[str, list[CampaignRow]] = {tier_id: [] for tier_id in tiers}
        for row in rows:
            if row.tier_id not in row_groups:
                raise ValueError(f"campaign report row references unknown tier: {row.tier_id}")
            row_groups[row.tier_id].append(row)
        for tier_id, tier in tiers.items():
            if tier.get("tier_id") != tier_id:
                raise ValueError(f"campaign report tier key mismatch: {tier_id}")
            if tier.get("status") not in {"complete", "partial"}:
                raise ValueError(f"campaign report tier {tier_id} has invalid status")
            selected_ids = tier.get("selected_ids")
            if (
                not isinstance(selected_ids, list)
                or not selected_ids
                or not all(isinstance(value, str) and value for value in selected_ids)
                or len(set(selected_ids)) != len(selected_ids)
            ):
                raise ValueError(f"campaign report tier {tier_id} requires unique selected_ids")
            for field in ("model", "policy", "config_fingerprint", "code_fingerprint", "model_digest"):
                value = tier.get(field)
                if not isinstance(value, str) or not value:
                    raise ValueError(f"campaign report tier {tier_id} requires {field}")
            generation_options = tier.get("generation_options")
            if not isinstance(generation_options, Mapping) or not generation_options:
                raise ValueError(f"campaign report tier {tier_id} requires generation_options")
            metadata = tier.get("model_metadata")
            if not isinstance(metadata, Mapping) or metadata.get("digest") != tier["model_digest"]:
                raise ValueError(f"campaign report tier {tier_id} model metadata digest mismatch")
            sample_size = tier.get("sample_size")
            if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size != len(selected_ids):
                raise ValueError(f"campaign report tier {tier_id} sample_size mismatches selected_ids")
            counts: dict[str, int] = {}
            for field in ("n_requested", "n_evaluated", "n_failed"):
                value = tier.get(field)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f"campaign report tier {tier_id} has invalid {field}")
                counts[field] = value
            if counts["n_requested"] != len(selected_ids):
                raise ValueError(f"campaign report tier {tier_id} requested count mismatches selected_ids")
            tier_rows = row_groups[tier_id]
            if len({row.example_id for row in tier_rows}) != len(tier_rows):
                raise ValueError(f"campaign report tier {tier_id} contains duplicate example rows")
            if any(row.example_id not in selected_ids for row in tier_rows):
                raise ValueError(f"campaign report tier {tier_id} contains a row outside selected_ids")
            if any(row.model != tier["model"] or row.policy != tier["policy"] for row in tier_rows):
                raise ValueError(f"campaign report tier {tier_id} row provenance mismatches tier")
            actual_complete = sum(row.status == "complete" for row in tier_rows)
            actual_failed = sum(row.status == "failed" for row in tier_rows)
            if (actual_complete, actual_failed) != (counts["n_evaluated"], counts["n_failed"]):
                raise ValueError(f"campaign report tier {tier_id} counts mismatch rows")
            if counts["n_evaluated"] + counts["n_failed"] > counts["n_requested"]:
                raise ValueError(f"campaign report tier {tier_id} evaluates more rows than requested")
            if tier["status"] == "complete" and (
                counts["n_evaluated"] != counts["n_requested"] or counts["n_failed"] != 0
            ):
                raise ValueError(f"campaign report tier {tier_id} marked complete with incomplete accounting")
            if tier["status"] == "partial" and (
                counts["n_evaluated"] == counts["n_requested"] and counts["n_failed"] == 0
            ):
                raise ValueError(f"campaign report tier {tier_id} marked partial despite complete accounting")
        all_tiers_complete = all(tier["status"] == "complete" for tier in tiers.values())
        if status == "complete" and not all_tiers_complete:
            raise ValueError("complete campaign report requires every tier to be complete")
        if status == "partial" and all_tiers_complete:
            raise ValueError("partial campaign report cannot have every tier complete")
        benchmark = data.get("benchmark_provenance")
        if not isinstance(benchmark, Mapping) or not isinstance(benchmark.get("sha256"), str) or not benchmark.get("sha256"):
            raise ValueError("campaign report requires benchmark SHA-256 provenance")
        return cls(
            campaign_id=_required_text(data, "campaign_id"),
            status=str(status),
            benchmark_provenance=_required_mapping(data, "benchmark_provenance"),
            campaign_fingerprint=_required_text(data, "campaign_fingerprint"),
            code_fingerprint=_required_text(data, "code_fingerprint"),
            tiers=tiers,
            rows=rows,
        )

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
        temporary = target.with_name(f".{target.name}.tmp")
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return target


def run_campaign(
    spec: CampaignSpec,
    examples: Sequence[EvalExample],
    *,
    output_root: str | Path,
    model_metadata: Mapping[str, Mapping[str, object]],
    lm_factory: Callable[[str, Mapping[str, object]], LMClient] | None = None,
    base_config: HarnessConfig | None = None,
    project_root: str | Path = _PROJECT_ROOT,
    allow_scope_change: bool = False,
) -> CampaignReport:
    """Run or resume every tier, writing only isolated campaign artifacts.

    ``lm_factory`` is injectable for real deterministic integration tests using a
    ``CallableLM``; production callers use the default Ollama factory.  A tier is
    complete only when every selected row is complete.  Any failure makes the
    report partial and prevents canonical aggregate promotion.
    """
    if not examples:
        raise ValueError("examples must be non-empty")
    for tier in spec.tiers:
        metadata = model_metadata.get(tier.model)
        if (
            not isinstance(metadata, Mapping)
            or not isinstance(metadata.get("digest"), str)
            or not metadata.get("digest")
        ):
            raise ValueError(
                f"model_metadata for tier {tier.tier_id} must include a non-empty digest"
            )
    benchmark_path = Path(spec.benchmark_path)
    benchmark = file_provenance(benchmark_path)
    all_cohorts = select_nested_cohorts(
        examples,
        (tier.sample_size for tier in spec.tiers),
        selection_salt=spec.selection_salt,
    )
    root = Path(output_root) / spec.campaign_id
    root.mkdir(parents=True, exist_ok=True)
    code_digest = code_fingerprint(project_root)
    base = base_config or default_config()
    all_rows: list[CampaignRow] = []
    tier_reports: dict[str, dict[str, object]] = {}
    campaign_interrupted = False

    for tier in spec.tiers:
        cohort = all_cohorts[tier.sample_size]
        selected_ids = tuple(example.example_id for example in cohort)
        config = tier.config(base)
        config_digest = fingerprint_config(config)
        metadata = dict(model_metadata.get(tier.model, {}))
        default_checkpoint_path = root / "checkpoints" / f"{tier.tier_id}.json"
        checkpoint_path = default_checkpoint_path
        scoped_checkpoint_path = _checkpoint_scope_path(
            root,
            tier=tier,
            benchmark=benchmark,
            config_fingerprint=config_digest,
            code_digest=code_digest,
            model_metadata=metadata,
            generation_options=spec.generation_options_dict,
        )
        checkpoint_rows: dict[str, CampaignRow] = {}
        scope_match_found = False
        valid_scope_mismatch = False
        candidates = [default_checkpoint_path]
        candidates.extend(
            sorted(
                (root / "checkpoints").glob(f"{tier.tier_id}.scope-*.json"),
                key=lambda path: path.name,
            )
        )
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                checkpoint = CampaignCheckpoint.read(candidate)
                if _checkpoint_scope_matches(
                    checkpoint,
                    spec=spec,
                    tier=tier,
                    benchmark=benchmark,
                    selected_ids=selected_ids,
                    config_fingerprint=config_digest,
                    code_digest=code_digest,
                    model_metadata=metadata,
                ):
                    checkpoint_path = candidate
                    checkpoint_rows = {row.example_id: row for row in checkpoint.rows}
                    scope_match_found = True
                    break
                valid_scope_mismatch = True
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        if valid_scope_mismatch and not scope_match_found and not allow_scope_change:
            raise ValueError(
                f"existing checkpoint scope mismatch for tier {tier.tier_id}; "
                "use a new campaign_id or explicitly allow_scope_change"
            )
        if not scope_match_found and any(candidate.exists() for candidate in candidates):
            # Never overwrite a valid, corrupt, or scope-mismatched checkpoint.
            # A new scope gets an isolated file so a changed code/config/model
            # cannot destroy the evidence needed for forensic recovery.
            checkpoint_path = scoped_checkpoint_path

        lm = lm_factory(tier.model, spec.generation_options_dict) if lm_factory else _default_lm(tier.model, spec.generation_options_dict)
        config_rows: dict[str, CampaignRow] = dict(checkpoint_rows)
        consecutive_failures = 0
        tier_interrupted = False
        pause_reason: str | None = None
        with AutoHarness(config=config, lm=lm) as harness:
            for example in cohort:
                try:
                    free_bytes = shutil.disk_usage(root).free
                except OSError as exc:
                    free_bytes = 0
                    pause_reason = f"disk_usage_error:{type(exc).__name__}"
                if free_bytes < spec.min_free_bytes:
                    pause_reason = pause_reason or "unsafe_disk_pressure"
                    tier_interrupted = True
                    break
                prior = config_rows.get(example.example_id)
                if prior is not None and prior.status == "complete":
                    continue
                started = time.perf_counter()
                try:
                    output = harness.run(example)
                    row = _make_complete_row(
                        tier=tier,
                        example=example,
                        output=output,
                        latency_seconds=time.perf_counter() - started,
                    )
                    consecutive_failures = 0
                except Exception as exc:  # live model failures are accounted, never hidden
                    row = _make_failed_row(tier=tier, example=example, error=exc)
                    consecutive_failures += 1
                config_rows[example.example_id] = row
                CampaignCheckpoint(
                    campaign_id=spec.campaign_id,
                    tier_id=tier.tier_id,
                    benchmark_provenance=benchmark,
                    model=tier.model,
                    model_metadata=metadata,
                    generation_options=spec.generation_options_dict,
                    config_fingerprint=config_digest,
                    code_fingerprint=code_digest,
                    selected_ids=selected_ids,
                    rows=tuple(config_rows.values()),
                ).write(checkpoint_path)
                if consecutive_failures >= spec.max_consecutive_failures:
                    pause_reason = f"repeated_model_failures:{spec.max_consecutive_failures}"
                    tier_interrupted = True
                    break

        rows_list: list[CampaignRow] = []
        for example in cohort:
            saved_row = config_rows.get(example.example_id)
            if saved_row is not None:
                rows_list.append(saved_row)
        rows = tuple(rows_list)
        complete = sum(row.status == "complete" for row in rows)
        failed = sum(row.status == "failed" for row in rows)
        tier_status = "complete" if complete == len(cohort) else "partial"
        complete_rows = [row for row in rows if row.status == "complete"]

        def mean(field_name: str) -> float | None:
            values = [
                float(getattr(row, field_name))
                for row in complete_rows
                if getattr(row, field_name) is not None
            ]
            return sum(values) / len(values) if values else None

        def statistic(field_name: str) -> dict[str, object] | None:
            values = [
                float(getattr(row, field_name))
                for row in complete_rows
                if getattr(row, field_name) is not None
            ]
            return bootstrap_mean(
                values,
                resamples=1000,
                seed=sum(ord(char) for char in tier.tier_id) + len(values),
                confidence=0.95,
            ).to_dict() if values else None

        tier_reports[tier.tier_id] = {
            "tier_id": tier.tier_id,
            "sample_size": len(cohort),
            "n_requested": len(cohort),
            "n_evaluated": complete,
            "n_failed": failed,
            "status": tier_status,
            "model": tier.model,
            "policy": tier.policy,
            "selected_ids": list(selected_ids),
            "config_fingerprint": config_digest,
            "model_metadata": metadata,
            "model_digest": metadata.get("digest"),
            "generation_options": spec.generation_options_dict,
            "code_fingerprint": code_digest,
            "pause_reason": pause_reason,
            "metrics": {
                "accuracy": mean("accuracy"),
                "grounding_session": mean("grounding_session"),
                "composite": mean("composite"),
                "citation_precision": mean("citation_precision"),
                "source_recall": mean("source_recall"),
                "citation_token_f1": mean("citation_token_f1"),
                "latency_seconds": mean("latency_seconds"),
                "exact_accuracy_rate": (
                    sum(row.accuracy == 1.0 for row in complete_rows) / len(complete_rows)
                    if complete_rows
                    else None
                ),
                "accuracy_rate": (
                    binary_rate(
                        sum(row.accuracy == 1.0 for row in complete_rows),
                        len(complete_rows),
                    ).to_dict()
                    if complete_rows
                    else None
                ),
                "statistics": {
                    field_name: statistic(field_name)
                    for field_name in (
                        "accuracy",
                        "grounding_session",
                        "composite",
                        "citation_precision",
                        "source_recall",
                        "citation_token_f1",
                        "latency_seconds",
                    )
                },
            },
        }
        all_rows.extend(rows)
        if tier_interrupted:
            campaign_interrupted = True
            break

    # A pause can occur before a later tier starts (for example after repeated
    # model failures or unsafe disk pressure).  Preserve explicit accounting for
    # those tiers instead of silently dropping them from the report.
    if campaign_interrupted:
        started_tiers = set(tier_reports)
        for tier in spec.tiers:
            if tier.tier_id in started_tiers:
                continue
            cohort = all_cohorts[tier.sample_size]
            selected_ids = tuple(example.example_id for example in cohort)
            config_digest = fingerprint_config(tier.config(base))
            metadata = dict(model_metadata[tier.model])
            tier_reports[tier.tier_id] = {
                "tier_id": tier.tier_id,
                "sample_size": len(cohort),
                "n_requested": len(cohort),
                "n_evaluated": 0,
                "n_failed": 0,
                "status": "partial",
                "model": tier.model,
                "policy": tier.policy,
                "selected_ids": list(selected_ids),
                "config_fingerprint": config_digest,
                "model_metadata": metadata,
                "model_digest": metadata["digest"],
                "generation_options": spec.generation_options_dict,
                "code_fingerprint": code_digest,
                "pause_reason": "campaign_interrupted_before_tier",
                "metrics": {
                    field_name: None
                    for field_name in (
                        "accuracy",
                        "grounding_session",
                        "composite",
                        "citation_precision",
                        "source_recall",
                        "citation_token_f1",
                        "latency_seconds",
                    )
                },
            }

    report_status = (
        "complete"
        if not campaign_interrupted and len(tier_reports) == len(spec.tiers)
        and all(report["status"] == "complete" for report in tier_reports.values())
        else "partial"
    )
    report = CampaignReport(
        campaign_id=spec.campaign_id,
        status=report_status,
        benchmark_provenance=benchmark,
        campaign_fingerprint=spec.fingerprint(),
        code_fingerprint=code_digest,
        tiers=tier_reports,
        rows=tuple(all_rows),
    )
    report.write(root / "campaign_report.json")
    return report


def _default_lm(model: str, generation_options: Mapping[str, object]) -> LMClient:
    from ..llm import OllamaLM

    return OllamaLM(model=model, timeout=120.0, options=dict(generation_options))


def load_campaign_report(path: str | Path) -> CampaignReport:
    """Load a report and fail closed on malformed or incomplete structure."""
    source = Path(path)
    return CampaignReport.from_dict(json.loads(source.read_text(encoding="utf-8")))


def promote_campaign_report(
    source_path: str | Path,
    target_path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Promote only a complete campaign report to a new aggregate path.

    Promotion is explicit and never overwrites an existing aggregate unless the
    caller opts in.  Partial reports remain valid checkpoints but cannot become
    manuscript-facing evidence.
    """
    report = load_campaign_report(source_path)
    if (
        report.status != "complete"
        or any(tier.get("status") != "complete" for tier in report.tiers.values())
        or any(
            not tier.get("model_digest")
            or not tier.get("generation_options")
            or not tier.get("selected_ids")
            or not tier.get("config_fingerprint")
            or not tier.get("code_fingerprint")
            for tier in report.tiers.values()
        )
        or not report.benchmark_provenance.get("sha256")
    ):
        raise ValueError("only complete, fully-provenanced campaign tiers may be promoted")
    target = Path(target_path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing aggregate: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return target


__all__ = [
    "CAMPAIGN_SCHEMA_VERSION",
    "CHECKPOINT_SCHEMA_VERSION",
    "CampaignTier",
    "CampaignSpec",
    "CampaignRow",
    "CampaignCheckpoint",
    "CampaignReport",
    "select_nested_cohort",
    "select_nested_cohorts",
    "code_fingerprint",
    "load_campaign_report",
    "promote_campaign_report",
    "run_campaign",
]
