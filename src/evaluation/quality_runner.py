"""Thin live runner support for the typed model-quality protocol."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping, Sequence

from ..config import HarnessConfig, default_config
from ..harness import AutoHarness
from ..llm import OllamaLM
from ..module import LMClient
from ..signatures import HarnessOutput
from .accounting import fingerprint_config
from .longmemeval import load_longmemeval
from .quality import (
    QualityCondition,
    QualityClaim,
    QualityObservation,
    QualityProtocol,
    load_jsonl,
    parse_confidence_response,
    quality_code_fingerprint,
    write_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUALITY_ROOT = Path(
    os.environ.get("THALIA_QUALITY_ROOT", Path.home() / "thalia_external" / "quality")
)
DEFAULT_BENCHMARK = PROJECT_ROOT / "data" / "longmemeval" / "longmemeval_s.json"


@dataclass(frozen=True)
class QualityRunSummary:
    """External run summary; annotations are intentionally a later stage."""

    protocol_id: str
    phase: str
    status: str
    output_root: str
    n_requested: int
    n_evaluated: int
    n_failed: int
    annotation_template: str
    observations_path: str
    metadata_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol_id": self.protocol_id,
            "phase": self.phase,
            "status": self.status,
            "output_root": self.output_root,
            "n_requested": self.n_requested,
            "n_evaluated": self.n_evaluated,
            "n_failed": self.n_failed,
            "annotation_template": self.annotation_template,
            "observations_path": self.observations_path,
            "metadata_path": self.metadata_path,
        }


def _prompt(evidence: Sequence[str], query: str) -> str:
    joined = "\n".join(f"[{index}] {text}" for index, text in enumerate(evidence))
    return f"### EVIDENCE\n{joined}\n\n### QUESTION\n{query}\n"


def _confidence_prompt(*, query: str, answer: str, evidence: Sequence[str]) -> str:
    return (
        "Return only a JSON object with one numeric field named confidence, between 0 and 1. "
        "It is your probability that the answer is fully correct given the evidence. "
        "Do not add commentary.\n"
        f"Question: {query}\nAnswer: {answer}\nEvidence:\n{_prompt(evidence, query)}"
    )


def parse_confidence(response: str) -> float | None:
    """Parse a strict confidence response without silently inventing a value."""
    return parse_confidence_response(response)


def _complete_confidence(lm: LMClient, prompt: str) -> str:
    """Run the bounded confidence probe with a short JSON-only generation budget."""
    if isinstance(lm, OllamaLM):
        probe = OllamaLM(
            model=lm.model,
            host=lm.host,
            timeout=min(lm.timeout, 60.0),
            options={"temperature": 0.0, "num_predict": 32},
        )
        return probe.complete(prompt)
    return lm.complete(prompt)


def _safe_stem(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _extract_atomic_claims(answer: str, evidence_indices: Sequence[int]) -> tuple[QualityClaim, ...]:
    """Split an answer into auditable claim units without asking a model to segment it."""
    segments = [segment.strip() for segment in re.split(r"(?:\n+|(?<=[.!?])\s+)", answer) if segment.strip()]
    return tuple(
        QualityClaim(claim_id=f"claim-{index:04d}", claim_text=segment, evidence_indices=tuple(evidence_indices))
        for index, segment in enumerate(segments)
    )


def _observation_from_output(
    *,
    protocol: QualityProtocol,
    phase: str,
    condition: QualityCondition,
    example,
    output: HarnessOutput | None,
    answer: str | None,
    evidence_indices: Sequence[int],
    citations: Sequence[tuple[int, str]],
    evidence_text: Sequence[str],
    confidence: float | None,
    confidence_response: str = "",
    latency_seconds: float,
    model_digest: str,
    config_digest: str,
    code_digest: str,
    raw_path: str,
    error: BaseException | None = None,
) -> QualityObservation:
    if error is not None:
        return QualityObservation(
            observation_id=f"{phase}:{condition.condition_id}:{example.example_id}",
            protocol_id=protocol.protocol_id,
            phase=phase,
            condition_id=condition.condition_id,
            question_id=example.example_id,
            model=condition.model,
            mode=condition.mode,
            status="failed",
            stratum=example.stratum,
            latency_seconds=latency_seconds,
            model_digest=model_digest,
            config_fingerprint=config_digest,
            code_fingerprint=code_digest,
            generation_options=tuple(sorted(protocol.generation_options.items())),
            raw_path=raw_path,
            error_class=type(error).__name__,
            error_message=str(error),
        )
    if answer is None:
        raise ValueError("a successful quality observation requires an answer")
    answer_text = answer
    return QualityObservation(
        observation_id=f"{phase}:{condition.condition_id}:{example.example_id}",
        protocol_id=protocol.protocol_id,
        phase=phase,
        condition_id=condition.condition_id,
        question_id=example.example_id,
        model=condition.model,
        mode=condition.mode,
        status="complete",
        stratum=example.stratum,
        answer=answer_text,
        citation_indices=tuple(index for index, _ in citations),
        citations=tuple(citations),
        evidence_indices=tuple(evidence_indices),
        claims=_extract_atomic_claims(answer_text, evidence_indices),
        confidence=confidence,
        confidence_response=confidence_response,
        latency_seconds=latency_seconds,
        answer_sha256=hashlib.sha256(answer_text.encode("utf-8")).hexdigest(),
        model_digest=model_digest,
        config_fingerprint=config_digest,
        code_fingerprint=code_digest,
        generation_options=tuple(sorted(protocol.generation_options.items())),
        raw_path=raw_path,
    )


def _run_one(
    *,
    condition: QualityCondition,
    example,
    protocol: QualityProtocol,
    phase: str,
    lm: LMClient,
    base_config: HarnessConfig,
    model_digest: str,
    code_digest: str,
    raw_path: str,
) -> QualityObservation:
    config = base_config.with_(**dict(condition.config_overrides))
    config_digest = fingerprint_config(config)
    started = time.perf_counter()
    answer: str | None = None
    output: HarnessOutput | None = None
    evidence_indices: tuple[int, ...] = ()
    citations: tuple[tuple[int, str], ...] = ()
    evidence_text: tuple[str, ...] = ()
    confidence_response = ""
    try:
        if condition.mode == "harness":
            with AutoHarness(config=config, lm=lm) as harness:
                output = harness.run(example)
            answer = output.answer
            evidence_indices = tuple(item.window.source_index for item in output.ranked_evidence)
            citations = tuple((item.source_index, item.excerpt) for item in output.evidence_citations)
            evidence_text = tuple(item.window.text for item in output.ranked_evidence)
        elif condition.mode == "no_harness":
            answer = lm.complete(_prompt(example.session_history.splitlines(), example.query))
            evidence_text = tuple(example.session_history.splitlines())
        elif condition.mode == "oracle_evidence":
            lines = tuple(example.session_history.splitlines())
            evidence_indices = tuple(example.expected_source_indices)
            evidence_text = tuple(lines[index] for index in evidence_indices if index < len(lines))
            answer = lm.complete(_prompt(evidence_text, example.query))
        else:  # pragma: no cover - QualityCondition validates the closed set.
            raise ValueError(f"unsupported quality mode {condition.mode}")
        confidence_response = _complete_confidence(
            lm,
            _confidence_prompt(query=example.query, answer=answer, evidence=evidence_text),
        )
        confidence = parse_confidence(confidence_response)
        return _observation_from_output(
            protocol=protocol,
            phase=phase,
            condition=condition,
            example=example,
            output=output,
            answer=answer,
            evidence_indices=evidence_indices,
            citations=citations,
            evidence_text=evidence_text,
            confidence=confidence,
            confidence_response=confidence_response,
            latency_seconds=time.perf_counter() - started,
            model_digest=model_digest,
            config_digest=config_digest,
            code_digest=code_digest,
            raw_path=raw_path,
        )
    except Exception as exc:  # live failures become explicit quality rows.
        return _observation_from_output(
            protocol=protocol,
            phase=phase,
            condition=condition,
            example=example,
            output=None,
            answer=None,
            evidence_indices=(),
            citations=(),
            evidence_text=(),
            confidence=None,
            confidence_response="",
            latency_seconds=time.perf_counter() - started,
            model_digest=model_digest,
            config_digest=config_digest,
            code_digest=code_digest,
            raw_path=raw_path,
            error=exc,
        )


def _default_lm_factory(model: str, generation_options: Mapping[str, object]) -> LMClient:
    return OllamaLM(model=model, timeout=120.0, options=dict(generation_options))


def create_annotation_template(
    observations: Sequence[QualityObservation],
    examples: Sequence,
    path: str | Path,
    *,
    blinding_seed: str = "thalia-quality-blind-v2",
) -> Path:
    """Write randomized, condition-neutral packets for evaluator annotation.

    Judges receive the same question/context schema for every condition.  Model
    citations and source indices remain in the analyst ledger; exposing an empty
    versus non-empty citation list would identify the baseline condition.
    """
    by_id = {example.example_id: example for example in examples}
    rows = []
    complete_observations = [observation for observation in observations if observation.status == "complete"]
    ordered_observations = sorted(
        complete_observations,
        key=lambda row: (_safe_stem(f"{blinding_seed}:{row.presentation_id}"), row.presentation_id),
    )
    for observation in ordered_observations:
        if observation.status != "complete":
            continue
        example = by_id[observation.question_id]
        evidence_packet = [
            {"source_id": f"line-{index:04d}", "text": line}
            for index, line in enumerate(example.session_history.splitlines())
        ]
        claims = [{"claim_id": claim.claim_id, "claim_text": claim.claim_text} for claim in observation.claims]
        packet = {
            "packet_id": observation.presentation_id,
            "question": example.query,
            "session_history": example.session_history,
            "evidence_packet": evidence_packet,
            "answer": observation.answer,
            "claims": claims,
            "annotation_note": "Model and condition are withheld. Judge against the supplied question and source material.",
        }
        packet["packet_digest"] = hashlib.sha256(
            json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        rows.append(
            packet
        )
    return write_jsonl(path, rows)


def run_quality_campaign(
    protocol: QualityProtocol,
    examples: Sequence,
    *,
    phase: str,
    output_root: str | Path,
    model_metadata: Mapping[str, Mapping[str, object]],
    lm_factory: Callable[[str, Mapping[str, object]], LMClient] | None = None,
    base_config: HarnessConfig | None = None,
    project_root: str | Path = PROJECT_ROOT,
) -> QualityRunSummary:
    """Run one pilot/confirmatory phase and emit external raw evidence."""
    if phase not in {"pilot", "confirmatory"}:
        raise ValueError("phase must be pilot or confirmatory")
    if phase == "confirmatory" and not protocol.frozen:
        raise ValueError("confirmatory quality run requires a frozen protocol")
    if phase == "confirmatory":
        from .quality import _validate_pilot_review_binding

        pilot_review_issue = _validate_pilot_review_binding(protocol)
        if pilot_review_issue is not None:
            raise ValueError(f"confirmatory quality run pilot review binding failed: {pilot_review_issue}")
    examples_by_id = {example.example_id: example for example in examples}
    selected_ids = protocol.pilot_ids if phase == "pilot" else protocol.confirmatory_ids
    if any(question_id not in examples_by_id for question_id in selected_ids):
        raise ValueError("protocol selected IDs are not present in benchmark examples")
    root = Path(output_root) / protocol.protocol_id / phase
    root.mkdir(parents=True, exist_ok=True)
    protocol.write(root.parent / "protocol.json")
    code_digest = quality_code_fingerprint(project_root)
    config = base_config or default_config()
    factory = lm_factory or _default_lm_factory
    existing_path = root / "observations.jsonl"
    progress_path = root / "progress.json"
    existing: dict[str, QualityObservation] = {}
    if existing_path.exists():
        for row in load_jsonl(existing_path, QualityObservation.from_dict):
            existing[row.observation_id] = row
    observations: list[QualityObservation] = []
    metadata_by_model: dict[str, Mapping[str, object]] = {}
    for condition in protocol.conditions:
        metadata = model_metadata.get(condition.model)
        if not isinstance(metadata, Mapping) or not isinstance(metadata.get("digest"), str) or not metadata.get("digest"):
            raise ValueError(f"model metadata for {condition.model} requires a digest")
        metadata_by_model[condition.model] = metadata
    config_fingerprints = {
        condition.condition_id: fingerprint_config(config.with_(**dict(condition.config_overrides)))
        for condition in protocol.conditions
    }
    expected_generation_options = tuple(sorted(protocol.generation_options.items()))
    metadata_path = root / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "protocol_id": protocol.protocol_id,
                "phase": phase,
                "benchmark_provenance": dict(protocol.benchmark_provenance),
                "generation_options": dict(protocol.generation_options),
                "code_fingerprint": code_digest,
                "conditions": [condition.to_dict() for condition in protocol.conditions],
                "config_fingerprints": config_fingerprints,
                "models": {model: dict(metadata) for model, metadata in metadata_by_model.items()},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for condition in protocol.conditions:
        lm = factory(condition.model, protocol.generation_options)
        model_digest = str(metadata_by_model[condition.model]["digest"])
        for question_id in selected_ids:
            example = examples_by_id[question_id]
            observation_id = f"{phase}:{condition.condition_id}:{question_id}"
            prior = existing.get(observation_id)
            if prior is not None:
                expected_raw_path = f"raw/{condition.condition_id}/{_safe_stem(question_id)}.json"
                provenance_mismatches = []
                if prior.phase != phase or prior.question_id != question_id:
                    provenance_mismatches.append("question_scope")
                if prior.model != condition.model or prior.mode != condition.mode:
                    provenance_mismatches.append("condition")
                if prior.model_digest != model_digest:
                    provenance_mismatches.append("model_digest")
                if prior.config_fingerprint != config_fingerprints[condition.condition_id]:
                    provenance_mismatches.append("config_fingerprint")
                if prior.code_fingerprint != code_digest:
                    provenance_mismatches.append("code_fingerprint")
                if prior.generation_options != expected_generation_options:
                    provenance_mismatches.append("generation_options")
                if prior.raw_path != expected_raw_path or not (root / prior.raw_path).is_file():
                    provenance_mismatches.append("raw_path")
                if prior.raw_sha256 is None:
                    provenance_mismatches.append("raw_digest")
                elif (root / prior.raw_path).is_file():
                    observed_raw_digest = hashlib.sha256((root / prior.raw_path).read_bytes()).hexdigest()
                    if observed_raw_digest != prior.raw_sha256:
                        provenance_mismatches.append("raw_content_digest")
                if provenance_mismatches:
                    raise ValueError(
                        "existing observation provenance mismatch for "
                        f"{observation_id}: {', '.join(provenance_mismatches)}"
                    )
                observations.append(prior)
                continue
            raw_path = f"raw/{condition.condition_id}/{_safe_stem(question_id)}.json"
            observation = _run_one(
                condition=condition,
                example=example,
                protocol=protocol,
                phase=phase,
                lm=lm,
                base_config=config,
                model_digest=model_digest,
                code_digest=code_digest,
                raw_path=raw_path,
            )
            raw_file = root / raw_path
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            raw_text = json.dumps(
                {
                    "question_id": question_id,
                    "question": example.query,
                    "session_history": example.session_history,
                    "observation": observation.to_dict(include_raw_digest=False),
                },
                indent=2,
                sort_keys=True,
            ) + "\n"
            raw_file.write_text(raw_text, encoding="utf-8")
            observation = replace(observation, raw_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest())
            observations.append(observation)
            write_jsonl(existing_path, (row.to_dict() for row in observations))
            progress_path.write_text(
                json.dumps(
                    {
                        "protocol_id": protocol.protocol_id,
                        "phase": phase,
                        "last_observation_id": observation.observation_id,
                        "n_requested": len(selected_ids) * len(protocol.conditions),
                        "n_evaluated": sum(row.status == "complete" for row in observations),
                        "n_failed": sum(row.status == "failed" for row in observations),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            print(
                f"[quality] {phase} {len(observations)}/{len(selected_ids) * len(protocol.conditions)} "
                f"{condition.condition_id} {question_id} status={observation.status}",
                flush=True,
            )
    write_jsonl(existing_path, (observation.to_dict() for observation in observations))
    template = create_annotation_template(observations, examples, root / "annotation_template.jsonl")
    summary = QualityRunSummary(
        protocol_id=protocol.protocol_id,
        phase=phase,
        status="pending_annotation",
        output_root=str(root),
        n_requested=len(selected_ids) * len(protocol.conditions),
        n_evaluated=sum(observation.status == "complete" for observation in observations),
        n_failed=sum(observation.status == "failed" for observation in observations),
        annotation_template=str(template),
        observations_path=str(existing_path),
        metadata_path=str(metadata_path),
    )
    (root / "run_summary.json").write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def load_benchmark(path: str | Path = DEFAULT_BENCHMARK):
    """Load the validated LongMemEval benchmark for the CLI."""
    return load_longmemeval(path)


__all__ = [
    "DEFAULT_BENCHMARK",
    "DEFAULT_QUALITY_ROOT",
    "QualityRunSummary",
    "create_annotation_template",
    "load_benchmark",
    "parse_confidence",
    "run_quality_campaign",
]
