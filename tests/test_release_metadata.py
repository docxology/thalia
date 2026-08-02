"""Tests for source-controlled public-release metadata (real files, no mocks)."""

import json
from datetime import date
from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 uses the declared backport
    import tomli as tomllib

from src import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_citation_metadata_is_parseable_and_matches_package() -> None:
    metadata = yaml.safe_load((PROJECT_ROOT / "CITATION.cff").read_text())

    assert metadata["cff-version"] == "1.2.0"
    assert metadata["type"] == "software"
    assert metadata["version"] == __version__
    assert metadata["license"] == "MIT"
    assert metadata["doi"] == "10.5281/zenodo.21763245"
    assert metadata["repository-code"] == "https://github.com/docxology/thalia"
    assert metadata["authors"]
    assert metadata["title"]
    assert metadata["abstract"]
    assert date.fromisoformat(str(metadata["date-released"])) == date(2026, 8, 2)


def test_release_checklist_keeps_license_and_doi_as_explicit_gates() -> None:
    checklist = (PROJECT_ROOT / "docs" / "release_readiness.md").read_text()

    assert "THALIA `v0.1.0` is publicly released" in checklist
    assert "MIT applies to THALIA's authored source code" in checklist
    assert "10.5281/zenodo.21763245" in checklist


def test_mit_metadata_is_consistent_across_package_and_archive_files() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    assert project["project"]["license"] == "MIT"
    assert project["project"]["license-files"] == ["LICENSE"]

    license_text = (PROJECT_ROOT / "LICENSE").read_text()
    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 Daniel Ari Friedman" in license_text

    zenodo = json.loads((PROJECT_ROOT / ".zenodo.json").read_text())
    assert zenodo["license"] == "MIT"
    assert zenodo["upload_type"] == "software"
    assert zenodo["version"] == __version__
    assert zenodo["doi"] == "10.5281/zenodo.21763245"
    assert zenodo["creators"]
    assert any(
        item["identifier"] == "https://github.com/docxology/thalia"
        for item in zenodo["related_identifiers"]
    )
