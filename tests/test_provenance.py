"""Tests for generated provenance registries (Zero-Mock)."""

import json

import pytest

from src.provenance import (
    FIGURE_CAPTIONS,
    FIGURE_LABELS,
    default_verification_summary,
    validate_artifact_manifest,
    write_artifact_manifest,
    write_figure_registry,
    write_verification_summary,
)


class TestVerificationSummary:

    def test_existing_observations_keep_current_commands(self, tmp_path):
        path = tmp_path / "verification_summary.json"
        path.write_text(
            json.dumps(
                {
                    **default_verification_summary().to_dict(),
                    "render_command": "stale renderer",
                    "latest_observed_tests": "720 passed",
                    "status": "pass",
                }
            )
        )
        refreshed = write_verification_summary(path)
        payload = json.loads(refreshed.read_text())
        assert payload["latest_observed_tests"] == "720 passed"
        assert payload["render_command"] == default_verification_summary().render_command

    def test_refreshes_observations_from_machine_reports(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        (reports / "pytest.xml").write_text('<testsuites><testsuite tests="733" failures="0" errors="0" skipped="2"/></testsuites>')
        (reports / "coverage.json").write_text(json.dumps({"totals": {"percent_covered": 94.68}}))
        path = write_verification_summary(reports / "verification_summary.json")
        payload = json.loads(path.read_text())
        assert payload["latest_observed_tests"] == "731 passed; 733 collected"
        assert payload["latest_observed_coverage"] == "94.68% (src; gate 90%)"
        assert payload["status"] == "pass"
        tests = payload["command_results"]["tests"]
        assert tests["resource_warnings_as_errors"] is None
        assert set(tests["report_evidence"]) == {"pytest.xml", "coverage.json"}

    @pytest.mark.parametrize("tests,failures,errors,skipped", [
        (0, 0, 0, 0), (4, 1, 0, 0), (4, 0, 1, 0),
    ])
    def test_current_unsuccessful_collection_never_passes(
        self, tmp_path, tests, failures, errors, skipped,
    ):
        junit = tmp_path / "pytest.xml"
        coverage = tmp_path / "coverage.json"
        junit.write_text(
            f'<testsuite tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}"/>'
        )
        coverage.write_text('{"totals": {"percent_covered": 99}}')
        original = (junit.read_bytes(), coverage.read_bytes())
        payload = json.loads(write_verification_summary(tmp_path / "summary.json").read_text())
        assert payload["status"] == "fail"
        assert payload["command_results"]["tests"]["status"] == "fail"
        assert payload["command_results"]["tests"]["collected"] == tests
        assert original == (junit.read_bytes(), coverage.read_bytes())

    @pytest.mark.parametrize("junit,coverage", [
        (None, '{"totals": {"percent_covered": 99}}'),
        ('<testsuite tests="5" failures="0" errors="0" skipped="0"/>', None),
        ('<broken', '{"totals": {"percent_covered": 99}}'),
        ('<other/>', '{"totals": {"percent_covered": 99}}'),
        ('<testsuites/>', '{"totals": {"percent_covered": 99}}'),
        ('<testsuite tests="-1" failures="0" errors="0" skipped="0"/>', '{"totals": {"percent_covered": 99}}'),
        ('<testsuite tests="2.5" failures="0" errors="0" skipped="0"/>', '{"totals": {"percent_covered": 99}}'),
        ('<testsuite tests="1" failures="1" errors="1" skipped="0"/>', '{"totals": {"percent_covered": 99}}'),
        ('<testsuite failures="0" errors="0" skipped="0"/>', '{"totals": {"percent_covered": 99}}'),
        ('<testsuite tests="5" failures="0" errors="0" skipped="0"/>', '[]'),
        ('<testsuite tests="5" failures="0" errors="0" skipped="0"/>', '{"totals": {}}'),
        ('<testsuite tests="5" failures="0" errors="0" skipped="0"/>', 'not JSON'),
    ])
    def test_partial_or_malformed_reports_replace_stale_pass(self, tmp_path, junit, coverage):
        path = tmp_path / "summary.json"
        path.write_text(json.dumps({
            **default_verification_summary().to_dict(),
            "status": "pass",
            "latest_observed_tests": "999 passed",
            "latest_observed_coverage": "100%",
            "command_results": {"tests": {"status": "pass", "collected": 999, "passed": 999}},
        }))
        if junit is not None:
            (tmp_path / "pytest.xml").write_text(junit)
        if coverage is not None:
            (tmp_path / "coverage.json").write_text(coverage)
        payload = json.loads(write_verification_summary(path).read_text())
        assert payload["status"] == "fail"
        assert payload["latest_observed_tests"] == ""
        assert payload["latest_observed_coverage"] == ""
        assert payload["command_results"]["tests"]["status"] == "unavailable"
        assert "collected" not in payload["command_results"]["tests"]
        assert payload["command_results"]["tests"]["issues"]

    @pytest.mark.parametrize("percent", [float("nan"), float("inf"), float("-inf"), -1, 101, True, "99"])
    def test_invalid_coverage_is_unavailable(self, tmp_path, percent):
        (tmp_path / "pytest.xml").write_text(
            '<testsuite tests="5" failures="0" errors="0" skipped="0"/>'
        )
        (tmp_path / "coverage.json").write_text(json.dumps({"totals": {"percent_covered": percent}}))
        payload = json.loads(write_verification_summary(tmp_path / "summary.json").read_text())
        assert payload["status"] == "fail"
        assert payload["command_results"]["tests"]["status"] == "unavailable"
        assert payload["latest_observed_coverage"] == ""

    @pytest.mark.parametrize("counters", [
        {"num_statements": -1},
        {"num_statements": True},
        {"covered_lines": 1.5},
        {"num_partial_branches": -1},
        {"num_statements": 1, "covered_lines": 2},
        {"num_statements": 5, "covered_lines": 3, "missing_lines": 3},
        {"num_branches": 2, "covered_branches": 3},
        {"num_branches": 4, "covered_branches": 2, "missing_branches": 1},
    ])
    def test_invalid_coverage_counters_fail_closed(self, tmp_path, counters):
        (tmp_path / "pytest.xml").write_text(
            '<testsuite tests="5" failures="0" errors="0" skipped="0"/>'
        )
        (tmp_path / "coverage.json").write_text(json.dumps({
            "totals": {"percent_covered": 99, **counters},
        }))
        payload = json.loads(write_verification_summary(tmp_path / "summary.json").read_text())
        assert payload["command_results"]["tests"]["status"] == "unavailable"

    def test_aggregate_suites_and_coverage_threshold(self, tmp_path):
        (tmp_path / "pytest.xml").write_text(
            '<testsuites tests="5" failures="0" errors="0" skipped="1">'
            '<testsuite tests="2" failures="0" errors="0" skipped="1"/>'
            '<testsuite tests="3" failures="0" errors="0" skipped="0"/></testsuites>'
        )
        (tmp_path / "coverage.json").write_text('{"totals": {"percent_covered": 89.99}}')
        payload = json.loads(write_verification_summary(tmp_path / "summary.json").read_text())
        assert payload["status"] == "fail"
        assert payload["command_results"]["tests"]["passed"] == 4
        assert payload["command_results"]["tests"]["coverage_percent"] == 89.99

    def test_both_absent_preserve_historical_test_observations(self, tmp_path):
        previous = {
            **default_verification_summary().to_dict(),
            "status": "pass",
            "latest_observed_tests": "8 passed; 8 collected",
            "latest_observed_coverage": "95.00% (src; gate 90%)",
            "command_results": {"tests": {"status": "pass", "collected": 8, "passed": 8}},
        }
        path = tmp_path / "summary.json"
        path.write_text(json.dumps(previous))
        assert json.loads(write_verification_summary(path).read_text()) == previous

    def test_refreshes_artifact_observation_from_manifest(self, tmp_path):
        root = tmp_path / "thalia"
        reports = root / "output" / "reports"
        data = root / "output" / "data"
        reports.mkdir(parents=True)
        data.mkdir(parents=True)
        (data / "demo_result.json").write_text("{}\n")
        summary_path = write_verification_summary(reports / "verification_summary.json")
        write_artifact_manifest(root)

        refreshed = write_verification_summary(summary_path)
        payload = json.loads(refreshed.read_text())
        artifact_result = payload["command_results"]["artifact_pipeline"]
        assert artifact_result["status"] == "pass"
        assert artifact_result["checked"] >= 2
        assert artifact_result["required"] == 0
        assert payload["status"] == "unavailable"
        assert payload["command_results"]["tests"]["status"] == "unavailable"


class TestFigureRegistry:
    def test_writes_template_compatible_registry(self, tmp_path):
        fig = tmp_path / "retriever_comparison.png"
        fig.write_bytes(b"png")
        path = write_figure_registry([fig], tmp_path / "figure_registry.json")
        payload = json.loads(path.read_text())
        assert payload["fig:retriever_comparison"]["filename"] == "retriever_comparison.png"
        assert payload["fig:retriever_comparison"]["caption"] == FIGURE_CAPTIONS["retriever_comparison"]
        assert set(FIGURE_LABELS.values())

    def test_method_design_registry_and_authored_alt_text(self, tmp_path):
        from src.figures.diagrams import plot_backend_method_design

        fig = plot_backend_method_design(tmp_path / "backend_method_design.png")
        path = tmp_path / "figure_registry.json"
        authored_alt = "Authored description: query → context policies → complete-pair gate."
        path.write_text(json.dumps({
            "fig:backend_method_design": {"alt_text": authored_alt},
        }), encoding="utf-8")
        write_figure_registry([fig], path)
        entry = json.loads(path.read_text())["fig:backend_method_design"]
        assert entry["filename"] == "backend_method_design.png"
        assert entry["label"] == "fig:backend_method_design"
        assert entry["alt_text"] == authored_alt
        assert entry["caption"] == FIGURE_CAPTIONS["backend_method_design"]
        assert entry["generated_by"] == "scripts/generate_figures.py"
        assert entry["source"] == "src/figures/"
        write_figure_registry([fig], path)
        assert json.loads(path.read_text())["fig:backend_method_design"]["alt_text"] == authored_alt

    def test_missing_authored_alt_uses_source_caption(self, tmp_path):
        fig = tmp_path / "backend_method_design.png"
        path = write_figure_registry([fig], tmp_path / "figure_registry.json")
        entry = json.loads(path.read_text())["fig:backend_method_design"]
        assert entry["alt_text"] == FIGURE_CAPTIONS["backend_method_design"]


class TestArtifactManifest:
    def test_writes_current_hashes_for_stable_outputs(self, tmp_path):
        root = tmp_path / "thalia"
        data = root / "output" / "data"
        data.mkdir(parents=True)
        artifact = data / "demo_result.json"
        artifact.write_text("{}\n")
        path = write_artifact_manifest(root)
        payload = json.loads(path.read_text())
        entries = payload["entries"]
        assert payload["issues"] == []
        assert entries[0]["path"] == "output/data/demo_result.json"
        assert entries[0]["contract_match"] is True
        assert len(entries[0]["sha256"]) == 64

    def test_tracks_source_bound_integrity_screen(self, tmp_path):
        root = tmp_path / "thalia"
        screen = root / "data" / "integrity_advantage.json"
        screen.parent.mkdir(parents=True)
        screen.write_text('{"schema_version": 3}\n')

        manifest = write_artifact_manifest(root)
        payload = json.loads(manifest.read_text())
        paths = {entry["path"] for entry in payload["entries"]}

        assert "data/integrity_advantage.json" in paths
        report = validate_artifact_manifest(root, required_paths=("data/integrity_advantage.json",))
        assert report.ok

    def test_tracks_both_publication_input_receipts(self, tmp_path):
        reports = tmp_path / "output" / "reports"
        reports.mkdir(parents=True)
        for consumer in ("dashboard", "manuscript"):
            (reports / f"{consumer}_benchmark_input.json").write_text("{}\n")
        payload = json.loads(write_artifact_manifest(tmp_path).read_text())
        assert {entry["path"] for entry in payload["entries"]} == {
            "output/reports/dashboard_benchmark_input.json",
            "output/reports/manuscript_benchmark_input.json",
        }

    def test_validator_accepts_current_manifest(self, tmp_path):
        root = tmp_path / "thalia"
        data = root / "output" / "data"
        data.mkdir(parents=True)
        artifact = data / "demo_result.json"
        artifact.write_text("{}\n")
        write_artifact_manifest(root)
        report = validate_artifact_manifest(root, required_paths=("output/data/demo_result.json",))
        assert report.ok
        assert report.checked == 1
        assert report.required == 1

    def test_validator_refuses_mutated_artifact(self, tmp_path):
        root = tmp_path / "thalia"
        data = root / "output" / "data"
        data.mkdir(parents=True)
        artifact = data / "demo_result.json"
        artifact.write_text("{}\n")
        write_artifact_manifest(root)
        artifact.write_text('{"changed": true}\n')
        report = validate_artifact_manifest(root)
        assert not report.ok
        assert any("mismatch" in issue for issue in report.issues)

    def test_validator_refuses_unsafe_manifest_path(self, tmp_path):
        root = tmp_path / "thalia"
        manifest = root / "output" / "reports" / "thalia_artifact_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"entries": [{"path": "../secret.txt"}], "issues": []}\n')
        report = validate_artifact_manifest(root)
        assert not report.ok
        assert "unsafe artifact path" in report.issues[0]

    def test_validator_refuses_symlinked_artifact(self, tmp_path):
        root = tmp_path / "thalia"
        data = root / "output" / "data"
        data.mkdir(parents=True)
        outside = tmp_path / "outside.json"
        outside.write_text("{}\n")
        artifact = data / "demo_result.json"
        artifact.symlink_to(outside)
        manifest = root / "output" / "reports" / "thalia_artifact_manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"entries": [{
            "path": "output/data/demo_result.json",
            "contract_match": True,
            "sha256": "0" * 64,
            "size_bytes": outside.stat().st_size,
        }]}, sort_keys=True))
        report = validate_artifact_manifest(root)
        assert not report.ok
        assert "symlink" in report.issues[0]

    def test_malformed_domain_profile_fails_closed(self, tmp_path):
        root = tmp_path / "thalia"
        profile = root / "domain_profile.yaml"
        profile.parent.mkdir(parents=True)
        profile.write_text("artifact_expectations: [\n")
        manifest = root / "output" / "reports" / "thalia_artifact_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"entries": [], "issues": []}\n')
        report = validate_artifact_manifest(root)
        assert not report.ok
        assert "domain profile invalid" in report.issues[0]

    def test_native_inventory_cannot_replace_required_source_attestation(self, tmp_path):
        root = tmp_path / "thalia"
        screen = root / "data" / "integrity_advantage.json"
        screen.parent.mkdir(parents=True)
        screen.write_text('{"observed": 1}\n')
        (root / "domain_profile.yaml").write_text(
            "artifact_expectations:\n  - data/integrity_advantage.json\n"
        )
        native = root / "output" / "reports" / "artifact_manifest.json"
        native.parent.mkdir(parents=True)
        native.write_text('{"native_inventory": "retained"}\n')
        write_artifact_manifest(root)
        assert json.loads(native.read_text()) == {"native_inventory": "retained"}

        # Native validation inventories output/, not committed required data.
        native.write_text('{"entries": [], "issues": []}\n')
        assert validate_artifact_manifest(root).ok
        screen.write_text('{"observed": 2}\n')
        report = validate_artifact_manifest(root)
        assert not report.ok
        assert any("sha256 mismatch: data/integrity_advantage.json" == issue for issue in report.issues)
