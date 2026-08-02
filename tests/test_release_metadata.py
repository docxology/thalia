"""Tests for source-controlled public-release metadata (real files, no mocks)."""

from datetime import date
from pathlib import Path

import yaml

from src import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_citation_metadata_is_parseable_and_matches_package() -> None:
    metadata = yaml.safe_load((PROJECT_ROOT / "CITATION.cff").read_text())

    assert metadata["cff-version"] == "1.2.0"
    assert metadata["type"] == "software"
    assert metadata["version"] == __version__
    assert metadata["repository-code"] == "https://github.com/docxology/thalia"
    assert metadata["authors"]
    assert metadata["title"]
    assert metadata["abstract"]
    assert date.fromisoformat(str(metadata["date-released"])) == date(2026, 8, 2)


def test_release_checklist_keeps_license_and_doi_as_explicit_gates() -> None:
    checklist = (PROJECT_ROOT / "docs" / "release_readiness.md").read_text()

    assert "not yet ready for a public GitHub or Zenodo release" in checklist
    assert "choose a software license" in checklist
    assert "minted DOI" in checklist
