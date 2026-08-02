"""Zero-mock tests for the exploratory local LLM-judge diagnostic."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.compiler.metrics import EvalExample
from src.evaluation.llm_judge import (
    JudgeModelSpec,
    bind_judge_models,
    parse_judge_annotation,
    run_llm_judging,
)
from src.evaluation.quality import (
    QualityClaim,
    QualityCondition,
    QualityObservation,
    QualityProtocol,
    load_jsonl,
)
from src.llm import CallableLM


_TARGET_DIGEST = "a" * 64
_JUDGE_A_DIGEST = "b" * 64
_JUDGE_B_DIGEST = "c" * 64
_ADJUDICATOR_DIGEST = "d" * 64


def _examples() -> list[EvalExample]:
    return [
        EvalExample(
            session_history="User: the alpha value is seven.",
            query="What is the alpha value?",
            expected_answer="seven",
            expected_source_indices=(0,),
            example_id="q-alpha",
            stratum="alpha",
        ),
        EvalExample(
            session_history="User: the alpha value is nine.",
            query="What is the alpha value?",
            expected_answer="nine",
            expected_source_indices=(0,),
            example_id="q-alpha-2",
            stratum="alpha",
        ),
        EvalExample(
            session_history="User: the beta value is eight.",
            query="What is the beta value?",
            expected_answer="eight",
            expected_source_indices=(0,),
            example_id="q-beta",
            stratum="beta",
        ),
        EvalExample(
            session_history="User: the beta value is ten.",
            query="What is the beta value?",
            expected_answer="ten",
            expected_source_indices=(0,),
            example_id="q-beta-2",
            stratum="beta",
        ),
    ]


def _protocol(tmp_path: Path):
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text("[]\n", encoding="utf-8")
    draft = QualityProtocol.from_examples(
        protocol_id="llm-judge-test",
        benchmark_path=benchmark,
        examples=_examples(),
        conditions=(
            QualityCondition("target-harness", "target-model", "harness"),
            QualityCondition("target-no-harness", "target-model", "no_harness", policy="full_context"),
        ),
        pilot_per_stratum=1,
    )
    return bind_judge_models(
        draft,
        (
            JudgeModelSpec("judge-1", "judge-model-a", _JUDGE_A_DIGEST),
            JudgeModelSpec("judge-2", "judge-model-b", _JUDGE_B_DIGEST),
        ),
        JudgeModelSpec("adjudicator", "adjudicator-model", _ADJUDICATOR_DIGEST, role="adjudicator"),
    )


def _observations(protocol: QualityProtocol) -> list[QualityObservation]:
    rows: list[QualityObservation] = []
    for condition in protocol.conditions:
        for question_id in protocol.pilot_ids:
            answer = f"answer for {question_id}"
            rows.append(
                QualityObservation(
                    observation_id=f"pilot:{condition.condition_id}:{question_id}",
                    protocol_id=protocol.protocol_id,
                    phase="pilot",
                    condition_id=condition.condition_id,
                    question_id=question_id,
                    model=condition.model,
                    mode=condition.mode,
                    status="complete",
                    stratum="alpha" if "alpha" in question_id else "beta",
                    answer=answer,
                    citation_indices=(0,),
                    citations=((0, "the source"),),
                    evidence_indices=(0,),
                    claims=(QualityClaim("claim-0000", answer, (0,)),),
                    confidence=0.8,
                    confidence_response=json.dumps({"confidence": 0.8}),
                    latency_seconds=0.1,
                    answer_sha256=hashlib.sha256(answer.encode()).hexdigest(),
                    model_digest=_TARGET_DIGEST,
                    config_fingerprint="e" * 64,
                    code_fingerprint="f" * 64,
                    generation_options=(("temperature", 0.0),),
                    raw_path=f"raw/{condition.condition_id}/{question_id}.json",
                )
            )
    return rows


def _judge_response(prompt: str, correctness: int) -> str:
    return json.dumps(
        {
            "correctness": correctness,
            "completeness": 2,
            "faithfulness": 2,
            "usefulness": 2,
            "abstention_appropriate": True,
            "critical_safety_failure": False,
            "claim_labels": [{"claim_id": "claim-0000", "label": "supported"}],
            "failure_modes": [],
            "confidence": 0.75,
            "notes": "bounded test evaluation",
        }
    )


def test_judge_binding_rejects_target_overlap(tmp_path: Path):
    protocol = _protocol(tmp_path)
    with pytest.raises(ValueError, match="must not overlap target"):
        bind_judge_models(
            replace(protocol, judge_models=(), adjudicator_model=()),
            (
                JudgeModelSpec("judge-1", "target-model", _JUDGE_A_DIGEST),
                JudgeModelSpec("judge-2", "judge-model-b", _JUDGE_B_DIGEST),
            ),
            JudgeModelSpec("adjudicator", "adjudicator-model", _ADJUDICATOR_DIGEST, role="adjudicator"),
        )


def test_parse_judge_annotation_requires_complete_atomic_labels(tmp_path: Path):
    protocol = _protocol(tmp_path)
    packet = {
        "packet_id": "presentation",
        "claims": [{"claim_id": "claim-0000", "claim_text": "a claim"}],
    }
    spec = JudgeModelSpec("judge-1", "judge-model-a", _JUDGE_A_DIGEST)
    with pytest.raises(ValueError, match="cover every atomic claim"):
        parse_judge_annotation(
            _judge_response("", 2).replace('"claim_labels": [{"claim_id": "claim-0000", "label": "supported"}]', '"claim_labels": []'),
            packet=packet,
            judge=spec,
            rubric_version=protocol.rubric_version,
            raw_path="judge_raw/judge-1/presentation.json",
            raw_sha256="1" * 64,
            prompt_sha256="2" * 64,
        )


def test_parse_judge_annotation_rejects_embedded_json_with_prose(tmp_path: Path):
    protocol = _protocol(tmp_path)
    packet = {
        "packet_id": "presentation",
        "claims": [{"claim_id": "claim-0000", "claim_text": "a claim"}],
    }
    spec = JudgeModelSpec("judge-1", "judge-model-a", _JUDGE_A_DIGEST)
    with pytest.raises(ValueError, match="strict JSON"):
        parse_judge_annotation(
            "Here is the result: " + _judge_response("", 2),
            packet=packet,
            judge=spec,
            rubric_version=protocol.rubric_version,
            raw_path="judge_raw/judge-1/presentation.json",
            raw_sha256="1" * 64,
            prompt_sha256="2" * 64,
        )


def test_run_llm_judging_writes_blinded_raw_provenance_and_adjudication(tmp_path: Path):
    protocol = _protocol(tmp_path)
    observations = _observations(protocol)

    def factory(spec: JudgeModelSpec):
        if spec.role == "adjudicator":
            return CallableLM(lambda prompt: _judge_response(prompt, 2))
        correctness = 2 if spec.judge_id == "judge-1" else 1
        return CallableLM(lambda prompt: _judge_response(prompt, correctness))

    summary = run_llm_judging(
        protocol,
        observations,
        _examples(),
        phase="pilot",
        output_root=tmp_path / "evidence",
        lm_factory=factory,
        project_root=Path(__file__).resolve().parents[1],
    )
    assert summary.n_expected == 4
    assert summary.n_annotations == 8
    assert summary.n_adjudications == 4
    assert summary.n_failed_judgments == 0
    annotations = load_jsonl(summary.annotations_path, lambda row: row)
    adjudications = load_jsonl(summary.adjudications_path, lambda row: row)
    assert len(annotations) == 8
    assert len(adjudications) == 4
    assert all(row["raw_sha256"] and row["prompt_sha256"] for row in annotations)
    assert all(row["raw_sha256"] and row["prompt_sha256"] for row in adjudications)
    assert all("target-model" not in json.dumps(row) for row in annotations)
    assert all("reference_answer" not in json.dumps(row) for row in annotations)
