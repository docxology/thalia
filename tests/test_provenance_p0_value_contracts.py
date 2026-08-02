"""Focused zero-mock validation tests for P0 immutable evidence values."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.evaluation import provenance_p0 as p0


_DIGEST = "a" * 64


def _source() -> p0.P0SourceRecord:
    return p0.P0SourceRecord("true", "Verified fact.", "true", ("fact",))


def _claim() -> p0.P0ClaimSpec:
    return p0.P0ClaimSpec("claim", "State the verified fact.", "verified", ("true",), ("true",))


def _probe() -> p0.P0Probe:
    true = _source()
    false = p0.P0SourceRecord("false", "Conflicting fact.", "adversarial")
    return p0.P0Probe(
        task_id="task-1",
        attack_family="direct_override",
        answer_type="lookup",
        source_condition="one_false_source",
        query="What does the source support?",
        blinded_query="What answer is supported by the supplied records?",
        sources=(true, false),
        claims=(_claim(),),
        injected_source_ids=("false",),
    )


def _citation() -> p0.P0Citation:
    return p0.P0Citation("true", _DIGEST, "Verified fact.", 0, ("claim",))


def _row() -> p0.P0RunRow:
    return p0.P0RunRow(
        row_id="row-1",
        protocol_sha256=_DIGEST,
        run_id="initial",
        task_id="task-1",
        attack_family="direct_override",
        answer_type="lookup",
        source_condition="one_false_source",
        true_source_ids=("true",),
        injected_source_ids=("false",),
        condition_id="thalia",
        status="complete",
        canonical_input_sha256=_DIGEST,
        delivered_context_sha256=_DIGEST,
        answer_text="verified",
        citations=(_citation(),),
        delivered_source_ids=("true",),
        retrieved_source_ids=("true",),
        raw_path="raw/row-1.json",
        raw_sha256=_DIGEST,
        model_fingerprint=_DIGEST,
        config_fingerprint=_DIGEST,
        code_fingerprint=_DIGEST,
        execution_fingerprint=_DIGEST,
    )


def _receipt() -> p0.P0RunReceipt:
    return p0.P0RunReceipt(
        receipt_id="initial-receipt",
        protocol_sha256=_DIGEST,
        run_id="initial",
        model_fingerprint=_DIGEST,
        config_fingerprint=_DIGEST,
        code_fingerprint=_DIGEST,
        raw_path="raw/receipts/initial.json",
        raw_sha256=_DIGEST,
    )


def _blinded_claim() -> p0.P0BlindedClaim:
    return p0.P0BlindedClaim("claim-0001", "State the verified fact.", (("source-0001", "Verified fact."),))


def _adjudication() -> p0.P0Adjudication:
    return p0.P0Adjudication(
        presentation_id="p0-presentation",
        scorer_id="expert-a",
        scorer_version="rubric-v1",
        rubric_version="rubric-v1",
        evaluator_kind="blinded_expert_human",
        claims=(p0.P0ClaimAdjudication("claim-0001", True, True, True, False, True),),
        source_recall=True,
        source_precision=True,
        false_source_citation=False,
        poisoned_answer=False,
        raw_path="raw/adjudications/p0-presentation.json",
        raw_sha256=_DIGEST,
    )


def test_scalar_and_immutable_value_contracts_fail_closed(tmp_path) -> None:
    """Exercise the strict parser boundaries used before ledger analysis."""
    for function, value, name in (
        (p0._text, "", "text"),
        (p0._boolean, "true", "boolean"),
        (p0._integer, True, "integer"),
        (p0._unit, float("nan"), "unit"),
        (p0._finite, False, "finite"),
        (p0._mapping, [], "mapping"),
        (p0._items, {}, "items"),
        (p0._digest, "A" * 64, "digest"),
        (p0._safe_relative, "../escape", "path"),
    ):
        with pytest.raises(ValueError):
            function(value, name)
    with pytest.raises(ValueError, match="at least"):
        p0._integer(0, "minimum", minimum=1)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        p0._unit(1.1, "unit")
    with pytest.raises(ValueError, match="attack_family"):
        p0._admission(
            {"admission_id": "id", "criteria": "criterion", "path": "admission.json", "sha256": _DIGEST, "attack_family": "wrong"},
            "admission",
            expected_attack_family="direct_override",
        )

    source = _source()
    with pytest.raises(ValueError, match="source role"):
        replace(source, role="unsupported")
    with pytest.raises(ValueError, match="fact_ids"):
        replace(source, fact_ids=("fact", "fact"))
    source_payload = source.to_dict()
    source_payload["sha256"] = _DIGEST
    with pytest.raises(ValueError, match="source sha256"):
        p0.P0SourceRecord.from_dict(source_payload)

    claim = _claim()
    with pytest.raises(ValueError, match="true_source_ids"):
        replace(claim, true_source_ids=())
    with pytest.raises(ValueError, match="admissible_source_ids"):
        replace(claim, admissible_source_ids=())
    with pytest.raises(ValueError, match="must be admissible"):
        replace(claim, admissible_source_ids=("other",))

    probe = _probe()
    duplicate_text = p0.P0SourceRecord("context", source.text, "context")
    context = p0.P0SourceRecord("context", "Additional context.", "context")
    adversarial_true = p0.P0SourceRecord("true", source.text, "adversarial")
    with pytest.raises(ValueError, match="attack_family"):
        replace(probe, attack_family="unsupported")
    with pytest.raises(ValueError, match="answer_type"):
        replace(probe, answer_type="unsupported")
    with pytest.raises(ValueError, match="source_condition"):
        replace(probe, source_condition="unsupported")
    with pytest.raises(ValueError, match="sources"):
        replace(probe, sources=())
    with pytest.raises(ValueError, match="record IDs"):
        replace(probe, sources=(source, replace(source, text="Different fact.")))
    with pytest.raises(ValueError, match="source texts"):
        replace(probe, sources=(source, duplicate_text))
    with pytest.raises(ValueError, match="claims"):
        replace(probe, claims=())
    with pytest.raises(ValueError, match="claim IDs"):
        replace(probe, claims=(claim, replace(claim, expected_answer="different")))
    with pytest.raises(ValueError, match="claim_text"):
        replace(probe, claims=(replace(claim, claim_text="task-1 is the answer."),))
    with pytest.raises(ValueError, match="unknown source"):
        replace(probe, claims=(replace(claim, true_source_ids=("unknown",), admissible_source_ids=("unknown",)),))
    with pytest.raises(ValueError, match="injected_source_ids must be unique"):
        replace(probe, injected_source_ids=("false", "false"))
    with pytest.raises(ValueError, match="injected_source_ids reference"):
        replace(probe, injected_source_ids=("unknown",))
    with pytest.raises(ValueError, match="true and injected"):
        replace(probe, injected_source_ids=("true",))
    with pytest.raises(ValueError, match="adversarial role"):
        replace(probe, sources=(source, context), injected_source_ids=("context",))
    with pytest.raises(ValueError, match="true role"):
        replace(probe, sources=(adversarial_true, probe.sources[1]))
    with pytest.raises(ValueError, match="clean controls"):
        replace(probe, attack_family=p0.P0_CLEAN_CONTROL_FAMILY, source_condition="clean")
    with pytest.raises(ValueError, match="attack probes"):
        replace(probe, source_condition="clean")
    with pytest.raises(ValueError, match="multiple_false_sources"):
        replace(probe, source_condition="multiple_false_sources")

    with pytest.raises(ValueError, match="condition role"):
        p0.P0Condition("condition", "unsupported", "delivery", True, False)
    with pytest.raises(ValueError, match="citation_channel"):
        p0.P0Condition("condition", "target", "delivery", "true", False)  # type: ignore[arg-type]
    citation = _citation()
    with pytest.raises(ValueError, match="claim_ids"):
        replace(citation, claim_ids=())
    citation_payload = citation.to_dict()
    citation_payload["excerpt_sha256"] = _DIGEST
    with pytest.raises(ValueError, match="excerpt_sha256"):
        p0.P0Citation.from_dict(citation_payload)

    row = _row()
    with pytest.raises(ValueError, match="status"):
        replace(row, status="unknown")
    with pytest.raises(ValueError, match="delivered_source_ids"):
        replace(row, delivered_source_ids=("true", "true"))
    with pytest.raises(ValueError, match="retrieved_source_ids"):
        replace(row, retrieved_source_ids=("true", "true"))
    with pytest.raises(ValueError, match="true_source_ids"):
        replace(row, true_source_ids=())
    with pytest.raises(ValueError, match="injected_source_ids"):
        replace(row, injected_source_ids=("false", "false"))
    with pytest.raises(ValueError, match="true and injected"):
        replace(row, injected_source_ids=("true",))
    with pytest.raises(ValueError, match="error_class"):
        replace(row, error_class="RuntimeError")
    with pytest.raises(ValueError, match="partial answer"):
        replace(row, status="failed", error_class="RuntimeError")
    row_payload = row.to_dict()
    row_payload["answer_sha256"] = _DIGEST
    with pytest.raises(ValueError, match="answer_sha256"):
        p0.P0RunRow.from_dict(row_payload)
    failed = replace(row, status="failed", answer_text="", citations=(), retrieved_source_ids=(), error_class="RuntimeError")
    failed_payload = failed.to_dict()
    failed_payload["answer_sha256"] = _DIGEST
    with pytest.raises(ValueError, match="null answer_sha256"):
        p0.P0RunRow.from_dict(failed_payload)

    receipt = _receipt()
    receipt_payload = receipt.to_dict()
    receipt_payload["execution_fingerprint"] = _DIGEST
    with pytest.raises(ValueError, match="execution_fingerprint"):
        p0.P0RunReceipt.from_dict(receipt_payload)
    with pytest.raises(ValueError, match="one-to-one"):
        p0.P0BlindKey("presentation", "row", _DIGEST, (("blind", "claim"), ("blind", "other")))

    manifest = p0.P0BlindingManifest(*((_DIGEST,) * 6))
    manifest_payload = manifest.to_dict()
    manifest_payload["schema_version"] = 0
    with pytest.raises(ValueError, match="manifest schema"):
        p0.P0BlindingManifest.from_dict(manifest_payload)
    manifest_payload = manifest.to_dict()
    manifest_payload["manifest_sha256"] = _DIGEST
    with pytest.raises(ValueError, match="manifest digest"):
        p0.P0BlindingManifest.from_dict(manifest_payload)

    blinded_claim = _blinded_claim()
    with pytest.raises(ValueError, match="packet sources"):
        p0.P0BlindedPacket("presentation", "query", "answer", (), (blinded_claim,), "rubric-v1")
    with pytest.raises(ValueError, match="packet claim IDs"):
        p0.P0BlindedPacket("presentation", "query", "answer", (("source-0001", "Verified fact."),), (), "rubric-v1")
    with pytest.raises(ValueError, match="unknown packet source"):
        p0.P0BlindedPacket("presentation", "query", "answer", (("source-0001", "Verified fact."),), (p0.P0BlindedClaim("claim", "claim", (("source-9999", "Verified fact."),)),), "rubric-v1")
    with pytest.raises(ValueError, match="not a span"):
        p0.P0BlindedPacket("presentation", "query", "answer", (("source-0001", "Verified fact."),), (p0.P0BlindedClaim("claim", "claim", (("source-0001", "missing"),)),), "rubric-v1")

    adjudication = _adjudication()
    with pytest.raises(ValueError, match="adjudication claims"):
        replace(adjudication, claims=())
    with pytest.raises(ValueError, match="unknown P0 endpoint"):
        adjudication.endpoint_value("unknown")

    with pytest.raises(ValueError, match="unsupported P0 report status"):
        p0.P0Report("protocol", "unsupported", {}, {}, {}, {}, {}, (), {})
    with pytest.raises(ValueError, match="incomplete P0 reports"):
        p0.P0Report("protocol", "incomplete", {}, {}, {}, {}, {}, (), {})
    gates = {name: True for name in p0.P0_PROMOTION_GATE_KEYS}
    with pytest.raises(ValueError, match="exact predeclared"):
        p0.P0Report("protocol", "promotion_eligible", {}, {}, {}, {**gates, "extra": True}, {"fixture": {}}, (), {})

    missing_jsonl = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError):
        p0.load_p0_jsonl(missing_jsonl)
    not_object = tmp_path / "not-object.jsonl"
    not_object.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        p0.load_p0_jsonl(not_object)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="at least one"):
        p0.load_p0_jsonl(empty)
