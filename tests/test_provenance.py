"""Tests for generated provenance registries (Zero-Mock)."""

import json

from src.provenance import (
    FIGURE_CAPTIONS,
    FIGURE_LABELS,
    default_verification_summary,
    load_verification_summary,
    validate_artifact_manifest,
    write_artifact_manifest,
    write_figure_registry,
    write_verification_summary,
)


class TestVerificationSummary:
    def test_default_summary_has_authoritative_commands(self):
        summary = default_verification_summary()
        assert "uv run --project . --extra dev python -m pytest tests/" in summary.test_command
        assert summary.coverage_gate == 90

    def test_write_and_load_round_trip(self, tmp_path):
        path = write_verification_summary(tmp_path / "verification_summary.json")
        loaded = load_verification_summary(path)
        assert loaded.test_command == default_verification_summary().test_command

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


class TestFigureRegistry:
    def test_writes_template_compatible_registry(self, tmp_path):
        fig = tmp_path / "retriever_comparison.png"
        fig.write_bytes(b"png")
        path = write_figure_registry([fig], tmp_path / "figure_registry.json")
        payload = json.loads(path.read_text())
        assert payload["fig:retriever_comparison"]["filename"] == "retriever_comparison.png"
        assert payload["fig:retriever_comparison"]["caption"] == FIGURE_CAPTIONS["retriever_comparison"]
        assert set(FIGURE_LABELS.values())


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

        write_artifact_manifest(root)
        payload = json.loads((root / "output" / "reports" / "artifact_manifest.json").read_text())
        paths = {entry["path"] for entry in payload["entries"]}

        assert "data/integrity_advantage.json" in paths
        report = validate_artifact_manifest(root, required_paths=("data/integrity_advantage.json",))
        assert report.ok

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
        manifest = root / "output" / "reports" / "artifact_manifest.json"
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
        manifest = root / "output" / "reports" / "artifact_manifest.json"
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
        manifest = root / "output" / "reports" / "artifact_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"entries": [], "issues": []}\n')
        report = validate_artifact_manifest(root)
        assert not report.ok
        assert "domain profile invalid" in report.issues[0]
