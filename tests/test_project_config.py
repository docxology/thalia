"""Tests for the THALIA-local research overlay contract."""

from pathlib import Path

import pytest

from src.project_config import load_thalia_overlay, load_thalia_overlay_section


def test_overlay_keeps_project_specific_sections_local():
    payload = load_thalia_overlay()
    assert set(payload) == {"quality_evidence", "production_readiness", "v2_campaign", "model_quality"}
    quality = load_thalia_overlay_section("model_quality")
    assert quality["total_questions"] == 500
    assert quality["pilot"]["total_questions"] + quality["confirmatory"]["total_questions"] == 500


def test_overlay_rejects_non_mapping_and_missing_sections(tmp_path: Path):
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a mapping"):
        load_thalia_overlay(invalid)

    empty = tmp_path / "empty.yaml"
    empty.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a 'model_quality' mapping"):
        load_thalia_overlay_section("model_quality", empty)
