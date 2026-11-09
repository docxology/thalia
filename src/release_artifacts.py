"""Assemble reviewed frozen bytes, not a native-validation or publication gate.

The allowlist is an explicit iterable of canonical project-relative file paths.
Both existing artifact inventories must themselves be selected. Their output
closure must be selected too; required non-output inputs are validated in the
staged source tree but are not implicitly copied into the supplement. Review
privacy and redistribution rights before supplying the allowlist.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import stat
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import BinaryIO, cast

from .provenance import validate_artifact_manifest

THALIA_MANIFEST = "output/reports/thalia_artifact_manifest.json"
NATIVE_MANIFEST = "output/reports/artifact_manifest.json"


def _portable_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("paths must be nonempty strings")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {".", ".."} for part in path.parts)
        or not path.parts
        or any(char in value for char in "\\:\x00")
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"unsafe or noncanonical path: {value!r}")
    return value


def _regular_file(root: Path, relative: str) -> Path:
    """Refuse links in every project-relative component, not only the leaf."""
    path = root
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        path = path / part
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink is not permitted: {relative}")
        expected = stat.S_ISREG(mode) if index == len(parts) - 1 else stat.S_ISDIR(mode)
        if not expected:
            raise ValueError(f"not a regular file with directory parents: {relative}")
    return path


class _HashingReader:
    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        data = self.stream.read(size)
        self.digest.update(data)
        self.size += len(data)
        return data

    def identity(self) -> tuple[str, int]:
        return self.digest.hexdigest(), self.size


def _fingerprint(root: Path, relative: str) -> tuple[str, int]:
    path = _regular_file(root, relative)
    with path.open("rb") as stream:
        reader = _HashingReader(stream)
        while reader.read(1024 * 1024):
            pass
    _regular_file(root, relative)
    return reader.identity()


def _inventory(root: Path, relative: str) -> tuple[bytes, dict[str, tuple[str, int]]]:
    raw = _regular_file(root, relative).read_bytes()
    payload = json.loads(raw)
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"manifest entries must be a list: {relative}")
    result: dict[str, tuple[str, int]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"manifest entry must be a mapping: {relative}")
        path = _portable_path(entry.get("path"))
        if path in result:
            raise ValueError(f"duplicate manifest path: {path}")
        digest, size = entry.get("sha256"), entry.get("size_bytes")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or type(size) is not int
            or size < 0
        ):
            raise ValueError(f"invalid manifest byte identity: {path}")
        result[path] = digest, size
    return raw, result


def load_release_allowlist(path: str | Path) -> tuple[str, ...]:
    """Read a JSON array; do not glob, discover files, or add implicit members."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError("allowlist must be a JSON array of relative file paths")
    return tuple(payload)


def assemble_release_artifacts(
    project_root: str | Path,
    allowlist: Iterable[str],
    output: str | Path,
    *,
    prefix: str = "",
) -> dict[str, object]:
    """Atomically create a deterministic tar.gz without replacing a destination.

    Return a JSON-ready external member receipt. ``checks`` describe byte and
    closure checks only. Native execution, rendering, models, Git and publishing
    are never invoked. Existing inventories are included byte-for-byte, never
    regenerated. Any failure before publication removes only our temporary file.
    """
    project = Path(project_root)
    if project.is_symlink():
        raise ValueError("project_root must not be a symlink")
    root = project.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project_root must be a directory")
    if isinstance(allowlist, (str, bytes)):
        raise ValueError("allowlist must be an iterable of paths, not a string")
    selected = tuple(_portable_path(path) for path in allowlist)
    if not selected:
        raise ValueError("allowlist must not be empty")
    if len(set(selected)) != len(selected):
        raise ValueError("duplicate allowlist path")
    selected = tuple(sorted(selected))
    if prefix:
        _portable_path(prefix)
    destination = Path(output).absolute()
    if os.path.lexists(destination):
        raise FileExistsError(f"destination already exists: {destination}")
    # Do not follow destination parent links into the selected inputs.
    for parent in destination.parents:
        if parent.is_symlink():
            raise ValueError(f"destination parent must not be a symlink: {parent}")
    if not destination.parent.is_dir():
        raise ValueError("destination parent must already be a directory")

    optional_presence = {
        path: os.path.lexists(root / path)
        for path in (NATIVE_MANIFEST, "domain_profile.yaml")
    }
    manifest_paths = [THALIA_MANIFEST]
    if optional_presence[NATIVE_MANIFEST]:
        manifest_paths.append(NATIVE_MANIFEST)
    inventories: list[dict[str, object]] = []
    expected: dict[str, tuple[str, int]] = {}
    manifest_bytes: dict[str, tuple[str, int]] = {}
    for relative in manifest_paths:
        if relative not in selected:
            raise ValueError(f"inventory must be explicitly selected: {relative}")
        raw, entries = _inventory(root, relative)
        identity = hashlib.sha256(raw).hexdigest(), len(raw)
        manifest_bytes[relative] = identity
        inventories.append({"path": relative, "sha256": identity[0], "size_bytes": identity[1]})
        for path, identity in entries.items():
            if path.startswith("output/") and path not in selected:
                raise ValueError(f"inventoried output missing from allowlist: {path}")
            if path in expected and expected[path] != identity:
                raise ValueError(f"inventories disagree on byte identity: {path}")
            expected[path] = identity

    inputs = set(selected) | set(expected) | set(manifest_paths)
    if optional_presence["domain_profile.yaml"]:
        inputs.add("domain_profile.yaml")
    snapshots = {path: _fingerprint(root, path) for path in sorted(inputs)}
    for inventory in (expected, manifest_bytes):
        for path, identity in inventory.items():
            if snapshots[path] != identity:
                raise ValueError(f"frozen byte identity mismatch: {path}")
    if any(destination == root / path for path in inputs):
        raise ValueError("destination must be outside the selected and required inputs")

    validation = validate_artifact_manifest(root)
    if not validation.ok:
        raise ValueError("THALIA manifest validation failed: " + "; ".join(validation.issues))
    if NATIVE_MANIFEST in manifest_paths:
        native = validate_artifact_manifest(root, root / NATIVE_MANIFEST, required_paths=())
        if not native.ok:
            raise ValueError("native inventory byte validation failed: " + "; ".join(native.issues))
    members: list[dict[str, object]] = []
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".thalia-", delete=False) as stream:
            temporary = Path(stream.name)
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0, compresslevel=9) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    for relative in selected:
                        digest, size = snapshots[relative]
                        archive_path = f"{prefix}/{relative}" if prefix else relative
                        info = tarfile.TarInfo(archive_path)
                        info.size = size
                        info.mode = 0o644
                        info.mtime = info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        with _regular_file(root, relative).open("rb") as source:
                            reader = _HashingReader(source)
                            archive.addfile(info, cast(BinaryIO, reader))
                            if reader.read(1) or reader.identity() != (digest, size):
                                raise ValueError(f"selected bytes changed during assembly: {relative}")
                        members.append({
                            "path": relative, "archive_path": archive_path,
                            "sha256": digest, "size_bytes": size,
                        })
        for relative, identity in snapshots.items():
            if _fingerprint(root, relative) != identity:
                raise ValueError(f"input bytes changed during assembly: {relative}")
        for relative, present in optional_presence.items():
            if present != os.path.lexists(root / relative):
                raise ValueError(f"input presence changed during assembly: {relative}")
        with temporary.open("rb") as archive_stream:
            archive_hash = hashlib.file_digest(archive_stream, "sha256").hexdigest()
        archive_size = temporary.stat().st_size
        # Same-directory hard linking publishes the complete file atomically and
        # fails if another writer has claimed the destination in the meantime.
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink()

    return {
        "schema_version": 1,
        "scope": "byte-and-closure-checks-only",
        "native_validation": "not_run",
        "archive": {"path": destination.name, "sha256": archive_hash, "size_bytes": archive_size},
        "prefix": prefix,
        "members": members,
        "inventories": inventories,
        "checks": {
            "thalia_manifest_checked": validation.checked,
            "thalia_required_paths": validation.required,
            "inventoried_output_closure": True,
            "frozen_input_bytes": True,
        },
    }


__all__ = ["assemble_release_artifacts", "load_release_allowlist"]
