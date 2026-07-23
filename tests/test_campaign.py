"""Zero-mock tests for campaign selection, checkpointing, and promotion safety."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.compiler.metrics import EvalExample
from src.evaluation.campaign import (
    CampaignCheckpoint,
    CampaignReport,
    CampaignRow,
    CampaignSpec,
    CampaignTier,
    load_campaign_report,
    promote_campaign_report,
    run_campaign,
    select_nested_cohort,
    select_nested_cohorts,
)
from src.module import ExtractiveLM
from src.signatures import TaskCategory


def _examples() -> list[EvalExample]:
    rows: list[EvalExample] = []
    categories = (TaskCategory.SINGLE_SESSION, TaskCategory.PREFERENCE, TaskCategory.TEMPORAL)
    for index in range(9):
        category = categories[index % len(categories)]
        rows.append(
            EvalExample(
                session_history=f"User: fact {index} is value {index}.",
                query=f"What is fact {index}?",
                expected_answer=f"fact {index} is value {index}",
                expected_source_indices=(0,),
                task_category=category,
                example_id=f"q-{index}",
                stratum=category.value,
            )
        )
    return rows


def _spec(tmp_path: Path, *tiers: CampaignTier) -> CampaignSpec:
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text("[]\n", encoding="utf-8")
    return CampaignSpec(
        campaign_id="test-campaign",
        benchmark_path=benchmark,
        tiers=tuple(tiers),
        # The production campaign keeps a 5 GiB safety floor; unit tests use
        # real temporary files and only need to assert campaign behavior.
        min_free_bytes=1,
    )


def test_nested_cohort_is_stable_balanced_and_prefix_nested():
    examples = _examples()
    first = select_nested_cohort(examples, 5, selection_salt="salt")
    second = select_nested_cohort(examples, 5, selection_salt="salt")
    cohorts = select_nested_cohorts(examples, (3, 5, 8), selection_salt="salt")

    assert [row.example_id for row in first] == [row.example_id for row in second]
    assert set(row.stratum for row in first) == {"single_session", "preference", "temporal"}
    assert [row.example_id for row in cohorts[3]] == [row.example_id for row in cohorts[5]][:3]
    assert [row.example_id for row in cohorts[5]] == [row.example_id for row in cohorts[8]][:5]


def test_cohort_rejects_duplicate_or_unidentified_examples():
    examples = _examples()
    with pytest.raises(ValueError, match="stable example_id"):
        select_nested_cohort([EvalExample("x", "q", "a")], 1, selection_salt="salt")
    with pytest.raises(ValueError, match="unique"):
        select_nested_cohort([examples[0], examples[0]], 1, selection_salt="salt")


def test_checkpoint_roundtrip_and_corruption_fail_closed(tmp_path):
    row = {
        "row_id": "tier:model:q-1",
        "tier_id": "tier",
        "example_id": "q-1",
        "model": "model",
        "policy": "default",
        "status": "complete",
        "accuracy": 1.0,
        "grounding_session": 1.0,
        "composite": 0.9,
        "citation_precision": 1.0,
        "source_recall": 1.0,
        "citation_token_f1": 1.0,
        "ranked_evidence_count": 1,
        "latency_seconds": 0.1,
        "answer_sha256": "abc",
        "citation_indices": [0],
        "error_class": None,
        "error_message": None,
    }
    checkpoint = CampaignCheckpoint(
        campaign_id="c",
        tier_id="tier",
        benchmark_provenance={"sha256": "digest"},
        model="model",
        model_metadata={"digest": "model-digest"},
        generation_options={"temperature": 0.0},
        config_fingerprint="config",
        code_fingerprint="code",
        selected_ids=("q-1",),
        rows=(CampaignRow.from_dict(row),),
    )
    path = checkpoint.write(tmp_path / "checkpoint.json")
    assert CampaignCheckpoint.read(path).to_dict() == checkpoint.to_dict()
    path.write_text("not json", encoding="utf-8")
    with pytest.raises((ValueError, json.JSONDecodeError)):
        CampaignCheckpoint.read(path)
    checkpoint = CampaignCheckpoint(
        campaign_id="c",
        tier_id="tier",
        benchmark_provenance={"sha256": "digest"},
        model="model",
        model_metadata={"digest": "model-digest"},
        generation_options={"temperature": 0.0},
        config_fingerprint="config",
        code_fingerprint="code",
        selected_ids=("q-1",),
        rows=(CampaignRow.from_dict(row),),
    )
    path = checkpoint.write(tmp_path / "mismatched.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["model_digest"] = "wrong-digest"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="model_digest"):
        CampaignCheckpoint.read(path)


def test_checkpoint_rejects_duplicate_examples_and_scope_mismatches(tmp_path):
    examples = _examples()
    spec = _spec(tmp_path, CampaignTier("tier-2", 2, "test-model"))
    run_campaign(
        spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: ExtractiveLM(),
    )
    path = tmp_path / "campaigns" / "test-campaign" / "checkpoints" / "tier-2.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    duplicate = dict(payload["rows"][0])
    duplicate["row_id"] = "different-row-id"
    payload["rows"].append(duplicate)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="example IDs must be unique"):
        CampaignCheckpoint.read(path)

    run_campaign(
        spec,
        examples,
        output_root=tmp_path / "scope-campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: ExtractiveLM(),
    )
    scope_path = tmp_path / "scope-campaigns" / "test-campaign" / "checkpoints" / "tier-2.json"
    scope_payload = json.loads(scope_path.read_text(encoding="utf-8"))
    scope_payload["rows"][0]["tier_id"] = "other-tier"
    scope_path.write_text(json.dumps(scope_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="row provenance"):
        CampaignCheckpoint.read(scope_path)


def test_run_campaign_resumes_and_promotes_only_complete_reports(tmp_path):
    examples = _examples()
    spec = _spec(tmp_path, CampaignTier("tier-3", 3, "test-model"))

    def factory(model, options):
        assert model == "test-model"
        assert options["temperature"] == 0.0
        return ExtractiveLM()

    report = run_campaign(
        spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=factory,
    )
    assert report.status == "complete"
    assert report.tiers["tier-3"]["n_evaluated"] == 3
    assert all(row.status == "complete" for row in report.rows)

    report_path = tmp_path / "campaigns" / "test-campaign" / "campaign_report.json"
    loaded = load_campaign_report(report_path)
    target = tmp_path / "promoted.json"
    assert promote_campaign_report(report_path, target) == target
    with pytest.raises(FileExistsError):
        promote_campaign_report(report_path, target)
    assert CampaignReport.from_dict(json.loads(target.read_text(encoding="utf-8"))).to_dict() == loaded.to_dict()


def test_failed_campaign_is_partial_and_cannot_promote(tmp_path):
    examples = _examples()
    spec = _spec(tmp_path, CampaignTier("tier-3", 3, "test-model"))

    class FailingLM:
        def complete(self, prompt: str) -> str:
            raise RuntimeError("capacity")

    report = run_campaign(
        spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: FailingLM(),
    )
    assert report.status == "partial"
    assert report.tiers["tier-3"]["n_evaluated"] == 0
    assert report.tiers["tier-3"]["n_failed"] == 3
    assert report.tiers["tier-3"]["pause_reason"] == "repeated_model_failures:3"
    with pytest.raises(ValueError, match="complete"):
        promote_campaign_report(
            tmp_path / "campaigns" / "test-campaign" / "campaign_report.json",
            tmp_path / "promoted.json",
        )


def test_interrupted_campaign_accounts_for_unstarted_tiers(tmp_path):
    examples = _examples()
    spec = _spec(
        tmp_path,
        CampaignTier("tier-3", 3, "test-model"),
        CampaignTier("tier-5", 5, "test-model"),
    )

    class FailingLM:
        def complete(self, prompt: str) -> str:
            raise RuntimeError("capacity")

    report = run_campaign(
        spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: FailingLM(),
    )
    assert report.status == "partial"
    assert report.tiers["tier-3"]["n_failed"] == 3
    assert report.tiers["tier-5"]["n_requested"] == 5
    assert report.tiers["tier-5"]["n_evaluated"] == 0
    assert report.tiers["tier-5"]["n_failed"] == 0
    assert report.tiers["tier-5"]["pause_reason"] == "campaign_interrupted_before_tier"
    assert load_campaign_report(
        tmp_path / "campaigns" / "test-campaign" / "campaign_report.json"
    ).tiers["tier-5"]["status"] == "partial"


def test_campaign_requires_model_digest_before_running(tmp_path):
    spec = _spec(tmp_path, CampaignTier("tier-3", 3, "test-model"))
    with pytest.raises(ValueError, match="model_metadata"):
        run_campaign(
            spec,
            _examples(),
            output_root=tmp_path / "campaigns",
            model_metadata={"test-model": {}},
            lm_factory=lambda model, options: ExtractiveLM(),
        )


def test_partial_checkpoint_resumes_and_scope_mismatch_recomputes(tmp_path):
    examples = _examples()
    first_spec = _spec(tmp_path, CampaignTier("tier-3", 3, "test-model"))

    class FailOnce:
        def __init__(self):
            self.calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            if self.calls <= 3:
                raise RuntimeError("temporary capacity")
            return ExtractiveLM().complete(prompt)

    failing = FailOnce()
    partial = run_campaign(
        first_spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: failing,
    )
    assert partial.status == "partial"
    checkpoint = tmp_path / "campaigns" / "test-campaign" / "checkpoints" / "tier-3.json"
    assert checkpoint.is_file()

    resumed = run_campaign(
        first_spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: ExtractiveLM(),
    )
    assert resumed.status == "complete"
    assert resumed.tiers["tier-3"]["n_evaluated"] == 3

    changed_spec = CampaignSpec(
        campaign_id="test-campaign",
        benchmark_path=first_spec.benchmark_path,
        tiers=first_spec.tiers,
        generation_options=(("temperature", 0.0), ("num_predict", 999)),
        min_free_bytes=1,
    )
    with pytest.raises(ValueError, match="scope mismatch"):
        run_campaign(
            changed_spec,
            examples,
            output_root=tmp_path / "campaigns",
            model_metadata={"test-model": {"digest": "digest"}},
            lm_factory=lambda model, options: ExtractiveLM(),
        )
    calls = {"count": 0}

    class CountingLM:
        def complete(self, prompt: str) -> str:
            calls["count"] += 1
            return ExtractiveLM().complete(prompt)

    def counting_factory(model, options):
        return CountingLM()

    changed = run_campaign(
        changed_spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=counting_factory,
        allow_scope_change=True,
    )
    assert changed.status == "complete"
    assert calls["count"] == 3
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["generation_options"] == {
        "temperature": 0.0,
        "num_predict": 512,
    }
    scoped = list((tmp_path / "campaigns" / "test-campaign" / "checkpoints").glob("tier-3.scope-*.json"))
    assert len(scoped) == 1
    assert json.loads(scoped[0].read_text(encoding="utf-8"))["generation_options"]["num_predict"] == 999


def test_promotion_rejects_tampered_counts_and_missing_provenance(tmp_path):
    examples = _examples()
    spec = _spec(tmp_path, CampaignTier("tier-3", 3, "test-model"))
    report = run_campaign(
        spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: ExtractiveLM(),
    )
    report_path = tmp_path / "campaigns" / "test-campaign" / "campaign_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["tiers"]["tier-3"]["n_evaluated"] = 2
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="counts mismatch"):
        load_campaign_report(report_path)

    report_path.write_text(json.dumps(report.to_dict()), encoding="utf-8")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    del payload["tiers"]["tier-3"]["generation_options"]
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="generation_options"):
        promote_campaign_report(report_path, tmp_path / "promoted.json")


def test_report_rejects_status_and_model_metadata_inconsistency(tmp_path):
    examples = _examples()
    spec = _spec(tmp_path, CampaignTier("tier-3", 3, "test-model"))
    run_campaign(
        spec,
        examples,
        output_root=tmp_path / "campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: ExtractiveLM(),
    )
    path = tmp_path / "campaigns" / "test-campaign" / "campaign_report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tiers"]["tier-3"]["model_metadata"]["digest"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="model metadata digest"):
        load_campaign_report(path)

    second = run_campaign(
        spec,
        examples,
        output_root=tmp_path / "other-campaigns",
        model_metadata={"test-model": {"digest": "digest"}},
        lm_factory=lambda model, options: ExtractiveLM(),
    )
    payload = second.to_dict()
    payload["status"] = "partial"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="partial campaign report"):
        load_campaign_report(path)
