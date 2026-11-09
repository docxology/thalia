"""Frozen supplement behavior with real staged source and native inventories."""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
from pathlib import Path

import pytest

from src.release_artifacts import assemble_release_artifacts, load_release_allowlist

THALIA = "output/reports/thalia_artifact_manifest.json"
NATIVE = "output/reports/artifact_manifest.json"
DASHBOARD = "output/dashboard.html"
QA = "output/reports/native_qa.json"
SOURCE = "data/integrity_advantage.json"


def _write(root: Path, relative: str, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _entry(root: Path, relative: str) -> dict:
    content = (root / relative).read_bytes()
    return {
        "path": relative,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
        "contract_match": True,
        "stage_name": "frozen source fixture",
        "stage_num": 0,
        "timestamp": "retained-evidence-not-regenerated",
    }


def _manifest(root: Path, relative: str, paths: list[str]) -> None:
    _write(root, relative, (json.dumps({
        "entries": [_entry(root, path) for path in paths], "issues": [],
    }, indent=2, sort_keys=True) + "\n").encode())


@pytest.fixture
def stage(tmp_path):
    root = tmp_path / "thalia"
    _write(root, SOURCE, b'{"schema_version": 3, "observed": 2}\n')
    _write(root, DASHBOARD, b"<!doctype html><title>Frozen THALIA</title>\n")
    _write(root, QA, b'{"checks": ["native-gate-evidence-is-retained"]}\n')
    _write(root, "domain_profile.yaml", (
        "artifact_expectations:\n"
        f"  - {SOURCE}\n"
        f"  - {DASHBOARD}\n"
    ).encode())
    _manifest(root, THALIA, [SOURCE, DASHBOARD])
    _manifest(root, NATIVE, [DASHBOARD, QA, THALIA])
    return root, [DASHBOARD, THALIA, NATIVE, QA]


def test_round_trip_deterministic_archive_and_external_receipt(stage, tmp_path):
    root, selected = stage
    before = {path: (root / path).read_bytes() for path in selected}
    first, second = tmp_path / "one.tar.gz", tmp_path / "two.tar.gz"
    receipt = assemble_release_artifacts(root, reversed(selected), first, prefix="thalia-artifacts")
    # Metadata, order and destination filename must not change the archive bytes.
    for relative in selected:
        os.utime(root / relative, (1234567, 1234567))
        (root / relative).chmod(0o600)
    again = assemble_release_artifacts(root, selected, second, prefix="thalia-artifacts")
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes()[4:8] == b"\0\0\0\0"
    assert receipt["archive"]["path"] == first.name
    assert receipt["archive"]["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert receipt["archive"]["size_bytes"] == first.stat().st_size
    assert receipt["scope"] == "byte-and-closure-checks-only"
    assert receipt["native_validation"] == "not_run"
    assert receipt["checks"]["thalia_required_paths"] == 2
    assert receipt["members"] == again["members"]
    assert str(root) not in json.dumps(receipt)
    assert SOURCE not in [member["path"] for member in receipt["members"]]
    with tarfile.open(first, "r:gz") as archive:
        assert archive.getnames() == [f"thalia-artifacts/{path}" for path in sorted(selected)]
        for member, observed in zip(archive.getmembers(), receipt["members"], strict=True):
            assert member.isfile()
            assert member.mode == 0o644
            assert member.uid == member.gid == member.mtime == 0
            assert member.uname == member.gname == ""
            content = archive.extractfile(member).read()
            assert content == before[observed["path"]]
            assert observed["size_bytes"] == len(content)
            assert observed["sha256"] == hashlib.sha256(content).hexdigest()
    assert receipt["inventories"] == [
        {"path": path, "sha256": hashlib.sha256(before[path]).hexdigest(), "size_bytes": len(before[path])}
        for path in (THALIA, NATIVE)
    ]
    for path in selected:
        assert (root / path).read_bytes() == before[path]


def test_absent_native_inventory_is_not_invented(stage, tmp_path):
    root, selected = stage
    (root / NATIVE).unlink()
    selected.remove(NATIVE)
    receipt = assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")
    assert [entry["path"] for entry in receipt["inventories"]] == [THALIA]
    assert not (root / NATIVE).exists()
    assert receipt["native_validation"] == "not_run"


def test_native_qa_cannot_be_pruned_after_validation(stage, tmp_path):
    root, selected = stage
    selected.remove(QA)
    destination = tmp_path / "supplement.tar.gz"
    with pytest.raises(ValueError, match="inventoried output missing.*native_qa"):
        assemble_release_artifacts(root, selected, destination)
    assert not destination.exists()


@pytest.mark.parametrize("relative", [SOURCE, DASHBOARD, QA])
def test_changed_required_source_or_frozen_output_refused(stage, tmp_path, relative):
    root, selected = stage
    original = (root / relative).read_bytes()
    # Equal-size mutation must be caught by SHA, not just the length check.
    (root / relative).write_bytes(bytes([original[0] ^ 1]) + original[1:])
    destination = tmp_path / "supplement.tar.gz"
    with pytest.raises(ValueError, match="byte identity mismatch"):
        assemble_release_artifacts(root, selected, destination)
    assert not destination.exists()


def test_missing_required_source_remains_a_refusal(stage, tmp_path):
    root, selected = stage
    (root / SOURCE).unlink()
    with pytest.raises(FileNotFoundError):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")


def test_native_cannot_replace_thalia_required_source_attestation(stage, tmp_path):
    root, selected = stage
    _manifest(root, THALIA, [DASHBOARD])
    _manifest(root, NATIVE, [SOURCE, DASHBOARD, QA, THALIA])
    with pytest.raises(ValueError, match="required artifact absent.*data/integrity_advantage"):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")


@pytest.mark.parametrize("inventory", [THALIA, NATIVE])
def test_inventories_must_be_explicit_members(stage, tmp_path, inventory):
    root, selected = stage
    selected.remove(inventory)
    with pytest.raises(ValueError, match="inventory must be explicitly selected"):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")


@pytest.mark.parametrize("path", ["../secret", "/absolute", "output//file", "./file", "a/../b", "a\\b", "C:secret", "a/", "", "a\nsecret"])
def test_unsafe_allowlist_paths_refused(stage, tmp_path, path):
    root, selected = stage
    with pytest.raises(ValueError, match="path"):
        assemble_release_artifacts(root, [*selected, path], tmp_path / "supplement.tar.gz")


@pytest.mark.parametrize("prefix", ["../escape", "/absolute", "prefix/", "a\\b"])
def test_unsafe_prefix_refused(stage, tmp_path, prefix):
    root, selected = stage
    with pytest.raises(ValueError, match="path"):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz", prefix=prefix)


@pytest.mark.parametrize("selected", [[], [THALIA, THALIA], THALIA])
def test_empty_duplicate_or_string_allowlist_refused(stage, tmp_path, selected):
    root, _ = stage
    with pytest.raises(ValueError, match="allowlist"):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")


@pytest.mark.parametrize("parent_link", [False, True])
def test_selected_symlink_or_symlinked_parent_refused(stage, tmp_path, parent_link):
    root, selected = stage
    if parent_link:
        (root / "linked-reports").symlink_to(root / "output/reports", target_is_directory=True)
        selected.append("linked-reports/native_qa.json")
    else:
        (root / QA).unlink()
        (root / QA).symlink_to(root / DASHBOARD)
    with pytest.raises(ValueError, match="symlink"):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")


def test_nonregular_and_missing_allowlisted_files_refused(stage, tmp_path):
    root, selected = stage
    for relative, error in [("output/reports", ValueError), ("output/missing.json", FileNotFoundError)]:
        with pytest.raises(error):
            assemble_release_artifacts(root, [*selected, relative], tmp_path / "supplement.tar.gz")


@pytest.mark.parametrize("change", ["duplicate", "unsafe", "size", "digest", "contract", "entries", "entry", "disagreement"])
def test_malformed_or_disagreeing_native_inventory_refused(stage, tmp_path, change):
    root, selected = stage
    payload = json.loads((root / NATIVE).read_text())
    entry = payload["entries"][0]
    if change == "duplicate":
        payload["entries"].append(entry)
    elif change == "unsafe":
        entry["path"] = "../private"
    elif change == "size":
        entry["size_bytes"] = True
    elif change == "digest":
        entry["sha256"] = "not-a-sha256"
    elif change == "contract":
        entry["contract_match"] = False
    elif change == "entries":
        payload["entries"] = {}
    elif change == "entry":
        payload["entries"][0] = None
    elif change == "disagreement":
        entry["sha256"] = "0" * 64
    (root / NATIVE).write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")


def test_existing_destination_and_dangling_link_preserved(stage, tmp_path):
    root, selected = stage
    destination = tmp_path / "existing.tar.gz"
    destination.write_bytes(b"user-owned-original")
    with pytest.raises(FileExistsError):
        assemble_release_artifacts(root, selected, destination)
    assert destination.read_bytes() == b"user-owned-original"
    destination.unlink()
    destination.symlink_to(tmp_path / "absent-target")
    with pytest.raises(FileExistsError):
        assemble_release_artifacts(root, selected, destination)
    assert destination.is_symlink()
    assert not destination.exists()


def test_allowlist_json_reads_only_explicit_paths(tmp_path):
    path = tmp_path / "allowlist.json"
    path.write_text(json.dumps([THALIA, DASHBOARD, "output/release_support/LICENSE"]))
    assert load_release_allowlist(path) == (THALIA, DASHBOARD, "output/release_support/LICENSE")
    for payload in [{"paths": [THALIA]}, [THALIA, None], THALIA]:
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="JSON array"):
            load_release_allowlist(path)


def test_only_explicit_support_is_bundled_without_scanning(stage, tmp_path):
    root, selected = stage
    support = "output/release_support/STUDY_PRODUCER/original-receipt.json"
    _write(root, support, b'{"producer": "original-identity"}\n')
    _write(root, "output/unreviewed-private.json", b"not reviewed for release")
    selected.append(support)
    receipt = assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")
    assert [member["path"] for member in receipt["members"]] == sorted(selected)
    assert "output/unreviewed-private.json" not in json.dumps(receipt)


def test_symlinked_required_source_parent_is_refused(stage, tmp_path):
    root, selected = stage
    source_data = tmp_path / "external-data"
    (root / "data").rename(source_data)
    (root / "data").symlink_to(source_data, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")


def test_invalid_domain_profile_is_not_treated_as_no_requirements(stage, tmp_path):
    root, selected = stage
    (root / "domain_profile.yaml").write_text("artifact_expectations: [\n")
    with pytest.raises(ValueError, match="domain profile invalid"):
        assemble_release_artifacts(root, selected, tmp_path / "supplement.tar.gz")
