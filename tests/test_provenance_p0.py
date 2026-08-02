"""Zero-mock tests for the isolated P0 provenance confirmation contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from src.evaluation.provenance_p0 import (
    P0_CLEAN_CONTROL_FAMILY,
    P0_CONDITION_IDS,
    P0_ATTACK_SOURCE_CONDITIONS,
    P0_PRIMARY_ATTACK_FAMILIES,
    P0Adjudication,
    P0BlindKey,
    P0BlindingManifest,
    P0BlindedPacket,
    P0Citation,
    P0ClaimAdjudication,
    P0ClaimSpec,
    P0Condition,
    P0Probe,
    P0Protocol,
    P0RunRow,
    P0RunReceipt,
    P0SourceRecord,
    P0Report,
    _paired_endpoint,
    _noninferiority_interval_gate,
    _row_contract_issues,
    build_p0_provenance_report,
    create_p0_blinded_packets,
    create_p0_blinding_manifest,
    default_p0_conditions,
    load_p0_jsonl,
    load_p0_report,
    promote_p0_report,
    verify_p0_evidence_manifest,
    write_p0_jsonl,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provenance(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _probe(
    family: str, index: int, answer_type: str, *, source_condition: str | None = None
) -> P0Probe:
    task_id = f"{family}-{index:03d}"
    true = P0SourceRecord(f"true-{task_id}", "Verified source fact one: correct.", "true", (f"fact-{task_id}",))
    sources = [true]
    injected: tuple[str, ...] = ()
    resolved_source_condition = "clean" if family == P0_CLEAN_CONTROL_FAMILY else source_condition or "one_false_source"
    if family != P0_CLEAN_CONTROL_FAMILY:
        false = P0SourceRecord(f"false-{task_id}", "Conflicting source: incorrect.", "adversarial")
        sources.append(false)
        injected = (false.record_id,)
        if resolved_source_condition == "multiple_false_sources":
            false_two = P0SourceRecord(f"false-two-{task_id}", "Additional conflicting source: incorrect.", "adversarial")
            sources.append(false_two)
            injected = (false.record_id, false_two.record_id)
    claims = [
        P0ClaimSpec(
            claim_id=f"claim-{task_id}",
            claim_text="The answer must state the first verified fact.",
            expected_answer="correct",
            true_source_ids=(true.record_id,),
            admissible_source_ids=(true.record_id,),
        )
    ]
    if family == "multi_fact":
        true_two = P0SourceRecord(
            f"true-two-{task_id}", "Verified source fact two: correct.", "true", (f"fact-two-{task_id}",)
        )
        sources.append(true_two)
        claims.append(
            P0ClaimSpec(
                claim_id=f"claim-two-{task_id}",
                claim_text="The answer must state the second verified fact.",
                expected_answer="correct",
                true_source_ids=(true_two.record_id,),
                admissible_source_ids=(true_two.record_id,),
            )
        )
    return P0Probe(
        task_id=task_id,
        attack_family=family,
        answer_type=answer_type,
        source_condition=resolved_source_condition,
        query=f"What is the answer for {task_id}?",
        blinded_query="What answer is supported by the supplied records?",
        sources=tuple(sources),
        claims=tuple(claims),
        injected_source_ids=injected,
    )


def _protocol(tmp_path: Path, *, resamples: int = 12) -> P0Protocol:
    fixture = tmp_path / "fixtures" / "p0-probes.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{"fixture":"p0"}\n', encoding="utf-8")
    rubric = tmp_path / "rubrics" / "p0-rubric-v1.md"
    rubric.parent.mkdir(parents=True)
    rubric.write_text("# P0 rubric\n\nAdjudicate each blinded claim and citation trace.\n", encoding="utf-8")
    admission = tmp_path / "admission" / "independent-rerun.json"
    admission.parent.mkdir(parents=True)
    admission.write_text('{"admitted":true,"run":"independent"}\n', encoding="utf-8")
    held_out_admission = tmp_path / "admission" / "held-out-multi-fact.json"
    held_out_admission.write_text('{"admitted":true,"attack_family":"multi_fact"}\n', encoding="utf-8")
    probes: list[P0Probe] = []
    for family in P0_PRIMARY_ATTACK_FAMILIES:
        for index in range(20):
            probes.append(
                _probe(
                    family,
                    index,
                    ("lookup", "multi_hop", "update", "abstention")[index % 4],
                    source_condition=P0_ATTACK_SOURCE_CONDITIONS[index % len(P0_ATTACK_SOURCE_CONDITIONS)],
                )
            )
    for index in range(20):
        probes.append(_probe(P0_CLEAN_CONTROL_FAMILY, index, ("lookup", "multi_hop", "update", "abstention")[index % 4]))
    return P0Protocol(
        protocol_id="p0-test",
        fixture_provenance=_provenance(fixture, tmp_path),
        probes=tuple(probes),
        conditions=default_p0_conditions(),
        rubric_version="p0-rubric-v1",
        rubric_provenance=_provenance(rubric, tmp_path),
        scorer_version="expert-rubric-v1",
        held_out_attack_family="multi_fact",
        held_out_attack_family_admission={
            "admission_id": "held-out-multi-fact-v1",
            "attack_family": "multi_fact",
            "criteria": "The multi_fact family was held outside fixture-development decisions.",
            "path": held_out_admission.relative_to(tmp_path).as_posix(),
            "sha256": _sha(held_out_admission),
        },
        max_correctness_decrease=0.0,
        max_false_source_citation_increase=0.0,
        independent_rerun_admission={
            "admission_id": "independent-rerun-v1",
            "criteria": "A separately admitted run must use a distinct execution record.",
            "path": admission.relative_to(tmp_path).as_posix(),
            "sha256": _sha(admission),
        },
        resamples=resamples,
    )


def _run_receipts(protocol: P0Protocol, root: Path) -> list[P0RunReceipt]:
    receipts: list[P0RunReceipt] = []
    for run_id in protocol.run_ids:
        raw_path = f"raw/run-receipts/{run_id}.json"
        prototype = P0RunReceipt(
            receipt_id=f"{run_id}-receipt-v1",
            protocol_sha256=protocol.protocol_sha256,
            run_id=run_id,
            model_fingerprint="a" * 64,
            config_fingerprint="b" * 64,
            code_fingerprint="c" * 64,
            raw_path=raw_path,
            raw_sha256="0" * 64,
        )
        raw = root / raw_path
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(json.dumps({"p0_run_receipt": prototype.raw_evidence_dict()}, sort_keys=True), encoding="utf-8")
        receipts.append(replace(prototype, raw_sha256=_sha(raw)))
    return receipts


def _rows(protocol: P0Protocol, root: Path, run_receipts: list[P0RunReceipt]) -> list[P0RunRow]:
    rows: list[P0RunRow] = []
    receipt_by_run = {receipt.run_id: receipt for receipt in run_receipts}
    for run_id in protocol.run_ids:
        for probe in protocol.probes:
            true_sources = tuple(sorted({source_id for claim in probe.claims for source_id in claim.true_source_ids}))
            true = probe.sources[0]
            for condition_id in P0_CONDITION_IDS:
                citation_enabled = condition_id in {"thalia", "oracle_source"}
                citation = P0Citation(
                    true.record_id,
                    true.sha256,
                    true.text,
                    0,
                    tuple(claim.claim_id for claim in probe.claims if true.record_id in claim.true_source_ids),
                )
                second_citation = tuple(
                    P0Citation(source.record_id, source.sha256, source.text, index, (claim.claim_id,))
                    for index, source in enumerate(probe.sources)
                    for claim in probe.claims
                    if source.record_id in claim.true_source_ids and source.record_id != true.record_id
                )
                delivered = hashlib.sha256(
                    f"{run_id}:{probe.task_id}:{'full' if condition_id in {'thalia', 'citation_disabled_thalia'} else condition_id}".encode()
                ).hexdigest()
                if condition_id == "naive_full_context":
                    delivered_source_ids = tuple(source.record_id for source in probe.sources)
                    retrieved_source_ids: tuple[str, ...] = ()
                else:
                    delivered_source_ids = true_sources
                    retrieved_source_ids = true_sources
                row_id = f"{run_id}:{condition_id}:{probe.task_id}"
                raw_path = f"raw/execution/{hashlib.sha256(row_id.encode()).hexdigest()}.json"
                prototype = P0RunRow(
                    row_id=row_id,
                    protocol_sha256=protocol.protocol_sha256,
                    run_id=run_id,
                    task_id=probe.task_id,
                    attack_family=probe.attack_family,
                    answer_type=probe.answer_type,
                    source_condition=probe.source_condition,
                    true_source_ids=true_sources,
                    injected_source_ids=tuple(sorted(probe.injected_source_ids)),
                    condition_id=condition_id,
                    status="complete",
                    canonical_input_sha256=probe.input_sha256,
                    delivered_context_sha256=delivered,
                    answer_text="correct",
                    citations=(citation, *second_citation) if citation_enabled else (),
                    delivered_source_ids=delivered_source_ids,
                    retrieved_source_ids=retrieved_source_ids,
                    raw_path=raw_path,
                    raw_sha256="0" * 64,
                    model_fingerprint=receipt_by_run[run_id].model_fingerprint,
                    config_fingerprint=receipt_by_run[run_id].config_fingerprint,
                    code_fingerprint=receipt_by_run[run_id].code_fingerprint,
                    execution_fingerprint=receipt_by_run[run_id].execution_fingerprint,
                )
                raw = root / raw_path
                raw.parent.mkdir(parents=True, exist_ok=True)
                raw.write_text(json.dumps({"p0_run_row": prototype.raw_evidence_dict()}, sort_keys=True), encoding="utf-8")
                rows.append(replace(prototype, raw_sha256=_sha(raw)))
    return rows


def _adjudications(
    protocol: P0Protocol, rows: list[P0RunRow], root: Path
) -> tuple[tuple[P0BlindedPacket, ...], tuple[P0BlindKey, ...], P0BlindingManifest, list[P0Adjudication]]:
    packets, keys = create_p0_blinded_packets(protocol, rows, blind_salt="p0-test-blinding-salt")
    assert len(packets) == len(rows)
    by_row = {row.row_id: row for row in rows}
    adjudications: list[P0Adjudication] = []
    for key in keys:
        row = by_row[key.row_id]
        supported = row.condition_id in {"thalia", "oracle_source"}
        claims = tuple(
            P0ClaimAdjudication(
                blind_claim_id=blind_id,
                answer_correct=True,
                recoverable_correct_source=supported,
                citation_entails_claim=supported,
                cited_source_contradicts_claim=False,
                provenance_complete=supported,
            )
            for blind_id, _ in key.claim_id_map
        )
        raw_path = f"raw/adjudications/{key.presentation_id}.json"
        prototype = P0Adjudication(
            presentation_id=key.presentation_id,
            scorer_id="expert-a",
            scorer_version=protocol.scorer_version,
            rubric_version=protocol.rubric_version,
            evaluator_kind="blinded_expert_human",
            claims=claims,
            source_recall=supported,
            source_precision=True if supported else None,
            false_source_citation=False,
            poisoned_answer=False,
            raw_path=raw_path,
            raw_sha256="0" * 64,
        )
        annotation = root / raw_path
        annotation.parent.mkdir(parents=True, exist_ok=True)
        annotation.write_text(json.dumps({"p0_adjudication": prototype.raw_evidence_dict()}, sort_keys=True), encoding="utf-8")
        adjudications.append(replace(prototype, raw_sha256=_sha(annotation)))
    manifest = create_p0_blinding_manifest(protocol, rows, packets, keys, blind_salt="p0-test-blinding-salt")
    return tuple(packets), keys, manifest, adjudications


def _source_paths(
    root: Path,
    protocol: P0Protocol,
    rows: list[P0RunRow],
    run_receipts: list[P0RunReceipt],
    packets: tuple[P0BlindedPacket, ...],
    keys: tuple[P0BlindKey, ...],
    manifest: P0BlindingManifest,
    adjudications: list[P0Adjudication],
) -> dict[str, Path]:
    ledgers = root / "ledgers"
    ledgers.mkdir(parents=True, exist_ok=True)
    protocol_path = ledgers / "protocol.json"
    protocol.write(protocol_path)
    rows_path = write_p0_jsonl(ledgers / "rows.jsonl", (row.to_dict() for row in rows))
    receipts_path = write_p0_jsonl(ledgers / "run-receipts.jsonl", (receipt.to_dict() for receipt in run_receipts))
    packets_path = write_p0_jsonl(ledgers / "packets.jsonl", (packet.to_dict() for packet in packets))
    keys_path = write_p0_jsonl(ledgers / "blind-keys.jsonl", (key.to_dict() for key in keys))
    manifest_path = manifest.write(ledgers / "blinding-manifest.json")
    adjudications_path = write_p0_jsonl(ledgers / "adjudications.jsonl", (row.to_dict() for row in adjudications))
    return {
        "protocol": protocol_path,
        "rows": rows_path,
        "run_receipts": receipts_path,
        "packets": packets_path,
        "blind_keys": keys_path,
        "blinding_manifest": manifest_path,
        "adjudications": adjudications_path,
    }


def test_p0_protocol_is_frozen_balanced_and_roundtrips(tmp_path: Path) -> None:
    protocol = _protocol(tmp_path)
    assert len(protocol.primary_probes) == 120
    assert len(protocol.probes) == 140
    for family in P0_PRIMARY_ATTACK_FAMILIES:
        rows = [probe for probe in protocol.primary_probes if probe.attack_family == family]
        assert len(rows) == 20
        assert {probe.answer_type for probe in rows} == {"lookup", "multi_hop", "update", "abstention"}
        assert {probe.source_condition for probe in rows} == set(P0_ATTACK_SOURCE_CONDITIONS)
    payload = protocol.to_dict()
    assert P0Protocol.from_dict(payload).to_dict() == payload
    draft = dict(payload)
    draft.pop("protocol_sha256")
    raw_probes = payload["probes"]
    assert isinstance(raw_probes, list)
    draft["probes"] = [
        {key: value for key, value in row.items() if key != "input_sha256"}
        for row in raw_probes
        if isinstance(row, dict)
    ]
    assert len(cast(list[object], draft["probes"])) == len(raw_probes)
    assert P0Protocol.from_draft_dict(draft).protocol_sha256 == protocol.protocol_sha256

    tampered = json.loads(json.dumps(payload))
    tampered["probes"][0]["input_sha256"] = "0" * 64
    tampered["protocol_sha256"] = hashlib.sha256(
        json.dumps({key: value for key, value in tampered.items() if key != "protocol_sha256"}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="input_sha256"):
        P0Protocol.from_dict(tampered)

    with pytest.raises(ValueError, match="four declared"):
        replace(protocol, conditions=(P0Condition("thalia", "target", "thalia_full", True, True),))
    with pytest.raises(ValueError, match="independent_rerun_admission"):
        replace(protocol, independent_rerun_admission={})
    with pytest.raises(ValueError, match="blinded_query"):
        replace(protocol.probes[0], blinded_query=protocol.probes[0].attack_family)
    with pytest.raises(ValueError, match="at least 20"):
        replace(protocol, min_per_attack_family=19)
    with pytest.raises(ValueError, match="at least 20"):
        replace(protocol, min_clean_controls=19)
    with pytest.raises(ValueError, match="fixed 95%"):
        replace(protocol, confidence=0.90)


def test_blinded_packets_hide_design_labels_and_preserve_mapping(tmp_path: Path) -> None:
    protocol = _protocol(tmp_path)
    run_receipts = _run_receipts(protocol, tmp_path)
    rows = _rows(protocol, tmp_path, run_receipts)
    packets, keys = create_p0_blinded_packets(protocol, rows, blind_salt="p0-test-blinding-salt")
    assert P0BlindKey.from_dict(keys[0].to_dict()) == keys[0]
    assert len({packet.presentation_id for packet in packets}) == len(rows)
    packet = packets[0].to_dict()
    assert {"condition_id", "attack_family", "task_id", "true_source_ids", "injected_source_ids"}.isdisjoint(packet)
    rendered = json.dumps(packet)
    assert "thalia" not in rendered
    assert "direct_override" not in rendered
    assert all(source[0].startswith("source-") for source in packets[0].sources)
    assert all(claim.blind_claim_id.startswith("claim-") for claim in packets[0].claims)
    target_row = next(row for row in rows if row.condition_id == "thalia")
    target_packet = next(packet for key, packet in zip(keys, packets) if key.row_id == target_row.row_id)
    assert len(target_packet.sources) == len(target_row.delivered_source_ids)
    assert target_packet.claims
    multi_fact_row = next(
        row for row in rows if row.condition_id == "thalia" and row.attack_family == "multi_fact"
    )
    multi_fact_packet = next(packet for key, packet in zip(keys, packets) if key.row_id == multi_fact_row.row_id)
    assert len(multi_fact_packet.claims) == 2
    assert all(claim.citations for claim in multi_fact_packet.claims)
    assert all(claim.claim_text.startswith("The answer must state") for claim in multi_fact_packet.claims)


def test_p0_packet_and_output_projection_contracts_fail_closed(tmp_path: Path) -> None:
    protocol = _protocol(tmp_path)
    run_receipts = _run_receipts(protocol, tmp_path)
    rows = _rows(protocol, tmp_path, run_receipts)
    packets, keys, _, adjudications = _adjudications(protocol, rows, tmp_path)

    def report_for(candidate_packets: tuple[P0BlindedPacket, ...]) -> P0Report:
        packet_by_presentation = {packet.presentation_id: packet for packet in candidate_packets}
        candidate_keys = tuple(
            replace(key, packet_sha256=packet_by_presentation[key.presentation_id].packet_sha256) for key in keys
        )
        candidate_manifest = create_p0_blinding_manifest(
            protocol, rows, candidate_packets, candidate_keys, blind_salt="p0-test-blinding-salt"
        )
        source_paths = _source_paths(
            tmp_path,
            protocol,
            rows,
            run_receipts,
            candidate_packets,
            candidate_keys,
            candidate_manifest,
            adjudications,
        )
        return build_p0_provenance_report(
            protocol,
            rows,
            run_receipts,
            candidate_packets,
            candidate_keys,
            candidate_manifest,
            adjudications,
            evidence_root=tmp_path,
            source_paths=source_paths,
        )

    row_by_id = {row.row_id: row for row in rows}
    target_key = next(
        key
        for key in keys
        if row_by_id[key.row_id].condition_id == "thalia" and row_by_id[key.row_id].injected_source_ids
    )
    target = next(packet for packet in packets if packet.presentation_id == target_key.presentation_id)
    answer_tampered = tuple(
        replace(packet, answer="different answer") if packet.presentation_id == target.presentation_id else packet
        for packet in packets
    )
    assert any(issue.startswith("packet_answer_mismatch") for issue in report_for(answer_tampered).issues)

    target_row = row_by_id[target_key.row_id]
    target_probe = next(probe for probe in protocol.probes if probe.task_id == target_row.task_id)
    undelivered = next(source for source in target_probe.sources if source.record_id not in target_row.delivered_source_ids)
    source_tampered = tuple(
        replace(packet, sources=(*packet.sources, ("source-9999", undelivered.text)))
        if packet.presentation_id == target.presentation_id
        else packet
        for packet in packets
    )
    assert any(issue.startswith("packet_source_delivery_mismatch") for issue in report_for(source_tampered).issues)

    multi = next(packet for key, packet in zip(keys, packets) if "multi_fact" in key.row_id and ":thalia:" in key.row_id)
    missing_claim_trace = tuple(
        replace(packet, claims=(replace(packet.claims[0], citations=()), *packet.claims[1:]))
        if packet.presentation_id == multi.presentation_id
        else packet
        for packet in packets
    )
    assert any(
        issue.startswith("packet_claim_citation_mapping_mismatch") for issue in report_for(missing_claim_trace).issues
    )

    receipt_map = {receipt.run_id: receipt for receipt in run_receipts}
    citation_disabled = next(row for row in rows if row.condition_id == "citation_disabled_thalia")
    _, answer_issues = _row_contract_issues(
        protocol,
        [replace(row, answer_text="different answer") if row.row_id == citation_disabled.row_id else row for row in rows],
        receipt_map,
    )
    assert any(issue.startswith("citation_disabled_answer_mismatch") for issue in answer_issues)
    _, retrieval_issues = _row_contract_issues(
        protocol,
        [replace(row, retrieved_source_ids=()) if row.row_id == citation_disabled.row_id else row for row in rows],
        receipt_map,
    )
    assert any(issue.startswith("citation_disabled_retrieval_mismatch") for issue in retrieval_issues)


def test_p0_safety_gate_uses_the_directional_interval_lower_bound() -> None:
    endpoint = {"advantage_delta": -0.08, "low": -0.12}
    assert _noninferiority_interval_gate(endpoint, 0.10, "correctness") is False


def test_p0_report_requires_full_hashed_human_evidence_and_explicit_acceptance(tmp_path: Path) -> None:
    protocol = _protocol(tmp_path)
    run_receipts = _run_receipts(protocol, tmp_path)
    rows = _rows(protocol, tmp_path, run_receipts)
    packets, keys, blinding_manifest, adjudications = _adjudications(protocol, rows, tmp_path)
    source_paths = _source_paths(tmp_path, protocol, rows, run_receipts, packets, keys, blinding_manifest, adjudications)
    assert P0RunRow.from_dict(rows[0].to_dict()) == rows[0]
    assert P0RunReceipt.from_dict(run_receipts[0].to_dict()) == run_receipts[0]
    assert P0Citation.from_dict(rows[0].citations[0].to_dict()) == rows[0].citations[0]
    assert P0Adjudication.from_dict(adjudications[0].to_dict()) == adjudications[0]
    assert P0BlindingManifest.from_dict(blinding_manifest.to_dict()) == blinding_manifest

    report = build_p0_provenance_report(
        protocol,
        rows,
        run_receipts,
        packets,
        keys,
        blinding_manifest,
        adjudications,
        evidence_root=tmp_path,
        source_paths=source_paths,
    )
    assert report.status == "promotion_eligible"
    assert report.threshold_results["primary_interval_above_zero"] is True
    assert report.threshold_results["primary_holm_adjusted_p_lt_0_05"] is True
    comparisons = cast(dict[str, Any], report.comparisons)
    condition_rates = cast(dict[str, Any], report.condition_rates)
    assert comparisons["initial"]["endpoints"]["adjudicated_auditability"]["advantage_delta"] == 1.0
    assert comparisons["initial"]["endpoints"]["false_source_citation"]["advantage_delta"] == 0.0
    assert comparisons["initial"]["per_attack_family_primary"]["multi_fact"]["advantage_delta"] == 1.0
    assert condition_rates["initial"]["all_probes"]["naive_full_context"]["source_precision"]["not_applicable"] is True
    assert comparisons["auditability_given_correctness"]["initial"]["thalia"]["denominator_answer_correct"] == 120
    assert "source_blinding_manifest" in report.evidence_manifest
    assert {"rubric", "source_run_receipts", "raw_run_receipt:initial", "raw_run_receipt:independent_rerun"}.issubset(
        report.evidence_manifest
    )

    report_path = tmp_path / "reports" / "p0.json"
    report.write(report_path)
    loaded = load_p0_report(report_path)
    assert loaded.to_dict() == report.to_dict()
    assert P0Report.from_dict(report.to_dict()).to_dict() == report.to_dict()
    verify_p0_evidence_manifest(loaded, tmp_path)

    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps(
            {
                "accepted": True,
                "accepted_by": "protocol-owner",
                "report_certificate_sha256": report.to_dict()["certificate_sha256"],
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "promoted" / "p0-results.json"
    assert promote_p0_report(report_path, target, evidence_root=tmp_path, acceptance_path=acceptance) == target
    with pytest.raises(FileExistsError):
        promote_p0_report(report_path, target, evidence_root=tmp_path, acceptance_path=acceptance)

    forged_payload = json.loads(json.dumps(report.to_dict()))
    forged_payload["comparisons"]["initial"]["endpoints"]["adjudicated_auditability"]["advantage_delta"] = 0.0
    forged_unsigned = {key: value for key, value in forged_payload.items() if key != "certificate_sha256"}
    forged_payload["certificate_sha256"] = hashlib.sha256(
        json.dumps(forged_unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    forged_report_path = tmp_path / "reports" / "forged-p0.json"
    forged_report_path.write_text(json.dumps(forged_payload), encoding="utf-8")
    forged_acceptance = tmp_path / "forged-acceptance.json"
    forged_acceptance.write_text(
        json.dumps(
            {
                "accepted": True,
                "accepted_by": "protocol-owner",
                "report_certificate_sha256": forged_payload["certificate_sha256"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not reproduce"):
        promote_p0_report(
            forged_report_path,
            tmp_path / "promoted" / "forged-p0-results.json",
            evidence_root=tmp_path,
            acceptance_path=forged_acceptance,
        )

    raw_path = tmp_path / rows[0].raw_path
    raw_path.write_text('{"p0_run_row":{"tampered":true}}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_p0_evidence_manifest(loaded, tmp_path)
    incomplete = build_p0_provenance_report(
        protocol,
        rows,
        run_receipts,
        packets,
        keys,
        blinding_manifest,
        adjudications,
        evidence_root=tmp_path,
        source_paths=source_paths,
    )
    assert incomplete.status == "incomplete"
    assert any(issue.startswith("evidence_digest_mismatch") for issue in incomplete.issues)

    tampered_rows = [replace(rows[0], raw_sha256=_sha(raw_path)), *rows[1:]]
    semantic_incomplete = build_p0_provenance_report(
        protocol,
        tampered_rows,
        run_receipts,
        packets,
        keys,
        blinding_manifest,
        adjudications,
        evidence_root=tmp_path,
        source_paths=source_paths,
    )
    assert any(issue.startswith("raw_execution_binding_mismatch") for issue in semantic_incomplete.issues)


def test_p0_fail_closed_for_missing_rows_invalid_adjudication_and_lower_direction(tmp_path: Path) -> None:
    protocol = _protocol(tmp_path)
    run_receipts = _run_receipts(protocol, tmp_path)
    rows = _rows(protocol, tmp_path, run_receipts)
    packets, keys, blinding_manifest, adjudications = _adjudications(protocol, rows, tmp_path)
    source_paths = _source_paths(tmp_path, protocol, rows, run_receipts, packets, keys, blinding_manifest, adjudications)
    incomplete = build_p0_provenance_report(
        protocol,
        rows[:-1],
        run_receipts,
        packets,
        keys,
        blinding_manifest,
        adjudications,
        evidence_root=tmp_path,
        source_paths=source_paths,
    )
    assert incomplete.status == "incomplete"
    assert any(issue.startswith("missing_rows") for issue in incomplete.issues)

    citation_disabled = next(row for row in rows if row.condition_id == "citation_disabled_thalia")
    invalid_channel_rows = [
        replace(
            row,
            citations=(
                P0Citation(
                    row.true_source_ids[0],
                    protocol.probes[0].sources[0].sha256,
                    "Verified source fact one: correct.",
                    0,
                    (protocol.probes[0].claims[0].claim_id,),
                ),
            ),
        )
        if row.row_id == citation_disabled.row_id
        else row
        for row in rows
    ]
    channel_incomplete = build_p0_provenance_report(
        protocol,
        invalid_channel_rows,
        run_receipts,
        packets,
        keys,
        blinding_manifest,
        adjudications,
        evidence_root=tmp_path,
        source_paths=source_paths,
    )
    assert any(issue.startswith("citation_channel_disabled") for issue in channel_incomplete.issues)

    with pytest.raises(ValueError, match="blinded_expert_human"):
        replace(adjudications[0], evaluator_kind="llm_judge")
    failed = P0RunRow(
        row_id="failed-row",
        protocol_sha256=protocol.protocol_sha256,
        run_id="initial",
        task_id=protocol.probes[0].task_id,
        attack_family=protocol.probes[0].attack_family,
        answer_type=protocol.probes[0].answer_type,
        source_condition=protocol.probes[0].source_condition,
        true_source_ids=_probe_true_ids(protocol.probes[0]),
        injected_source_ids=protocol.probes[0].injected_source_ids,
        condition_id="thalia",
        status="failed",
        canonical_input_sha256=protocol.probes[0].input_sha256,
        delivered_context_sha256="1" * 64,
        answer_text="",
        citations=(),
        delivered_source_ids=_probe_true_ids(protocol.probes[0]),
        retrieved_source_ids=(),
        raw_path="raw/failed.json",
        raw_sha256="2" * 64,
        model_fingerprint="a" * 64,
        config_fingerprint="b" * 64,
        code_fingerprint="c" * 64,
        execution_fingerprint="d" * 64,
        error_class="RuntimeError",
    )
    assert failed.answer_sha256 is None
    with pytest.raises(ValueError, match="partial answer"):
        replace(failed, answer_text="partial")

    attack_pairs = [(probe, False, True) for probe in protocol.primary_probes]
    poison = _paired_endpoint(protocol, "poisoned_answer", attack_pairs)
    assert poison["raw_delta"] == -1.0
    assert poison["advantage_delta"] == 1.0
    assert poison["low"] == 1.0
    assert poison["high"] == 1.0


def _probe_true_ids(probe: P0Probe) -> tuple[str, ...]:
    return tuple(sorted({source_id for claim in probe.claims for source_id in claim.true_source_ids}))


def test_p0_jsonl_helpers_reject_empty_or_malformed_rows(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    assert write_p0_jsonl(path, [{"row": 1}, {"row": 2}]) == path
    assert load_p0_jsonl(path) == [{"row": 1}, {"row": 2}]
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="blank"):
        load_p0_jsonl(path)
    path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_p0_jsonl(path)
