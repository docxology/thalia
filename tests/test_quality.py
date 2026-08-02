"""Zero-mock tests for the typed model-quality evidence lane."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from src.compiler.metrics import EvalExample
from src.evaluation.quality import (
    QualityAdjudication,
    QualityAnnotation,
    QualityClaim,
    QualityClaimAdjudication,
    QualityClaimAnnotation,
    QualityCondition,
    QualityObservation,
    QualityProtocol,
    QualityReport,
    _pilot_review_structural_issue,
    _bool,
    _integer,
    _metric_mean,
    _percentile,
    _raw_evidence_manifest,
    _validate_pilot_review_binding,
    _validate_benchmark_file,
    _validate_external_provenance_paths,
    _evaluate_thresholds,
    build_quality_report,
    brier_score,
    default_quality_conditions,
    expected_calibration_error,
    promote_quality_report,
    parse_confidence_response,
    quality_code_fingerprint,
    reliability_curve,
    selective_accuracy,
    weighted_cohen_kappa,
    write_jsonl,
)
from src.evaluation.quality_runner import create_annotation_template, load_jsonl, parse_confidence, run_quality_campaign
from src.llm import CallableLM
from src.module import ExtractiveLM


def _examples() -> list[EvalExample]:
    rows: list[EvalExample] = []
    for index, stratum in enumerate(("a", "b", "c")):
        for offset in range(2):
            question_id = f"q-{stratum}-{offset}"
            rows.append(
                EvalExample(
                    session_history=f"User: fact {question_id} is value {offset}.",
                    query=f"What is fact {question_id}?",
                    expected_answer=f"fact {question_id} is value {offset}",
                    expected_source_indices=(0,),
                    example_id=question_id,
                    stratum=stratum,
                )
            )
    return rows


def _protocol(tmp_path: Path) -> QualityProtocol:
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text("[]\n", encoding="utf-8")
    conditions = (
        QualityCondition("model-harness", "model", "harness"),
        QualityCondition("model-no-harness", "model", "no_harness", policy="full_context"),
    )
    protocol = QualityProtocol.from_examples(
        protocol_id="quality-test",
        benchmark_path=benchmark,
        examples=_examples(),
        conditions=conditions,
        pilot_per_stratum=1,
    )
    return replace(protocol, pilot_review_provenance=_pilot_review_provenance(protocol, tmp_path))


def _observation(protocol: QualityProtocol, phase: str, condition_id: str, question_id: str, index: int) -> QualityObservation:
    answer = f"answer {question_id}"
    confidence = 0.9 if index % 2 == 0 else 0.2
    return QualityObservation(
        observation_id=f"{phase}:{condition_id}:{question_id}",
        protocol_id=protocol.protocol_id,
        phase=phase,
        condition_id=condition_id,
        question_id=question_id,
        model="model",
        mode="no_harness" if condition_id.endswith("no-harness") else "harness",
        status="complete",
        answer=answer,
        citation_indices=(0,),
        citations=((0, answer),),
        evidence_indices=(0,),
        claims=(QualityClaim("claim-0000", answer, (0,)),),
        confidence=confidence,
        confidence_response=json.dumps({"confidence": confidence}),
        latency_seconds=0.1,
        answer_sha256=hashlib.sha256(answer.encode()).hexdigest(),
        model_digest="model-digest",
        config_fingerprint="config-digest",
        code_fingerprint="code-digest",
        generation_options=(("num_predict", 512), ("temperature", 0.0)),
        raw_path=f"raw/{phase}/{condition_id}/{question_id}.json",
    )


def _materialize_raw(observations: list[QualityObservation], root: Path) -> list[QualityObservation]:
    materialized: list[QualityObservation] = []
    for observation in observations:
        raw_text = json.dumps(
            {
                "question_id": observation.question_id,
                "question": observation.question_id,
                "session_history": "history",
                "observation": observation.to_dict(include_raw_digest=False),
            },
            indent=2,
            sort_keys=True,
        ) + "\n"
        target = root / observation.raw_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(raw_text, encoding="utf-8")
        materialized.append(replace(observation, raw_sha256=hashlib.sha256(raw_text.encode()).hexdigest()))
    return materialized


def _labels(observations: list[QualityObservation], rubric: str = "frozen-v1") -> tuple[list[QualityAnnotation], list[QualityAdjudication]]:
    annotations: list[QualityAnnotation] = []
    adjudications: list[QualityAdjudication] = []
    for observation in observations:
        for judge in ("judge-a", "judge-b"):
            annotations.append(
                QualityAnnotation(
                    presentation_id=observation.presentation_id,
                    judge_id=judge,
                    rubric_version=rubric,
                    correctness=2,
                    completeness=2,
                    faithfulness=2,
                    usefulness=2,
                    abstention_appropriate=True,
                    critical_safety_failure=False,
                    claim_labels=(QualityClaimAnnotation(observation.presentation_id, judge, "claim-0000", "supported"),),
                )
            )
        adjudications.append(
            QualityAdjudication(
                presentation_id=observation.presentation_id,
                rubric_version=rubric,
                resolved_by="adjudicator",
                correctness=2,
                completeness=2,
                faithfulness=2,
                usefulness=2,
                abstention_appropriate=True,
                critical_safety_failure=False,
                claim_adjudications=(QualityClaimAdjudication(observation.presentation_id, "claim-0000", "adjudicator", "supported"),),
            )
        )
    return annotations, adjudications


def _pilot_review_provenance(protocol: QualityProtocol, tmp_path: Path) -> dict[str, object]:
    """Create a real pilot certificate so frozen-protocol tests exercise binding."""
    observations = [
        _observation(protocol, "pilot", condition_id, question_id, index)
        for index, question_id in enumerate(protocol.pilot_ids)
        for condition_id in ("model-harness", "model-no-harness")
    ]
    evidence_root = tmp_path / "pilot-evidence"
    observations = _materialize_raw(observations, evidence_root)
    annotations, adjudications = _labels(observations, rubric="draft-v1")
    report = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase="pilot",
        evidence_root=evidence_root,
    )
    report_path = tmp_path / "pilot-report.json"
    payload = report.to_dict()
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw = report_path.read_bytes()
    manifest = payload["evidence_manifest"]
    assert isinstance(manifest, dict)
    return {
        "report": {
            "path": str(report_path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "certificate_sha256": payload["certificate_sha256"],
        },
        "protocol_sha256": manifest["protocol_sha256"],
        "status": report.status,
        "n_observations": report.n_observations,
        "n_annotations": report.n_annotations,
        "n_adjudications": report.n_adjudications,
    }


def test_protocol_partition_is_deterministic_and_disjoint(tmp_path):
    first = _protocol(tmp_path)
    second = _protocol(tmp_path)
    assert first.pilot_ids == second.pilot_ids
    assert first.confirmatory_ids == second.confirmatory_ids
    assert set(first.pilot_ids).isdisjoint(first.confirmatory_ids)
    assert len(first.pilot_ids) == 3
    assert len(first.confirmatory_ids) == 3


def test_protocol_roundtrip_freeze_and_schema_fail_closed(tmp_path):
    protocol = _protocol(tmp_path)
    restored = QualityProtocol.from_dict(protocol.to_dict())
    assert restored == protocol
    assert len(quality_code_fingerprint(Path(__file__).resolve().parents[1])) == 64
    with pytest.raises(ValueError, match="ordinal_scale"):
        replace(protocol, rubric={**protocol.rubric, "ordinal_scale": {"0": "only one level"}})
    with pytest.raises(ValueError, match="protocol version"):
        QualityProtocol.from_dict({**protocol.to_dict(), "protocol_version": "unsupported-protocol-version"})
    with pytest.raises(ValueError, match="conditions must contain mappings"):
        QualityProtocol.from_dict({**protocol.to_dict(), "conditions": [None]})
    with pytest.raises(ValueError, match="thresholds"):
        protocol.freeze(
            rubric_version="frozen-v1",
            primary_metric="correctness_full_rate",
            thresholds={},
            pilot_review_provenance={"report_sha256": "pilot"},
        )
    with pytest.raises(ValueError, match="pilot review"):
        protocol.freeze(
            rubric_version="frozen-v1",
            primary_metric="correctness_full_rate",
            thresholds={"correctness_lower_bound": 0.0, "critical_safety_failure_rate_upper_bound": 0.0},
            pilot_review_provenance={},
        )
    with pytest.raises(ValueError, match="critical_safety_failure_rate_upper_bound"):
        protocol.freeze(
            rubric_version="frozen-v1",
            primary_metric="correctness_full_rate",
            thresholds={"correctness_lower_bound": 0.0},
            pilot_review_provenance={"report_sha256": "pilot"},
        )


def test_default_matrix_contains_two_models_and_three_modes():
    conditions = default_quality_conditions()
    assert len(conditions) == 6
    assert {condition.mode for condition in conditions} == {"harness", "no_harness", "oracle_evidence"}
    assert {condition.model for condition in conditions} == {"gemma3:4b", "hermes3:latest"}


def test_annotation_scores_and_blinding_are_strict(tmp_path):
    protocol = _protocol(tmp_path)
    observation = _observation(protocol, "pilot", "model-harness", protocol.pilot_ids[0], 0)
    assert len(observation.presentation_id) == 24
    annotation = QualityAnnotation(
        presentation_id=observation.presentation_id,
        judge_id="judge",
        rubric_version="draft-v1",
        correctness=2,
        completeness=2,
        faithfulness=2,
        usefulness=2,
        abstention_appropriate=True,
        critical_safety_failure=False,
        failure_modes=("none",),
    )
    assert QualityAnnotation.from_dict(annotation.to_dict()) == annotation
    with pytest.raises(ValueError, match="unique"):
        replace(annotation, failure_modes=("same", "same"))
    with pytest.raises(ValueError, match="score"):
        QualityAnnotation(
            presentation_id=observation.presentation_id,
            judge_id="judge",
            rubric_version="draft-v1",
            correctness=3,
            completeness=2,
            faithfulness=2,
            usefulness=2,
            abstention_appropriate=True,
            critical_safety_failure=False,
        )
    with pytest.raises(ValueError, match="unique claim IDs"):
        replace(
            observation,
            claims=(QualityClaim("duplicate", "one"), QualityClaim("duplicate", "two")),
        )


def test_quality_report_requires_two_judges_and_adjudication(tmp_path):
    draft = _protocol(tmp_path)
    protocol = draft.freeze(
        rubric_version="frozen-v1",
        primary_metric="correctness_full_rate",
        thresholds={
            "correctness_lower_bound": 0.0,
            "critical_safety_failure_rate_upper_bound": 0.0,
            "faithfulness_mean": 0.5,
        },
        pilot_review_provenance=draft.pilot_review_provenance,
    )
    observations = [
        _observation(protocol, "confirmatory", condition_id, question_id, index)
        for index, question_id in enumerate(protocol.confirmatory_ids)
        for condition_id in ("model-harness", "model-no-harness")
    ]
    evidence_root = tmp_path / "quality-evidence"
    observations = _materialize_raw(observations, evidence_root)
    annotations, adjudications = _labels(observations)
    report = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase="confirmatory",
        provenance={"code_fingerprint": "test"},
        evidence_root=evidence_root,
    )
    assert report.status == "passed"
    assert report.n_observations == 6
    assert report.agreement["correctness"] == 1.0
    assert report.threshold_results == {
        "correctness_lower_bound": True,
        "critical_safety_failure_rate_upper_bound": True,
        "faithfulness_mean": True,
    }
    assert report.metrics["n_primary_questions"] == 3
    assert report.comparisons["model-no-harness_vs_model-harness"]["clustered_delta"]["cluster_count"] == 3
    harness_metrics = report.metrics["conditions"]["model-harness"]
    assert harness_metrics["difficult_case_rate"] == 0.0
    assert len(harness_metrics["reliability_curve"]) == 10
    assert len(harness_metrics["selective_accuracy"]) == 4

    disagreement_annotations = list(annotations)
    disagreement_annotations[0] = replace(
        disagreement_annotations[0],
        correctness=1,
        abstention_appropriate=False,
        failure_modes=("incomplete",),
    )
    disagreement_report = build_quality_report(
        protocol,
        observations,
        disagreement_annotations,
        adjudications,
        phase="confirmatory",
        evidence_root=evidence_root,
    )
    assert disagreement_report.agreement["correctness_disagreement"]["n"] == 1
    assert disagreement_report.agreement["abstention_disagreement"]["n"] == 1
    assert disagreement_report.agreement["failure_mode_counts"] == {"incomplete": 1}

    incomplete = build_quality_report(protocol, observations, annotations[:-1], adjudications, phase="confirmatory", evidence_root=evidence_root)
    assert incomplete.status == "failed"
    assert any("missing_two_judge_labels" in issue for issue in incomplete.issues)


def test_report_roundtrip_and_promotion_is_fail_closed(tmp_path):
    draft = _protocol(tmp_path)
    protocol = draft.freeze(
        rubric_version="frozen-v1",
        primary_metric="correctness_full_rate",
        thresholds={"correctness_lower_bound": 0.0, "critical_safety_failure_rate_upper_bound": 0.0},
        pilot_review_provenance=draft.pilot_review_provenance,
    )
    observations = [
        _observation(protocol, "confirmatory", condition_id, question_id, index)
        for index, question_id in enumerate(protocol.confirmatory_ids)
        for condition_id in ("model-harness", "model-no-harness")
    ]
    evidence_root = tmp_path / "quality-evidence"
    observations = _materialize_raw(observations, evidence_root)
    annotations, adjudications = _labels(observations)
    protocol_path = tmp_path / "protocol.json"
    observations_path = tmp_path / "observations.jsonl"
    annotations_path = tmp_path / "annotations.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    protocol.write(protocol_path)
    write_jsonl(observations_path, (row.to_dict() for row in observations))
    write_jsonl(annotations_path, (row.to_dict() for row in annotations))
    write_jsonl(adjudications_path, (row.to_dict() for row in adjudications))
    report = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase="confirmatory",
        provenance={
            "protocol_path": str(protocol_path),
            "observations_path": str(observations_path),
            "annotations_path": str(annotations_path),
            "adjudications_path": str(adjudications_path),
        },
        evidence_root=evidence_root,
    )
    source = tmp_path / "quality_report.json"
    target = tmp_path / "quality_results.json"
    report.write(source)
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps({
            "accepted": True,
            "accepted_by": "test-reviewer",
            "report_certificate_sha256": json.loads(source.read_text(encoding="utf-8"))["certificate_sha256"],
        }),
        encoding="utf-8",
    )
    raw_file = evidence_root / observations[0].raw_path
    raw_original = raw_file.read_text(encoding="utf-8")
    raw_file.write_text(raw_original.replace("\"question\"", "\"tampered_question\"", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="raw evidence digest"):
        promote_quality_report(source, tmp_path / "tampered-raw-results.json", acceptance_path=acceptance)
    raw_file.write_text(raw_original, encoding="utf-8")
    assert promote_quality_report(source, target, acceptance_path=acceptance) == target
    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "passed"
    with pytest.raises(FileExistsError):
        promote_quality_report(source, target, acceptance_path=acceptance)

    llm_manifest = dict(report.evidence_manifest)
    llm_manifest["evaluation_mode"] = "llm_judge"
    llm_report = replace(report, evidence_manifest=llm_manifest)
    llm_source = tmp_path / "llm-judge-report.json"
    llm_report.write(llm_source)
    llm_acceptance = tmp_path / "llm-judge-acceptance.json"
    llm_acceptance.write_text(
        json.dumps(
            {
                "accepted": True,
                "accepted_by": "test-reviewer",
                "report_certificate_sha256": llm_report.to_dict()["certificate_sha256"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expert-human annotations"):
        promote_quality_report(
            llm_source,
            tmp_path / "llm-judge-results.json",
            acceptance_path=llm_acceptance,
        )

    tampered = json.loads(source.read_text(encoding="utf-8"))
    tampered["metrics"]["tampered"] = True
    tampered_source = tmp_path / "tampered.json"
    tampered_source.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="certificate digest"):
        promote_quality_report(tampered_source, tmp_path / "tampered-results.json", acceptance_path=acceptance)

    pending = build_quality_report(_protocol(tmp_path), observations, annotations, adjudications, phase="confirmatory", evidence_root=evidence_root)
    pending.write(tmp_path / "pending.json")
    assert pending.status == "failed"
    with pytest.raises(ValueError, match="passed quality certificate"):
        promote_quality_report(tmp_path / "pending.json", tmp_path / "never.json")

    unfrozen = _protocol(tmp_path)
    unfrozen_observations = [
        _observation(unfrozen, "confirmatory", condition_id, question_id, index)
        for index, question_id in enumerate(unfrozen.confirmatory_ids)
        for condition_id in ("model-harness", "model-no-harness")
    ]
    unfrozen_annotations, unfrozen_adjudications = _labels(unfrozen_observations, rubric="draft-v1")
    unfrozen_observations = _materialize_raw(unfrozen_observations, evidence_root)
    unfrozen_report = build_quality_report(
        unfrozen,
        unfrozen_observations,
        unfrozen_annotations,
        unfrozen_adjudications,
        phase="confirmatory",
        evidence_root=evidence_root,
    )
    assert unfrozen_report.status == "failed"
    assert "thresholds_not_frozen" in unfrozen_report.issues


def test_quality_report_rejects_duplicate_judges_failed_rows_and_bad_provenance(tmp_path):
    draft = _protocol(tmp_path)
    protocol = draft.freeze(
        rubric_version="frozen-v1",
        primary_metric="correctness_full_rate",
        thresholds={"correctness_lower_bound": 0.0, "critical_safety_failure_rate_upper_bound": 0.0},
        pilot_review_provenance=draft.pilot_review_provenance,
    )
    observations = [
        _observation(protocol, "confirmatory", condition_id, question_id, index)
        for index, question_id in enumerate(protocol.confirmatory_ids)
        for condition_id in ("model-harness", "model-no-harness")
    ]
    evidence_root = tmp_path / "quality-evidence"
    observations = _materialize_raw(observations, evidence_root)
    annotations, adjudications = _labels(observations)
    duplicate = build_quality_report(
        protocol,
        observations,
        annotations + [annotations[0]],
        adjudications,
        phase="confirmatory",
        evidence_root=evidence_root,
    )
    assert duplicate.status == "failed"
    assert any("duplicate_judge_labels" in issue for issue in duplicate.issues)

    mismatched_digest = build_quality_report(
        protocol,
        [replace(observations[0], model_digest="sha256:other")] + observations[1:],
        annotations,
        adjudications,
        phase="confirmatory",
        evidence_root=evidence_root,
    )
    assert mismatched_digest.status == "failed"
    assert any("condition_model_digest_mismatch" in issue for issue in mismatched_digest.issues)

    failed = build_quality_report(
        protocol,
        [replace(observations[0], status="failed", error_class="RuntimeError")] + observations[1:],
        annotations,
        adjudications,
        phase="confirmatory",
        evidence_root=evidence_root,
    )
    assert failed.status == "failed"
    assert "failed_observations_present" in failed.issues

    with pytest.raises(ValueError, match="raw_path"):
        QualityObservation(
            observation_id="bad",
            protocol_id=protocol.protocol_id,
            phase="confirmatory",
            condition_id="model-harness",
            question_id=protocol.confirmatory_ids[0],
            model="model",
            mode="harness",
            status="complete",
        )
    with pytest.raises(ValueError, match="relative path"):
        replace(observations[0], raw_path="../outside.json")


def test_calibration_and_weighted_agreement_are_deterministic():
    assert brier_score((0.9, 0.1), (True, False)) == pytest.approx(0.01)
    assert expected_calibration_error((0.9, 0.1), (True, False), bins=2) == pytest.approx(0.1)
    curve = reliability_curve((0.9, 0.1), (True, False), bins=2)
    assert curve[0]["n"] == 1
    assert curve[1]["accuracy"] == 1.0
    selective = selective_accuracy((0.9, 0.1), (True, False), coverage_levels=(0.5, 1.0))
    assert selective[0]["accuracy"] == 1.0
    assert selective[1]["accuracy"] == 0.5
    assert weighted_cohen_kappa((0, 1, 2), (0, 1, 2)) == 1.0
    assert weighted_cohen_kappa((0, 1, 2), (2, 1, 0)) < 0.0


def test_quality_red_team_rejects_unbound_raw_evidence_and_invalid_confidence(tmp_path):
    draft = _protocol(tmp_path)
    protocol = draft.freeze(
        rubric_version="frozen-v1",
        primary_metric="correctness_full_rate",
        thresholds={"correctness_lower_bound": 0.0, "critical_safety_failure_rate_upper_bound": 0.0},
        pilot_review_provenance=draft.pilot_review_provenance,
    )
    observations = [
        _observation(protocol, "confirmatory", condition_id, question_id, index)
        for index, question_id in enumerate(protocol.confirmatory_ids)
        for condition_id in ("model-harness", "model-no-harness")
    ]
    evidence_root = tmp_path / "evidence"
    observations = _materialize_raw(observations, evidence_root)
    annotations, adjudications = _labels(observations)
    unbound = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase="confirmatory",
        evidence_root=tmp_path / "missing-evidence",
    )
    assert unbound.status == "failed"
    assert "raw_evidence_root_missing" in unbound.issues

    tampered_raw = next((evidence_root / row.raw_path for row in observations))
    original_raw = tampered_raw.read_text(encoding="utf-8")
    tampered_payload = json.loads(original_raw)
    tampered_payload["question"] = "tampered question"
    tampered_raw.write_text(json.dumps(tampered_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tampered_report = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase="confirmatory",
        evidence_root=evidence_root,
    )
    assert tampered_report.status == "failed"
    assert any("raw_digest_mismatch" in issue for issue in tampered_report.issues)
    tampered_raw.write_text(original_raw, encoding="utf-8")

    with pytest.raises(ValueError, match="confidence_response"):
        replace(observations[0], confidence_response="not parseable")

    below_threshold = draft.freeze(
        rubric_version="frozen-v2",
        primary_metric="correctness_full_rate",
        thresholds={"correctness_lower_bound": 1.0, "critical_safety_failure_rate_upper_bound": 0.0},
        pilot_review_provenance=draft.pilot_review_provenance,
    )
    below = build_quality_report(
        below_threshold,
        [replace(row, protocol_id=below_threshold.protocol_id) for row in observations],
        [replace(annotation, rubric_version="frozen-v2") for annotation in annotations],
        [replace(adjudication, rubric_version="frozen-v2") for adjudication in adjudications],
        phase="confirmatory",
        evidence_root=evidence_root,
    )
    assert below.status == "complete_not_promoted"
    assert below.threshold_results["correctness_lower_bound"] is False

    other_protocol_path = tmp_path / "other-protocol.json"
    replace(protocol, protocol_id="different-protocol").write(other_protocol_path)
    source_bound_report = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase="confirmatory",
        provenance={"protocol_path": str(other_protocol_path)},
        evidence_root=evidence_root,
    )
    assert source_bound_report.status == "failed"
    assert "protocol_source_binding_mismatch" in source_bound_report.issues


def test_confirmatory_runner_refuses_tampered_pilot_certificate(tmp_path):
    draft = _protocol(tmp_path)
    frozen = draft.freeze(
        rubric_version="frozen-v1",
        primary_metric="correctness_full_rate",
        thresholds={"correctness_lower_bound": 0.0, "critical_safety_failure_rate_upper_bound": 0.0},
        pilot_review_provenance=draft.pilot_review_provenance,
    )
    pilot_path = Path(str(frozen.pilot_review_provenance["report"]["path"]))
    original = pilot_path.read_text(encoding="utf-8")
    pilot_path.write_text(original.replace("complete_not_promoted", "passed", 1), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="pilot review binding"):
            run_quality_campaign(
                frozen,
                _examples(),
                phase="confirmatory",
                output_root=tmp_path / "confirmatory",
                model_metadata={},
            )
    finally:
        pilot_path.write_text(original, encoding="utf-8")


def test_confirmatory_runner_refuses_mismatched_pilot_protocol_digest(tmp_path):
    draft = _protocol(tmp_path)
    review = dict(draft.pilot_review_provenance)
    review["protocol_sha256"] = hashlib.sha256(b"different-draft-protocol").hexdigest()
    frozen = draft.freeze(
        rubric_version="frozen-v1",
        primary_metric="correctness_full_rate",
        thresholds={"correctness_lower_bound": 0.0, "critical_safety_failure_rate_upper_bound": 0.0},
        pilot_review_provenance=review,
    )
    with pytest.raises(ValueError, match="pilot review binding"):
        run_quality_campaign(
            frozen,
            _examples(),
            phase="confirmatory",
            output_root=tmp_path / "confirmatory",
            model_metadata={},
        )


def test_confidence_probe_and_external_runner_capture_provenance(tmp_path):
    assert parse_confidence('{"confidence": 0.75}') == pytest.approx(0.75)
    assert parse_confidence("confidence: 0.25") == pytest.approx(0.25)
    assert parse_confidence("not a confidence response") is None

    protocol = _protocol(tmp_path)
    prompts: list[str] = []
    extractive = ExtractiveLM()

    def complete(prompt: str) -> str:
        if "numeric field named confidence" in prompt:
            return '{"confidence": 0.75}'
        prompts.append(prompt)
        return extractive.complete(prompt)

    summary = run_quality_campaign(
        protocol,
        _examples(),
        phase="pilot",
        output_root=tmp_path / "external",
        model_metadata={"model": {"digest": "sha256:model", "available": True}},
        lm_factory=lambda _model, _options: CallableLM(complete),
    )
    assert summary.status == "pending_annotation"
    assert summary.n_requested == 6
    assert summary.n_evaluated == 6
    assert summary.n_failed == 0
    assert Path(summary.metadata_path).is_file()
    observations = load_jsonl(summary.observations_path, QualityObservation.from_dict)
    assert len(observations) == 6
    assert all(row.confidence == pytest.approx(0.75) for row in observations)
    assert all(row.confidence_response == '{"confidence": 0.75}' for row in observations)
    assert all(row.model_digest == "sha256:model" for row in observations)
    template_rows = [json.loads(line) for line in Path(summary.annotation_template).read_text(encoding="utf-8").splitlines()]
    assert template_rows
    assert all(
        "model" not in row
        and "condition_id" not in row
        and "question_id" not in row
        and "evidence_indices" not in row
        and "cited_excerpts" not in row
        and "packet_id" in row
        and "evidence_packet" in row
        for row in template_rows
    )
    assert all("reference_answer" not in row for row in template_rows)
    assert prompts

    # The same question is presented with identical source material under each
    # condition; only the answer/claims vary.  Judges must not be able to infer
    # the condition from a missing or condition-specific evidence packet.
    packets_by_question: dict[str, list[dict]] = {}
    for row in template_rows:
        packets_by_question.setdefault(row["question"], []).append(row)
    assert all(len(rows) == 2 for rows in packets_by_question.values())
    for rows in packets_by_question.values():
        assert rows[0]["evidence_packet"] == rows[1]["evidence_packet"]
        assert rows[0]["session_history"] == rows[1]["session_history"]
        assert "reference_answer" not in rows[0] and "reference_answer" not in rows[1]

    reordered_path = tmp_path / "reordered-template.jsonl"
    create_annotation_template(
        list(reversed(observations)),
        _examples(),
        reordered_path,
    )
    first_packets = [json.loads(line) for line in Path(summary.annotation_template).read_text(encoding="utf-8").splitlines()]
    reordered_packets = [json.loads(line) for line in reordered_path.read_text(encoding="utf-8").splitlines()]
    # Different input order cannot change the deterministic blinded assignment.
    assert [row["packet_id"] for row in first_packets] == [row["packet_id"] for row in reordered_packets]

    observation_path = Path(summary.observations_path)
    tampered = json.loads(observation_path.read_text(encoding="utf-8").splitlines()[0])
    tampered["code_fingerprint"] = "stale-code"
    observation_path.write_text(json.dumps(tampered) + "\n" + "\n".join(observation_path.read_text(encoding="utf-8").splitlines()[1:]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="provenance mismatch"):
        run_quality_campaign(
            protocol,
            _examples(),
            phase="pilot",
            output_root=tmp_path / "external",
            model_metadata={"model": {"digest": "sha256:model", "available": True}},
            lm_factory=lambda _model, _options: CallableLM(complete),
        )


def test_quality_contract_rejects_invalid_rubric_protocol_and_parser_shapes(tmp_path):
    protocol = _protocol(tmp_path)
    rubric = dict(protocol.rubric)
    for field, value, message in (
        ("ordinal_scale", {"0": "only one level"}, "ordinal_scale"),
        ("dimensions", ["correctness"], "dimensions is missing"),
        ("binary_outcomes", ["critical_safety_failure"], "binary_outcomes is missing"),
        ("atomic_claim_labels", ["supported"], "atomic_claim_labels"),
    ):
        with pytest.raises(ValueError, match=message):
            replace(protocol, rubric={**rubric, field: value})
    with pytest.raises(ValueError, match=r"rubric.ordinal_scale\[0\]"):
        replace(protocol, rubric={**rubric, "ordinal_scale": {"0": "", "1": "partial", "2": "full"}})
    with pytest.raises(ValueError, match="rubric must be a mapping"):
        replace(protocol, rubric=[])
    with pytest.raises(ValueError, match="rubric.dimensions"):
        replace(protocol, rubric={**rubric, "dimensions": None})
    with pytest.raises(ValueError, match="rubric.binary_outcomes"):
        replace(protocol, rubric={**rubric, "binary_outcomes": None})
    with pytest.raises(ValueError, match="rubric.atomic_claim_labels"):
        replace(protocol, rubric={**rubric, "atomic_claim_labels": None})

    with pytest.raises(ValueError, match="mode"):
        QualityCondition("bad", "model", "unsupported")
    with pytest.raises(ValueError, match="duplicate keys"):
        QualityCondition("bad", "model", "harness", config_overrides=(("temperature", 0.0), ("temperature", 1.0)))
    with pytest.raises(ValueError, match="models"):
        default_quality_conditions(())
    with pytest.raises(ValueError, match="models"):
        default_quality_conditions(("same", "same"))

    examples = _examples()
    benchmark = tmp_path / "examples.json"
    benchmark.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="positive"):
        QualityProtocol.from_examples(protocol_id="bad", benchmark_path=benchmark, examples=examples, pilot_per_stratum=0)
    with pytest.raises(ValueError, match="non-empty"):
        QualityProtocol.from_examples(protocol_id="bad", benchmark_path=benchmark, examples=[], pilot_per_stratum=1)
    with pytest.raises(ValueError, match="unique"):
        QualityProtocol.from_examples(protocol_id="bad", benchmark_path=benchmark, examples=examples + [examples[0]], pilot_per_stratum=1)
    with pytest.raises(ValueError, match="fewer"):
        QualityProtocol.from_examples(protocol_id="bad", benchmark_path=benchmark, examples=examples, pilot_per_stratum=3)
    with pytest.raises(ValueError, match="confirmatory"):
        QualityProtocol.from_examples(protocol_id="bad", benchmark_path=benchmark, examples=examples, pilot_per_stratum=2)

    with pytest.raises(ValueError, match="benchmark_provenance must be a mapping"):
        replace(protocol, benchmark_provenance=[])
    with pytest.raises(ValueError, match="pilot_ids"):
        replace(protocol, pilot_ids=())
    with pytest.raises(ValueError, match="confirmatory_ids"):
        replace(protocol, confirmatory_ids=())
    with pytest.raises(ValueError, match="disjoint"):
        replace(protocol, confirmatory_ids=(protocol.pilot_ids[0], "new"))
    with pytest.raises(ValueError, match="conditions must be non-empty"):
        replace(protocol, conditions=())
    with pytest.raises(ValueError, match="generation_options"):
        replace(protocol, generation_options={})
    with pytest.raises(ValueError, match="rubric_version"):
        replace(protocol, rubric_version="")
    with pytest.raises(ValueError, match="primary_metric"):
        replace(protocol, primary_metric="accuracy")
    with pytest.raises(ValueError, match="confidence"):
        replace(protocol, confidence=1.0)
    with pytest.raises(ValueError, match="pilot_review_provenance"):
        replace(protocol, pilot_review_provenance=[])
    with pytest.raises(ValueError, match="matrix_policy"):
        replace(protocol, matrix_policy="other")
    with pytest.raises(ValueError, match="atomic_claims_required"):
        replace(protocol, atomic_claims_required=1)
    with pytest.raises(ValueError, match="judge_ids"):
        replace(protocol, judge_ids=("judge-a",))
    with pytest.raises(ValueError, match="adjudicator_id"):
        replace(protocol, adjudicator_id="judge-a")
    with pytest.raises(ValueError, match="blind_packet_version"):
        replace(protocol, blind_packet_version="")
    with pytest.raises(ValueError, match="standard-six"):
        replace(protocol, matrix_policy="standard-six")
    with pytest.raises(ValueError, match="thresholds"):
        replace(protocol, thresholds={"bad": 2.0})

    payload = protocol.to_dict()
    with pytest.raises(ValueError, match="schema"):
        QualityProtocol.from_dict({**payload, "schema_version": 999})
    with pytest.raises(ValueError, match="digest"):
        QualityProtocol.from_dict({**payload, "protocol_sha256": "0" * 64})
    with pytest.raises(ValueError, match="conditions must be a list"):
        QualityProtocol.from_dict({**payload, "conditions": None})

    assert parse_confidence_response("```json\n{\"confidence\": 0.5}\n```") == pytest.approx(0.5)
    assert parse_confidence_response("confidence=1.0") == pytest.approx(1.0)
    assert parse_confidence_response("") is None
    assert parse_confidence_response("{\"confidence\": true}") is None
    assert parse_confidence_response("{\"confidence\": 2}") is None


def test_quality_validation_and_calibration_fail_closed(tmp_path):
    """Exercise malformed typed payloads and the full calibration contract."""
    protocol = _protocol(tmp_path)
    with pytest.raises(ValueError, match="boolean"):
        _bool("yes", "flag")
    with pytest.raises(ValueError, match="integer"):
        _integer(True, "count")
    with pytest.raises(ValueError, match="size_bytes"):
        replace(protocol, benchmark_provenance={**protocol.benchmark_provenance, "size_bytes": -1})
    with pytest.raises(ValueError, match="question IDs"):
        replace(protocol, pilot_ids=("",))
    with pytest.raises(ValueError, match="evaluation_mode"):
        replace(protocol, evaluation_mode="human")
    with pytest.raises(ValueError, match="judge_models entries"):
        replace(protocol, judge_models=cast(Any, (("judge-a", "judge", "a" * 64, "extra"),)))
    with pytest.raises(ValueError, match="unique judge IDs"):
        replace(protocol, judge_models=cast(Any, (("judge-a", "judge", "a" * 64), ("judge-a", "judge2", "b" * 64))))
    with pytest.raises(ValueError, match="exactly the two"):
        replace(protocol, judge_models=(("other", "judge", "a" * 64),))
    with pytest.raises(ValueError, match="adjudicator_model"):
        replace(protocol, adjudicator_model=cast(Any, ("only-model",)))

    with pytest.raises(ValueError, match="non-empty"):
        weighted_cohen_kappa([], [])
    with pytest.raises(ValueError, match="maximum"):
        weighted_cohen_kappa([0], [0], maximum=0)
    with pytest.raises(ValueError, match="labels"):
        weighted_cohen_kappa([0], [3])
    with pytest.raises(ValueError, match="non-empty"):
        brier_score([], [])
    with pytest.raises(ValueError, match="outcomes"):
        brier_score([0.5], [2])
    with pytest.raises(ValueError, match="non-empty"):
        expected_calibration_error([], [])
    with pytest.raises(ValueError, match="bins"):
        expected_calibration_error([0.5], [1], bins=0)
    with pytest.raises(ValueError, match="outcomes"):
        expected_calibration_error([0.5], [2])
    with pytest.raises(ValueError, match="non-empty"):
        reliability_curve([], [])
    with pytest.raises(ValueError, match="bins"):
        reliability_curve([0.5], [1], bins=0)
    with pytest.raises(ValueError, match="outcomes"):
        reliability_curve([0.5], [2])
    with pytest.raises(ValueError, match="non-empty"):
        selective_accuracy([], [])
    with pytest.raises(ValueError, match="outcomes"):
        selective_accuracy([0.5], [2])
    with pytest.raises(ValueError, match="coverage_levels"):
        selective_accuracy([0.5], [1], coverage_levels=(0.0,))
    with pytest.raises(ValueError, match="unique"):
        selective_accuracy([0.5], [1], coverage_levels=(1.0, 1.0))


def test_quality_evidence_helpers_resolve_relative_inputs_fail_closed(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path)
    monkeypatch.chdir(tmp_path)
    from src.evaluation.accounting import file_provenance

    benchmark = Path(__file__).resolve().parents[1] / "data/longmemeval/longmemeval_s.json"
    benchmark_provenance = file_provenance(benchmark)
    assert _validate_benchmark_file({**benchmark_provenance, "path": "data/longmemeval/longmemeval_s.json"}) is None
    assert _validate_pilot_review_binding(replace(protocol, pilot_review_provenance={})) == "pilot review provenance is missing"

    observation = _observation(protocol, "pilot", "model-harness", protocol.pilot_ids[0], 0)
    issues: list[str] = []
    assert _raw_evidence_manifest([observation], evidence_root=None, issues=issues) == ()
    assert "raw_evidence_root_missing" in issues
    missing_root = tmp_path / "missing-evidence"
    missing_root.mkdir()
    missing_issues: list[str] = []
    assert _raw_evidence_manifest([observation], evidence_root=missing_root, issues=missing_issues) == ()
    assert any(issue.startswith("raw_evidence_missing:") for issue in missing_issues)
    target = missing_root / observation.raw_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")
    invalid_issues: list[str] = []
    entries = _raw_evidence_manifest([observation], evidence_root=missing_root, issues=invalid_issues)
    assert len(entries) == 1
    assert any(issue.startswith("raw_observation_missing:") for issue in invalid_issues)


def test_quality_record_types_reject_tampering_and_roundtrip_shapes(tmp_path):
    protocol = _protocol(tmp_path)
    observation = _observation(protocol, "pilot", "model-harness", protocol.pilot_ids[0], 0)
    with pytest.raises(ValueError, match="evidence_indices"):
        QualityClaim("claim", "text", (True,))
    claim = QualityClaim.from_dict(QualityClaim("claim", "text", (0,)).to_dict())
    assert claim.claim_text == "text"
    with pytest.raises(ValueError, match="claim label"):
        QualityClaimAnnotation(observation.presentation_id, "judge", "claim", "bad")
    claim_annotation = QualityClaimAnnotation.from_dict(
        QualityClaimAnnotation(observation.presentation_id, "judge", "claim", "supported").to_dict()
    )
    assert claim_annotation.label == "supported"
    with pytest.raises(ValueError, match="claim label"):
        QualityClaimAdjudication(observation.presentation_id, "claim", "adjudicator", "bad")
    claim_adjudication = QualityClaimAdjudication.from_dict(
        QualityClaimAdjudication(observation.presentation_id, "claim", "adjudicator", "uncertain").to_dict()
    )
    assert claim_adjudication.label == "uncertain"

    annotation = QualityAnnotation(
        presentation_id=observation.presentation_id,
        judge_id="judge",
        rubric_version="draft-v1",
        correctness=2,
        completeness=2,
        faithfulness=2,
        usefulness=2,
        abstention_appropriate=True,
        critical_safety_failure=False,
        claim_labels=(claim_annotation,),
    )
    assert QualityAnnotation.from_dict(annotation.to_dict()) == annotation
    with pytest.raises(ValueError, match="identity"):
        replace(annotation, claim_labels=(replace(claim_annotation, judge_id="other"),))
    with pytest.raises(ValueError, match="mappings"):
        QualityAnnotation.from_dict({**annotation.to_dict(), "claim_labels": [None]})

    adjudication = QualityAdjudication(
        presentation_id=observation.presentation_id,
        rubric_version="draft-v1",
        resolved_by="adjudicator",
        correctness=2,
        completeness=2,
        faithfulness=2,
        usefulness=2,
        abstention_appropriate=True,
        critical_safety_failure=False,
        claim_adjudications=(claim_adjudication,),
    )
    assert QualityAdjudication.from_dict(adjudication.to_dict()) == adjudication
    with pytest.raises(ValueError, match="identity"):
        replace(adjudication, claim_adjudications=(replace(claim_adjudication, resolved_by="other"),))
    with pytest.raises(ValueError, match="mappings"):
        QualityAdjudication.from_dict({**adjudication.to_dict(), "claim_adjudications": [None]})

    with pytest.raises(ValueError, match="phase"):
        replace(observation, phase="bad")
    with pytest.raises(ValueError, match="mode"):
        replace(observation, mode="bad")
    with pytest.raises(ValueError, match="status"):
        replace(observation, status="pending")
    with pytest.raises(ValueError, match="citation_indices"):
        replace(observation, citation_indices=(True,))
    with pytest.raises(ValueError, match="evidence_indices"):
        replace(observation, evidence_indices=(True,))
    with pytest.raises(ValueError, match="citations"):
        replace(observation, citations=((True, "text"),))
    with pytest.raises(ValueError, match="finite"):
        replace(observation, confidence=math.nan)
    with pytest.raises(ValueError, match="latency_seconds"):
        replace(observation, latency_seconds=-1.0)
    with pytest.raises(ValueError, match="answer_sha256"):
        replace(observation, answer_sha256="0")
    with pytest.raises(ValueError, match="generation_options"):
        replace(observation, generation_options=())
    with pytest.raises(ValueError, match="citation_indices"):
        replace(observation, citation_indices=(0,), citations=())
    with pytest.raises(ValueError, match="confidence_response"):
        replace(observation, confidence_response="")
    with pytest.raises(ValueError, match="confidence"):
        replace(observation, confidence=None, confidence_response='{"confidence": 0.9}')
    with pytest.raises(ValueError, match="latency_seconds"):
        replace(observation, latency_seconds=None)
    with pytest.raises(ValueError, match="answer_sha256"):
        replace(observation, answer_sha256="0" * 64)
    with pytest.raises(ValueError, match="cannot carry errors"):
        replace(observation, error_class="stale")
    with pytest.raises(ValueError, match="failed observations"):
        replace(observation, status="failed", error_class=None)

    observation_payload = observation.to_dict()
    blinded_payload = observation.to_dict(include_answer=False, include_raw_digest=False)
    assert "answer" not in blinded_payload
    assert "raw_sha256" not in blinded_payload
    with pytest.raises(ValueError, match="answer must be text"):
        QualityObservation.from_dict({**observation_payload, "answer": 1})
    with pytest.raises(ValueError, match="confidence_response must be text"):
        QualityObservation.from_dict({**observation_payload, "confidence_response": 1})
    with pytest.raises(ValueError, match="citations must contain mappings"):
        QualityObservation.from_dict({**observation_payload, "citations": [None]})
    with pytest.raises(ValueError, match="claims must contain mappings"):
        QualityObservation.from_dict({**observation_payload, "claims": [None]})
    with pytest.raises(ValueError, match="each claim at most once"):
        replace(annotation, claim_labels=(claim_annotation, claim_annotation))
    with pytest.raises(ValueError, match="cannot traverse"):
        replace(annotation, raw_path="../annotation.json")
    with pytest.raises(ValueError, match="each claim at most once"):
        replace(adjudication, claim_adjudications=(claim_adjudication, claim_adjudication))
    with pytest.raises(ValueError, match="cannot traverse"):
        replace(adjudication, raw_path="../adjudication.json")
    with pytest.raises(ValueError, match="non-empty"):
        _metric_mean([])
    with pytest.raises(ValueError, match="non-empty"):
        _percentile([], 0.95)
    assert _percentile([0.1], 0.95) == pytest.approx(0.1)


def test_quality_report_contract_and_threshold_family_fail_closed(tmp_path):
    protocol = _protocol(tmp_path)
    benchmark = dict(protocol.benchmark_provenance)
    base = {
        "protocol_id": protocol.protocol_id,
        "phase": "confirmatory",
        "status": "pending_annotation",
        "benchmark_provenance": benchmark,
        "n_observations": 0,
        "n_annotations": 0,
        "n_adjudications": 0,
        "metrics": {},
        "agreement": {},
        "comparisons": {},
        "threshold_results": {},
    }
    with pytest.raises(ValueError, match="phase"):
        QualityReport(**{**base, "phase": "bad"})
    with pytest.raises(ValueError, match="status"):
        QualityReport(**{**base, "status": "bad"})
    with pytest.raises(ValueError, match="certificate_sha256"):
        QualityReport(**{**base, "certificate_sha256": "0" * 63})
    with pytest.raises(ValueError, match="benchmark_provenance"):
        QualityReport(**{**base, "benchmark_provenance": []})
    with pytest.raises(ValueError, match="benchmark_provenance.sha256"):
        QualityReport(**{**base, "benchmark_provenance": {"sha256": "bad"}})
    with pytest.raises(ValueError, match="evidence_manifest"):
        QualityReport(**{**base, "evidence_manifest": []})
    with pytest.raises(ValueError, match="n_observations"):
        QualityReport(**{**base, "n_observations": True})
    with pytest.raises(ValueError, match="passed quality"):
        QualityReport(**{**base, "status": "passed", "threshold_results": {"x": False}, "evidence_manifest": {"x": 1}})
    with pytest.raises(ValueError, match="only confirmatory"):
        QualityReport(**{**base, "phase": "pilot", "status": "passed", "threshold_results": {"x": True}, "evidence_manifest": {"x": 1}})
    with pytest.raises(ValueError, match="failed quality"):
        QualityReport(**{**base, "status": "failed"})
    with pytest.raises(ValueError, match="complete_not_promoted"):
        QualityReport(**{**base, "status": "complete_not_promoted", "issues": ("unresolved",)})

    valid = QualityReport(**{
        **base,
        "status": "passed",
        "threshold_results": {"x": True},
        "evidence_manifest": {"x": 1},
    })
    payload = valid.to_dict()
    assert QualityReport.from_dict(payload).to_dict() == payload
    with pytest.raises(ValueError, match="schema"):
        QualityReport.from_dict({**payload, "schema_version": 999})
    with pytest.raises(ValueError, match="certificate digest"):
        QualityReport.from_dict({**payload, "certificate_sha256": "0" * 64})

    metrics = {
        "correctness_full_rate": {"low": 0.8},
        "faithfulness_mean": 0.9,
        "critical_safety_failure_rate": 0.0,
        "brier_score": 0.1,
        "expected_calibration_error": 0.05,
        "confidence_coverage": 1.0,
        "atomic_claim_support_rate": 0.95,
    }
    agreement = {field: 0.9 for field in ("correctness", "completeness", "faithfulness", "usefulness")}
    thresholds = {
        "correctness_lower_bound": 0.8,
        "faithfulness_mean": 0.9,
        "critical_safety_failure_rate_upper_bound": 0.0,
        "brier_score_upper_bound": 0.1,
        "expected_calibration_error_upper_bound": 0.05,
        "confidence_coverage_lower_bound": 1.0,
        "atomic_claim_support_lower_bound": 0.95,
        "inter_judge_kappa_lower_bound": 0.9,
        "unknown_threshold": 0.0,
    }
    evaluated = _evaluate_thresholds(thresholds, metrics, agreement)
    assert all(evaluated[name] for name in thresholds if name != "unknown_threshold")
    assert evaluated["unknown_threshold"] is False
    assert _evaluate_thresholds(
        {"brier_score_upper_bound": 0.1, "atomic_claim_support_lower_bound": 0.9},
        {"brier_score": None, "atomic_claim_support_rate": None},
        agreement,
    ) == {"brier_score_upper_bound": False, "atomic_claim_support_lower_bound": False}


def test_external_runner_executes_all_standard_matrix_modes(tmp_path):
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text("[]\n", encoding="utf-8")
    protocol = QualityProtocol.from_examples(
        protocol_id="standard-matrix",
        benchmark_path=benchmark,
        examples=_examples(),
        conditions=default_quality_conditions(),
        pilot_per_stratum=1,
    )
    extractive = ExtractiveLM()

    def complete(prompt: str) -> str:
        if "numeric field named confidence" in prompt:
            return '{"confidence": 0.75}'
        return extractive.complete(prompt)

    summary = run_quality_campaign(
        protocol,
        _examples(),
        phase="pilot",
        output_root=tmp_path / "standard-matrix-run",
        model_metadata={
            "gemma3:4b": {"digest": "sha256:gemma"},
            "hermes3:latest": {"digest": "sha256:hermes"},
        },
        lm_factory=lambda _model, _options: CallableLM(complete),
    )
    assert summary.n_requested == 18
    assert summary.n_evaluated == 18
    observations = load_jsonl(summary.observations_path, QualityObservation.from_dict)
    assert {row.mode for row in observations} == {"harness", "no_harness", "oracle_evidence"}
    assert all(row.confidence == pytest.approx(0.75) for row in observations)


def test_quality_provenance_helpers_fail_closed(tmp_path):
    assert _pilot_review_structural_issue({}) == "pilot review provenance is missing"
    assert _pilot_review_structural_issue({"report": {}}) == "pilot review provenance requires report.path"
    assert _pilot_review_structural_issue({"report": []}) == "pilot review provenance requires report metadata"
    assert _pilot_review_structural_issue({"report": {"path": "x"}}) == "pilot review provenance requires a non-negative report.size_bytes"
    assert _pilot_review_structural_issue({"report": {"path": "x", "size_bytes": 0}}).endswith("SHA-256 hex digest")
    valid_shape = {
        "report": {"path": "x", "size_bytes": 0, "sha256": "0" * 64, "certificate_sha256": "1" * 64},
        "protocol_sha256": "2" * 64,
        "status": "invalid",
    }
    assert "status" in (_pilot_review_structural_issue(valid_shape) or "")

    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text("[]\n", encoding="utf-8")
    from src.evaluation.accounting import file_provenance

    provenance = file_provenance(benchmark)
    assert _validate_benchmark_file({}) == "benchmark_path_missing"
    assert _validate_benchmark_file({"path": str(tmp_path / "missing.json")}) == "benchmark_file_missing"
    assert _validate_benchmark_file({"path": str(benchmark), "sha256": "0" * 64, "size_bytes": provenance["size_bytes"]}) == "benchmark_provenance_mismatch"
    assert _validate_benchmark_file(provenance) is None
    benchmark_provenance = file_provenance(Path("data/longmemeval/longmemeval_s.json"))
    assert _validate_benchmark_file({
        "path": "data/longmemeval/longmemeval_s.json",
        "sha256": benchmark_provenance["sha256"],
        "size_bytes": benchmark_provenance["size_bytes"],
    }) is None

    assert _validate_external_provenance_paths({"protocol_path": str(tmp_path / "no-protocol")}) == ["protocol_path_missing"]
    assert _validate_external_provenance_paths({"protocol_path": None, "observations_path": "", "annotations_path": 1}) == ["observations_path_missing", "annotations_path_missing"]


def test_quality_promotion_rejects_each_provenance_break(tmp_path):
    draft = _protocol(tmp_path)
    protocol = draft.freeze(
        rubric_version="frozen-v1",
        primary_metric="correctness_full_rate",
        thresholds={"correctness_lower_bound": 0.0, "critical_safety_failure_rate_upper_bound": 0.0},
        pilot_review_provenance=draft.pilot_review_provenance,
    )
    observations = [
        _observation(protocol, "confirmatory", condition_id, question_id, index)
        for index, question_id in enumerate(protocol.confirmatory_ids)
        for condition_id in ("model-harness", "model-no-harness")
    ]
    evidence_root = tmp_path / "evidence"
    observations = _materialize_raw(observations, evidence_root)
    annotations, adjudications = _labels(observations)
    protocol_path = tmp_path / "protocol.json"
    observations_path = tmp_path / "observations.jsonl"
    annotations_path = tmp_path / "annotations.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    protocol.write(protocol_path)
    write_jsonl(observations_path, (row.to_dict() for row in observations))
    write_jsonl(annotations_path, (row.to_dict() for row in annotations))
    write_jsonl(adjudications_path, (row.to_dict() for row in adjudications))
    report = build_quality_report(
        protocol,
        observations,
        annotations,
        adjudications,
        phase="confirmatory",
        provenance={
            "protocol_path": str(protocol_path),
            "observations_path": str(observations_path),
            "annotations_path": str(annotations_path),
            "adjudications_path": str(adjudications_path),
        },
        evidence_root=evidence_root,
    )
    source = tmp_path / "source.json"
    report.write(source)
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps({"accepted": True, "accepted_by": "reviewer", "report_certificate_sha256": report.to_dict()["certificate_sha256"]}),
        encoding="utf-8",
    )

    def attempt(name: str, variant: QualityReport, match: str) -> None:
        path = tmp_path / f"{name}.json"
        variant.write(path)
        with pytest.raises(ValueError, match=match):
            promote_quality_report(path, tmp_path / f"{name}-target.json", acceptance_path=acceptance)

    attempt("no-provenance", replace(report, provenance={}), "protocol and evidence provenance")
    missing_key = dict(report.evidence_manifest)
    missing_key.pop("condition_ids")
    attempt("missing-key", replace(report, evidence_manifest=missing_key), "complete evidence manifest")
    attempt("bad-benchmark", replace(report, benchmark_provenance={"path": str(tmp_path / "none"), "sha256": "0" * 64, "size_bytes": 0}), "benchmark provenance")
    attempt("missing-root", replace(report, provenance={**report.provenance, "evidence_root": str(tmp_path / "missing-root")}), "raw evidence root")
    attempt("no-raw", replace(report, evidence_manifest={**report.evidence_manifest, "raw_files": []}), "raw evidence entries")
    attempt("unsafe-raw", replace(report, evidence_manifest={**report.evidence_manifest, "raw_files": [{"raw_path": "../unsafe", "sha256": "0" * 64, "size_bytes": 0}]}), "raw evidence path")
    attempt("missing-raw", replace(report, evidence_manifest={**report.evidence_manifest, "raw_files": [{"raw_path": "missing.json", "sha256": "0" * 64, "size_bytes": 0}]}), "raw evidence is missing")
    attempt("no-sources", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": {}}), "source-file manifest")
    incomplete_sources = dict(report.evidence_manifest["source_files"])
    incomplete_sources.pop("annotations")
    attempt("missing-source-name", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": incomplete_sources}), "ledger source files")
    invalid_protocol_source = dict(report.evidence_manifest["source_files"])
    invalid_protocol_source["protocol"] = "not-a-mapping"
    attempt("bad-protocol-source", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": invalid_protocol_source}), "bound protocol source")
    missing_protocol_source = dict(report.evidence_manifest["source_files"])
    missing_protocol_source["protocol"] = {"path": str(tmp_path / "missing-protocol")}
    attempt("missing-protocol-source", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": missing_protocol_source}), "protocol source file is missing")
    unreadable = tmp_path / "unreadable-protocol"
    unreadable.write_text("not json\n", encoding="utf-8")
    unreadable_sources = dict(report.evidence_manifest["source_files"])
    unreadable_sources["protocol"] = {"path": str(unreadable)}
    attempt("unreadable-protocol-source", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": unreadable_sources}), "protocol source file is unreadable")
    other_protocol = tmp_path / "other-protocol.json"
    replace(protocol, protocol_id="other").write(other_protocol)
    other_sources = dict(report.evidence_manifest["source_files"])
    other_sources["protocol"] = {"path": str(other_protocol)}
    attempt("other-protocol-source", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": other_sources}), "protocol source digest mismatch")
    invalid_source_value = dict(report.evidence_manifest["source_files"])
    invalid_source_value["annotations"] = "not-a-mapping"
    attempt("bad-source-value", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": invalid_source_value}), "source-file manifest")
    missing_source_path = dict(report.evidence_manifest["source_files"])
    missing_source_path["annotations"] = {"path": str(tmp_path / "missing-annotations"), "sha256": "0" * 64, "size_bytes": 0}
    attempt("missing-source-path", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": missing_source_path}), "source file is missing")
    bad_source_digest = dict(report.evidence_manifest["source_files"])
    bad_source_digest["annotations"] = {**bad_source_digest["annotations"], "sha256": "0" * 64}
    attempt("bad-source-digest", replace(report, evidence_manifest={**report.evidence_manifest, "source_files": bad_source_digest}), "source-file digest mismatch")
    attempt("bad-protocol-provenance", replace(report, provenance={**report.provenance, "protocol_sha256": "0" * 64}), "protocol digest mismatch")
    with pytest.raises(ValueError, match="explicit acceptance"):
        promote_quality_report(source, tmp_path / "no-acceptance-target.json")
    with pytest.raises(ValueError, match="acceptance record is missing"):
        promote_quality_report(source, tmp_path / "missing-acceptance-target.json", acceptance_path=tmp_path / "missing-acceptance.json")
    invalid_acceptance = tmp_path / "invalid-acceptance.json"
    invalid_acceptance.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="acceptance record is unreadable"):
        promote_quality_report(source, tmp_path / "invalid-acceptance-target.json", acceptance_path=invalid_acceptance)
    false_acceptance = tmp_path / "false-acceptance.json"
    false_acceptance.write_text(json.dumps({"accepted": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="accepted=true"):
        promote_quality_report(source, tmp_path / "false-acceptance-target.json", acceptance_path=false_acceptance)
    wrong_acceptance = tmp_path / "wrong-acceptance.json"
    wrong_acceptance.write_text(json.dumps({"accepted": True, "accepted_by": "reviewer", "report_certificate_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(ValueError, match="does not bind"):
        promote_quality_report(source, tmp_path / "wrong-acceptance-target.json", acceptance_path=wrong_acceptance)
    blank_reviewer = tmp_path / "blank-reviewer.json"
    blank_reviewer.write_text(json.dumps({"accepted": True, "accepted_by": " ", "report_certificate_sha256": report.to_dict()["certificate_sha256"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="accepted_by"):
        promote_quality_report(source, tmp_path / "blank-reviewer-target.json", acceptance_path=blank_reviewer)
