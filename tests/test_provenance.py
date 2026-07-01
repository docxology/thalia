"""Tests for generated provenance registries (Zero-Mock)."""

import json
from pathlib import Path

from src.provenance import (
    FIGURE_LABELS,
    default_verification_summary,
    load_verification_summary,
    write_artifact_manifest,
    write_figure_registry,
    write_verification_summary,
)


class TestVerificationSummary:
    def test_default_summary_has_authoritative_commands(self):
        summary = default_verification_summary()
        assert "uv run --project working/thalia pytest working/thalia/tests/" in summary.test_command
        assert summary.coverage_gate == 90

    def test_write_and_load_round_trip(self, tmp_path):
        path = write_verification_summary(tmp_path / "verification_summary.json")
        loaded = load_verification_summary(path)
        assert loaded.test_command == default_verification_summary().test_command


class TestFigureRegistry:
    def test_writes_template_compatible_registry(self, tmp_path):
        fig = tmp_path / "retriever_comparison.png"
        fig.write_bytes(b"png")
        path = write_figure_registry([fig], tmp_path / "figure_registry.json")
        payload = json.loads(path.read_text())
        assert payload["fig:retriever_comparison"]["filename"] == "retriever_comparison.png"
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
