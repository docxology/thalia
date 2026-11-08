"""Tests for distinct current-release and historical-archive identities."""

import json
import tomllib
from datetime import date
from pathlib import Path

import yaml

from src import __version__
from src.manuscript_variables import _load_archived_release_doi


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_citation_metadata_is_parseable_and_matches_package() -> None:
    metadata = yaml.safe_load((PROJECT_ROOT / "CITATION.cff").read_text())

    assert metadata["cff-version"] == "1.2.0"
    assert metadata["type"] == "software"
    assert metadata["version"] == __version__
    assert metadata["license"] == "MIT"
    assert "doi" not in metadata
    assert metadata["repository-code"] == "https://github.com/docxology/thalia"
    assert metadata["url"] == f"{metadata['repository-code']}/releases/tag/v{__version__}"
    assert metadata["authors"]
    assert metadata["title"]
    assert metadata["abstract"]
    date.fromisoformat(str(metadata["date-released"]))


def test_current_release_identity_is_distinct_from_archived_doi() -> None:
    citation = yaml.safe_load((PROJECT_ROOT / "CITATION.cff").read_text())
    zenodo = json.loads((PROJECT_ROOT / ".zenodo.json").read_text())
    assert "doi" not in zenodo
    assert zenodo["version"] == __version__
    assert date.fromisoformat(zenodo["publication_date"]) == citation["date-released"]
    identities = [
        item["identifier"]
        for item in zenodo["related_identifiers"]
        if item["relation"] == "isIdenticalTo"
    ]
    assert identities == [citation["url"]]
    archived_doi = _load_archived_release_doi()
    assert archived_doi not in identities
    assert archived_doi in (PROJECT_ROOT / "docs" / "release_receipt.md").read_text()


def test_manuscript_identifies_current_release_without_claiming_archive_doi() -> None:
    config = yaml.safe_load((PROJECT_ROOT / "docs" / "manuscript" / "config.yaml").read_text())
    citation = yaml.safe_load((PROJECT_ROOT / "CITATION.cff").read_text())
    assert config["paper"]["version"] == __version__
    assert date.fromisoformat(config["paper"]["date"]) == citation["date-released"]
    assert not config["publication"]["doi"]


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
    assert zenodo["creators"]
