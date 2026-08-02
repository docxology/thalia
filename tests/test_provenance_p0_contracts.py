"""High-level fail-closed contract matrices for the P0 provenance tier.

These cases deliberately use the real frozen fixture and retained files from
``test_provenance_p0``.  They exercise the boundaries that sit between typed
records: row-to-receipt binding, scorer packet/key binding, human-label
restoration, and retained evidence/promotion checks.  They do not use mocks or
replace any call boundary.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.evaluation.provenance_p0 import (
    P0Citation,
    P0Report,
    _adjudication_contract_issues,
    _evidence_manifest,
    _evidence_manifest_path,
    _execution_receipts_are_distinct,
    _manifest_file,
    _packet_contract_issues,
    _resolve_evidence_path,
    _row_contract_issues,
    _run_receipt_contract_issues,
    _source_ledger_manifest,
    load_p0_report,
    promote_p0_report,
    verify_p0_evidence_manifest,
)
from tests.test_provenance_p0 import _adjudications, _protocol, _rows, _run_receipts, _sha, _source_paths


def _material(tmp_path: Path):
    """Build one real complete P0 fixture and its retained evidence files."""
    protocol = _protocol(tmp_path)
    receipts = _run_receipts(protocol, tmp_path)
    rows = _rows(protocol, tmp_path, receipts)
    packets, keys, manifest, adjudications = _adjudications(protocol, rows, tmp_path)
    paths = _source_paths(tmp_path, protocol, rows, receipts, packets, keys, manifest, adjudications)
    receipt_map = {receipt.run_id: receipt for receipt in receipts}
    row_map, issues = _row_contract_issues(protocol, rows, receipt_map)
    assert not issues
    return protocol, receipts, rows, packets, keys, manifest, adjudications, paths, receipt_map, row_map


def _replace_row(rows, original, replacement):
    return [replacement if row.row_id == original.row_id else row for row in rows]


def _has(issues: list[str], prefix: str) -> bool:
    return any(issue.startswith(prefix) for issue in issues)


def test_row_and_run_receipt_contract_matrix(tmp_path: Path) -> None:
    """Every retained execution identity is checked before analysis proceeds."""
    protocol, receipts, rows, _, _, _, _, _, receipt_map, _ = _material(tmp_path)
    initial, rerun = receipts
    base = next(row for row in rows if row.run_id == "initial" and row.condition_id == "thalia")
    same_task_other_condition = next(
        row
        for row in rows
        if row.run_id == base.run_id and row.task_id == base.task_id and row.condition_id != base.condition_id
    )
    probe = next(probe for probe in protocol.probes if probe.task_id == base.task_id)
    false_source = next(source for source in probe.sources if source.role == "adversarial")
    false_citation = P0Citation(
        false_source.record_id,
        false_source.sha256,
        false_source.text,
        probe.sources.index(false_source),
        (probe.claims[0].claim_id,),
    )
    disabled = next(
        row
        for row in rows
        if row.run_id == base.run_id
        and row.task_id == base.task_id
        and row.condition_id == "citation_disabled_thalia"
    )
    naive = next(row for row in rows if row.condition_id == "naive_full_context" and row.task_id == base.task_id)
    oracle = next(row for row in rows if row.condition_id == "oracle_source" and row.task_id == base.task_id)

    receipt_cases = (
        ([initial, initial], "duplicate_run_receipt:"),
        ([initial, replace(rerun, receipt_id=initial.receipt_id)], "duplicate_run_receipt_id:"),
        ([initial, replace(rerun, raw_path=initial.raw_path)], "duplicate_run_receipt_raw_path:"),
        ([initial, replace(rerun, protocol_sha256="f" * 64)], "run_receipt_protocol_mismatch:"),
        ([initial, replace(rerun, run_id="other")], "unknown_run_receipt:"),
        ([initial], "run_receipt_scope_mismatch"),
    )
    for candidate, expected in receipt_cases:
        _, issues = _run_receipt_contract_issues(protocol, candidate)
        assert _has(issues, expected)
    assert not _execution_receipts_are_distinct({"initial": initial})

    changed_fingerprints = replace(
        base,
        execution_fingerprint="e" * 64,
        model_fingerprint="f" * 64,
        config_fingerprint="a" * 64,
        code_fingerprint="b" * 64,
    )
    failed = replace(
        base,
        status="failed",
        answer_text="",
        citations=(),
        retrieved_source_ids=(),
        error_class="RuntimeError",
    )
    row_cases = (
        ([*rows, base], receipt_map, "duplicate_row:"),
        (_replace_row(rows, same_task_other_condition, replace(same_task_other_condition, row_id=base.row_id)), receipt_map, "duplicate_row_id:"),
        (_replace_row(rows, same_task_other_condition, replace(same_task_other_condition, raw_path=base.raw_path)), receipt_map, "duplicate_raw_path:"),
        (_replace_row(rows, base, replace(base, protocol_sha256="f" * 64)), receipt_map, "protocol_sha_mismatch:"),
        (_replace_row(rows, base, replace(base, task_id="unfrozen-task")), receipt_map, "unknown_task:"),
        (_replace_row(rows, base, replace(base, run_id="unregistered")), receipt_map, "unknown_run:"),
        (_replace_row(rows, base, changed_fingerprints), receipt_map, "row_execution_receipt_mismatch:"),
        (_replace_row(rows, base, replace(base, condition_id="unregistered-condition")), receipt_map, "unknown_condition:"),
        (_replace_row(rows, base, replace(base, attack_family="changed-family")), receipt_map, "task_metadata_mismatch:"),
        (_replace_row(rows, base, replace(base, true_source_ids=("different",))), receipt_map, "true_source_mismatch:"),
        (_replace_row(rows, base, replace(base, injected_source_ids=())), receipt_map, "injected_source_mismatch:"),
        (_replace_row(rows, base, replace(base, canonical_input_sha256="e" * 64)), receipt_map, "canonical_input_mismatch:"),
        (_replace_row(rows, base, replace(base, delivered_source_ids=("unknown",))), receipt_map, "unknown_delivered_source:"),
        (_replace_row(rows, base, replace(base, retrieved_source_ids=("unknown",))), receipt_map, "unknown_retrieved_source:"),
        (_replace_row(rows, base, replace(base, delivered_source_ids=(), retrieved_source_ids=base.true_source_ids)), receipt_map, "retrieved_source_not_delivered:"),
        (_replace_row(rows, naive, replace(naive, delivered_source_ids=naive.true_source_ids)), receipt_map, "naive_delivery_not_full_context:"),
        (_replace_row(rows, oracle, replace(oracle, delivered_source_ids=tuple(source.record_id for source in probe.sources))), receipt_map, "oracle_delivery_not_true_source_only:"),
        (_replace_row(rows, base, replace(base, citations=(replace(base.citations[0], source_id="unknown"),))), receipt_map, "unknown_citation_source:"),
        (_replace_row(rows, base, replace(base, citations=(replace(base.citations[0], source_record_sha256="e" * 64),))), receipt_map, "citation_source_hash_mismatch:"),
        (_replace_row(rows, base, replace(base, citations=(replace(base.citations[0], source_index=1),))), receipt_map, "citation_source_index_mismatch:"),
        (_replace_row(rows, base, replace(base, citations=(replace(base.citations[0], excerpt="not a source span"),))), receipt_map, "citation_excerpt_not_in_source:"),
        (_replace_row(rows, base, replace(base, citations=(false_citation,))), receipt_map, "citation_source_not_delivered:"),
        (_replace_row(rows, base, replace(base, citations=(replace(base.citations[0], claim_ids=("unknown-claim",)),))), receipt_map, "citation_claim_unknown:"),
        ([*rows, replace(base, row_id="unexpected-row", task_id="unfrozen-task")], receipt_map, "unexpected_rows:"),
        (_replace_row(rows, base, failed), receipt_map, "failed_row:"),
        (_replace_row(rows, disabled, replace(disabled, delivered_context_sha256="d" * 64)), receipt_map, "citation_disabled_delivery_mismatch:"),
        (_replace_row(rows, disabled, replace(disabled, delivered_source_ids=())), receipt_map, "citation_disabled_source_delivery_mismatch:"),
        (_replace_row(rows, disabled, replace(disabled, model_fingerprint="c" * 64)), receipt_map, "citation_disabled_model_mismatch:"),
        (_replace_row(rows, disabled, replace(disabled, config_fingerprint="d" * 64)), receipt_map, "citation_disabled_config_mismatch:"),
        (_replace_row(rows, disabled, replace(disabled, code_fingerprint="e" * 64)), receipt_map, "citation_disabled_code_mismatch:"),
        (_replace_row(rows, base, replace(base, execution_fingerprint="d" * 64)), receipt_map, "run_execution_fingerprint_not_constant:"),
        (rows, {"initial": initial}, "independent_rerun_receipts_not_distinct"),
    )
    for candidate_rows, candidate_receipts, expected in row_cases:
        _, issues = _row_contract_issues(protocol, candidate_rows, candidate_receipts)
        assert _has(issues, expected)


def test_packet_and_adjudication_contract_matrix(tmp_path: Path) -> None:
    """Packet/key and blinded-human-label boundaries reject typed tampering."""
    protocol, _, rows, packets, keys, manifest, adjudications, _, _, row_map = _material(tmp_path)
    packet_by_id = {packet.presentation_id: packet for packet in packets}
    row_by_id = {row.row_id: row for row in rows}
    target_key = next(
        key
        for key in keys
        if row_by_id[key.row_id].condition_id == "thalia" and row_by_id[key.row_id].attack_family != "multi_fact"
    )
    target_packet = packet_by_id[target_key.presentation_id]
    target_row = row_by_id[target_key.row_id]
    target_probe = next(probe for probe in protocol.probes if probe.task_id == target_row.task_id)
    naive_key = next(key for key in keys if row_by_id[key.row_id].condition_id == "naive_full_context")
    naive_packet = packet_by_id[naive_key.presentation_id]
    multi_key = next(key for key in keys if row_by_id[key.row_id].attack_family == "multi_fact")
    multi_adjudication = next(item for item in adjudications if item.presentation_id == multi_key.presentation_id)

    bad_manifest = replace(
        manifest,
        protocol_sha256="a" * 64,
        blinding_version="other-version",
        complete_row_fingerprint="b" * 64,
        packet_fingerprint="c" * 64,
        ordered_packet_fingerprint="d" * 64,
        blind_key_fingerprint="e" * 64,
    )
    assert {
        "blinding_manifest_protocol_mismatch",
        "blinding_manifest_version_mismatch",
        "blinding_manifest_row_binding_mismatch",
        "blinding_manifest_packet_binding_mismatch",
        "blinding_manifest_packet_order_mismatch",
        "blinding_manifest_key_binding_mismatch",
    }.issubset(_packet_contract_issues(protocol, row_map, packets, keys, bad_manifest))

    unblinded = replace(
        naive_packet,
        sources=tuple((f"plain-{index}", text) for index, (_, text) in enumerate(naive_packet.sources)),
    )
    unknown_source_text = "not a frozen source record"
    cited_alias = target_packet.claims[0].citations[0][0]
    unknown_source_packet = replace(
        target_packet,
        sources=tuple(
            (alias, unknown_source_text if alias == cited_alias else text)
            for alias, text in target_packet.sources
        ),
        claims=(replace(target_packet.claims[0], citations=((cited_alias, unknown_source_text),)),),
    )
    packet_cases = (
        ([*packets, target_packet], keys, manifest, "duplicate_packet:"),
        (packets, (*keys, target_key), manifest, "duplicate_presentation:"),
        (packets[:-1], keys, manifest, "packet_key_scope_mismatch"),
        (packets, (*keys, replace(keys[1], presentation_id="p0-extra", row_id=keys[0].row_id)), manifest, "packet_key_rows_not_one_to_one"),
        (packets, tuple(replace(key, packet_sha256="f" * 64) if key == target_key else key for key in keys), manifest, "packet_digest_mismatch:"),
        (tuple(replace(packet, query=f"{packet.query} {target_probe.task_id}") if packet.presentation_id == target_packet.presentation_id else packet for packet in packets), keys, manifest, "packet_label_leak:"),
        (tuple(unblinded if packet.presentation_id == unblinded.presentation_id else packet for packet in packets), keys, manifest, "packet_unblinded_source_id:"),
        (tuple(replace(packet, rubric_version="wrong-rubric") if packet.presentation_id == target_packet.presentation_id else packet for packet in packets), keys, manifest, "packet_rubric_version_mismatch:"),
        (tuple(unknown_source_packet if packet.presentation_id == target_packet.presentation_id else packet for packet in packets), keys, manifest, "packet_claim_unknown_source:"),
        (tuple(replace(packet, claims=(replace(packet.claims[0], claim_text="changed claim"),)) if packet.presentation_id == target_packet.presentation_id else packet for packet in packets), keys, manifest, "packet_claim_text_mismatch:"),
        (packets, tuple(replace(key, claim_id_map=(("claim-9999", key.claim_id_map[0][1]),)) if key == target_key else key for key in keys), manifest, "packet_claim_key_mismatch:"),
        (packets, tuple(replace(key, claim_id_map=((key.claim_id_map[0][0], "unknown-claim"),)) if key == target_key else key for key in keys), manifest, "packet_unknown_claim:"),
    )
    for candidate_packets, candidate_keys, candidate_manifest, expected in packet_cases:
        issues = _packet_contract_issues(protocol, row_map, candidate_packets, candidate_keys, candidate_manifest)
        assert _has(issues, expected)

    unknown_task_rows = dict(row_map)
    unknown_task_rows[(target_row.run_id, target_row.task_id, target_row.condition_id)] = replace(
        target_row, task_id="unfrozen-task"
    )
    assert _has(_packet_contract_issues(protocol, unknown_task_rows, packets, keys, manifest), "packet_unknown_task:")
    unknown_delivery_rows = dict(row_map)
    unknown_delivery_rows[(target_row.run_id, target_row.task_id, target_row.condition_id)] = replace(
        target_row, delivered_source_ids=("unknown",)
    )
    assert _has(
        _packet_contract_issues(protocol, unknown_delivery_rows, packets, keys, manifest),
        "packet_row_unknown_delivered_source:",
    )

    adjudication_cases = (
        ((*keys, target_key), adjudications, "duplicate_presentation:"),
        (tuple(replace(key, row_id="unknown-row") if key == target_key else key for key in keys), adjudications, "blind_key_unknown_row:"),
        (
            (*keys, replace(keys[1], presentation_id="p0-extra", row_id=keys[0].row_id)),
            adjudications,
            "blind_key_rows_not_one_to_one",
        ),
        (keys[:-1], adjudications, "blind_key_incomplete"),
        (keys, (*adjudications, adjudications[0]), "duplicate_adjudication:"),
        (keys, adjudications[:-1], "adjudication_incomplete"),
        (keys, tuple(replace(item, scorer_version="other") if item.presentation_id == target_key.presentation_id else item for item in adjudications), "scorer_version_mismatch:"),
        (keys, tuple(replace(item, rubric_version="other") if item.presentation_id == target_key.presentation_id else item for item in adjudications), "rubric_version_mismatch:"),
        (keys, tuple(replace(item, claims=(item.claims[0],)) if item.presentation_id == multi_adjudication.presentation_id else item for item in adjudications), "claim_adjudication_mismatch:"),
        (keys, tuple(replace(item, source_recall=not item.source_recall) if item.presentation_id == target_key.presentation_id else item for item in adjudications), "source_recall_raw_mismatch:"),
        (keys, tuple(replace(item, source_precision=False) if item.presentation_id == target_key.presentation_id else item for item in adjudications), "source_precision_raw_mismatch:"),
        (keys, tuple(replace(item, false_source_citation=not item.false_source_citation) if item.presentation_id == target_key.presentation_id else item for item in adjudications), "false_source_citation_raw_mismatch:"),
    )
    for candidate_keys, candidate_adjudications, expected in adjudication_cases:
        _, issues = _adjudication_contract_issues(protocol, row_map, candidate_keys, candidate_adjudications)
        assert _has(issues, expected)
    _, unknown_task_issues = _adjudication_contract_issues(protocol, unknown_task_rows, keys, adjudications)
    assert _has(unknown_task_issues, "adjudication_unknown_task:")


def test_retained_evidence_and_promotion_failure_matrix(tmp_path: Path) -> None:
    """Evidence roots, ledgers, manifest entries, and promotion stay fail-closed."""
    protocol, receipts, rows, packets, keys, manifest, adjudications, paths, _, _ = _material(tmp_path)
    root = tmp_path
    missing_root = root / "missing-root"

    assert _source_ledger_manifest(protocol, rows, receipts, packets, keys, manifest, adjudications, source_paths=paths, evidence_root=None)[1] == ["evidence_root_not_supplied"]
    assert _source_ledger_manifest(protocol, rows, receipts, packets, keys, manifest, adjudications, source_paths=paths, evidence_root=missing_root)[1] == ["evidence_root_missing"]
    assert _source_ledger_manifest(protocol, rows, receipts, packets, keys, manifest, adjudications, source_paths=None, evidence_root=root)[1] == ["source_ledger_paths_not_supplied"]
    assert _has(
        _source_ledger_manifest(
            protocol,
            rows,
            receipts,
            packets,
            keys,
            manifest,
            adjudications,
            source_paths={"protocol": paths["protocol"]},
            evidence_root=root,
        )[1],
        "source_ledger_paths_missing:",
    )
    unreadable_paths = dict(paths)
    unreadable_paths["rows"] = root / "does-not-exist.jsonl"
    assert _has(
        _source_ledger_manifest(protocol, rows, receipts, packets, keys, manifest, adjudications, source_paths=unreadable_paths, evidence_root=root)[1],
        "source_ledger_unreadable:rows",
    )
    invalid_rows = root / "ledgers" / "invalid-rows.jsonl"
    invalid_rows.write_text("not-json\n", encoding="utf-8")
    invalid_paths = dict(paths)
    invalid_paths["rows"] = invalid_rows
    assert _has(
        _source_ledger_manifest(protocol, rows, receipts, packets, keys, manifest, adjudications, source_paths=invalid_paths, evidence_root=root)[1],
        "source_ledger_invalid:rows",
    )

    assert _evidence_manifest(protocol, rows, receipts, adjudications, None)[1] == ["evidence_root_not_supplied"]
    assert _evidence_manifest(protocol, rows, receipts, adjudications, missing_root)[1] == ["evidence_root_missing"]
    row = rows[0]
    raw_path = root / row.raw_path
    raw_path.write_text("not-json\n", encoding="utf-8")
    malformed_row = replace(row, raw_sha256=_sha(raw_path))
    assert _has(_evidence_manifest(protocol, [malformed_row], (), (), root)[1], "raw_execution_invalid:")
    raw_path.write_text(json.dumps({"p0_run_row": {}}), encoding="utf-8")
    mismatched_row = replace(row, raw_sha256=_sha(raw_path))
    assert _has(_evidence_manifest(protocol, [mismatched_row], (), (), root)[1], "raw_execution_binding_mismatch:")

    receipt = receipts[0]
    receipt_path = root / receipt.raw_path
    receipt_path.write_text("not-json\n", encoding="utf-8")
    malformed_receipt = replace(receipt, raw_sha256=_sha(receipt_path))
    assert _has(_evidence_manifest(protocol, (), [malformed_receipt], (), root)[1], "raw_run_receipt_invalid:")
    adjudication = adjudications[0]
    adjudication_path = root / adjudication.raw_path
    adjudication_path.write_text("not-json\n", encoding="utf-8")
    malformed_adjudication = replace(adjudication, raw_sha256=_sha(adjudication_path))
    assert _has(_evidence_manifest(protocol, (), (), [malformed_adjudication], root)[1], "raw_adjudication_invalid:")

    evidence_dir = root / "manifest-root"
    evidence_dir.mkdir()
    inside = evidence_dir / "inside.txt"
    inside.write_text("inside", encoding="utf-8")
    issues: list[str] = []
    _manifest_file(evidence_dir, entry_name="missing", relative="missing.txt", expected_sha256="a" * 64, issues=issues)
    _manifest_file(evidence_dir, entry_name="digest", relative="inside.txt", expected_sha256="a" * 64, issues=issues)
    _manifest_file(evidence_dir, entry_name="size", relative="inside.txt", expected_sha256=_sha(inside), expected_size=99, issues=issues)
    outside = root / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (evidence_dir / "escape").symlink_to(outside)
    _manifest_file(evidence_dir, entry_name="outside", relative="escape", expected_sha256=_sha(outside), issues=issues)
    assert {"evidence_missing:missing", "evidence_digest_mismatch:digest", "evidence_size_mismatch:size", "evidence_path_outside_root:outside"}.issubset(issues)
    assert _resolve_evidence_path(evidence_dir, "inside.txt", "inside")[0] == inside.resolve()
    with pytest.raises(ValueError, match="inside evidence_root"):
        _resolve_evidence_path(evidence_dir, outside, "outside")

    incomplete = P0Report(
        protocol_id="p0-test",
        status="incomplete",
        accounting={},
        comparisons={},
        condition_rates={},
        threshold_results={},
        evidence_manifest={},
        issues=("not-run",),
        provenance={},
    )
    report_path = root / "reports" / "incomplete.json"
    incomplete.write(report_path)
    assert load_p0_report(report_path).status == "incomplete"
    with pytest.raises(ValueError, match="only a promotion-eligible"):
        promote_p0_report(report_path, root / "promoted.json", evidence_root=root, acceptance_path=root / "missing.json")
    with pytest.raises(ValueError, match="no retained evidence"):
        verify_p0_evidence_manifest(incomplete, root)
    with pytest.raises(ValueError, match="missing required source ledger"):
        _evidence_manifest_path(incomplete, root, "source_rows")
