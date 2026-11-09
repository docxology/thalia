"""Real offline benchmark files and publication receipts; no mocked boundaries."""

from __future__ import annotations

import hashlib
import json

import pytest

from src.evaluation.backend_benchmark import (
    BenchmarkBackend,
    build_benchmark_methods,
    run_backend_benchmark,
    validate_backend_benchmark,
)
from src.llm import CallableLM
from src.publication_inputs import validate_publication_inputs, write_benchmark_input_receipt


@pytest.fixture
def root(tmp_path):
    (tmp_path / "output/data").mkdir(parents=True)
    (tmp_path / "output/dashboard.html").write_text("<html>offline dashboard</html>\n")
    (tmp_path / "output/data/manuscript_variables.json").write_text('{"STATUS": "offline"}\n')
    return tmp_path


@pytest.fixture(scope="module")
def report():
    return run_backend_benchmark(
        [], methods=build_benchmark_methods(("full_context",)),
        per_category=1, limit=2, seeds=(0,), n_boot=3,
    )


def _stage(root, report, name="selected.json"):
    path = root / "output/data" / name
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return path


def _receipts(root, path):
    return [write_benchmark_input_receipt(consumer, path, project_root=root)
            for consumer in ("dashboard", "manuscript")]


def _change_receipt(path, section, field, value):
    payload = json.loads(path.read_text())
    if section is None:
        payload[field] = value
    else:
        payload[section][field] = value
    path.write_text(json.dumps(payload, sort_keys=True) + "\n")


def test_receipts_bind_final_artifacts_and_exact_selected_bytes(root, report):
    selected = _stage(root, report)
    paths = _receipts(root, selected)
    original = selected.read_bytes()
    for consumer, path in zip(("dashboard", "manuscript"), paths):
        payload = json.loads(path.read_text())
        assert payload["schema"] == 1 and payload["consumer"] == consumer
        assert payload["benchmark"] == {
            "selection": "staged", "portable": True, "path": "output/data/selected.json",
            "sha256": hashlib.sha256(original).hexdigest(),
            "report_fingerprint": report["report_fingerprint"],
            "dataset_fingerprint": report["dataset_fingerprint"], "status": "complete",
        }
        artifact = root / payload["artifact"]["path"]
        assert payload["artifact"]["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
        first = path.read_bytes()
        assert write_benchmark_input_receipt(consumer, selected, project_root=root).read_bytes() == first
    assert selected.read_bytes() == original
    assert validate_publication_inputs(root) == ()


def test_consistent_no_report_is_explicit_not_an_inferred_default(root, report):
    _stage(root, report, "backend_benchmark.json")
    paths = _receipts(root, None)
    for path in paths:
        benchmark = json.loads(path.read_text())["benchmark"]
        assert benchmark == {
            "selection": "not-recorded", "portable": True, "path": None,
            "sha256": None, "report_fingerprint": None, "dataset_fingerprint": None,
            "status": "not-recorded",
        }
    assert validate_publication_inputs(root) == ()


def test_incomplete_report_is_bound_without_becoming_a_success_claim(root):
    # This is a real callable adapter with an incompatible JSON parser, not a
    # mocked completion or pre-fabricated failure row. Its actual decode error
    # must remain represented in the valid diagnostic report and both receipts.
    backend = BenchmarkBackend("json-parser", "callable", "json.loads", CallableLM(json.loads))
    incomplete = run_backend_benchmark(
        [backend], methods=build_benchmark_methods(("full_context",)),
        per_category=1, limit=1, n_boot=3,
    )
    assert incomplete["status"] == "incomplete"
    validate_backend_benchmark(incomplete)
    selected = _stage(root, incomplete, "selected.incomplete.json")
    for path in _receipts(root, selected):
        assert json.loads(path.read_text())["benchmark"]["status"] == "incomplete"
    assert validate_publication_inputs(root) == ()


def test_missing_receipts_and_mixed_absent_selection_refuse(root, report):
    issues = validate_publication_inputs(root)
    assert len(issues) == 2
    selected = _stage(root, report)
    write_benchmark_input_receipt("dashboard", selected, project_root=root)
    assert validate_publication_inputs(root)
    write_benchmark_input_receipt("manuscript", None, project_root=root)
    assert "publication consumers selected different benchmark inputs" in validate_publication_inputs(root)


def test_different_valid_selected_reports_refuse(root, report):
    first = _stage(root, report, "first.json")
    second_report = run_backend_benchmark(
        [], methods=build_benchmark_methods(("full_context",)),
        per_category=1, limit=2, seeds=(1,), n_boot=3,
    )
    second = _stage(root, second_report, "second.json")
    write_benchmark_input_receipt("dashboard", first, project_root=root)
    write_benchmark_input_receipt("manuscript", second, project_root=root)
    assert report["report_fingerprint"] != second_report["report_fingerprint"]
    assert "publication consumers selected different benchmark inputs" in validate_publication_inputs(root)


def test_same_bytes_at_different_selected_paths_still_refuse(root, report):
    first = _stage(root, report, "first.json")
    second = _stage(root, report, "second.json")
    write_benchmark_input_receipt("dashboard", first, project_root=root)
    write_benchmark_input_receipt("manuscript", second, project_root=root)
    assert "publication consumers selected different benchmark inputs" in validate_publication_inputs(root)


@pytest.mark.parametrize("artifact", ["output/dashboard.html", "output/data/manuscript_variables.json"])
def test_post_receipt_artifact_mutation_refuses(root, report, artifact):
    _receipts(root, _stage(root, report))
    (root / artifact).write_bytes((root / artifact).read_bytes() + b" ")
    assert any("artifact receipt mismatch" in issue for issue in validate_publication_inputs(root))


def test_raw_report_mutation_refuses_even_with_unchanged_semantic_fingerprint(root, report):
    selected = _stage(root, report)
    _receipts(root, selected)
    selected.write_bytes(selected.read_bytes() + b"\n")
    validate_backend_benchmark(json.loads(selected.read_bytes()))
    assert any("benchmark receipt mismatch" in issue for issue in validate_publication_inputs(root))


def test_missing_selected_report_refuses(root, report):
    selected = _stage(root, report)
    _receipts(root, selected)
    selected.unlink()
    assert validate_publication_inputs(root)


def test_external_render_receipt_leaks_no_path_and_cannot_be_resealed_implicitly(root, report, tmp_path_factory):
    external = tmp_path_factory.mktemp("external") / "private-selection.json"
    external.write_text(json.dumps(report))
    paths = _receipts(root, external)
    for path in paths:
        payload = json.loads(path.read_text())
        assert str(external) not in path.read_text()
        assert payload["benchmark"]["path"] is None
        assert payload["benchmark"]["portable"] is False
        assert payload["benchmark"]["selection"] == "external"
    assert all("nonportable" in issue for issue in validate_publication_inputs(root))
    staged = _stage(root, report)
    # A copy alone is not a receipt migration. Both actual consumers must rerun.
    assert validate_publication_inputs(root)
    write_benchmark_input_receipt("dashboard", staged, project_root=root)
    assert validate_publication_inputs(root)
    write_benchmark_input_receipt("manuscript", staged, project_root=root)
    assert validate_publication_inputs(root) == ()


@pytest.mark.parametrize("section,field,value", [
    (None, "schema", 2), (None, "schema", True), (None, "consumer", "other"),
    ("artifact", "path", "output/other.html"), ("artifact", "sha256", "0" * 64),
    ("benchmark", "sha256", "0" * 64), ("benchmark", "report_fingerprint", "0" * 64),
    ("benchmark", "dataset_fingerprint", "0" * 64), ("benchmark", "status", "incomplete"),
    ("benchmark", "portable", False), ("benchmark", "selection", "invented"),
    ("benchmark", "portable", 1),
    ("benchmark", "path", "output/data/C:selected.json"),
    ("benchmark", "path", None), ("benchmark", "path", "output/other.json"),
    ("benchmark", "path", "output/data/../data/selected.json"),
    ("benchmark", "path", "/output/data/selected.json"),
    ("benchmark", "path", "output/data/./selected.json"),
    ("benchmark", "path", "output/data//selected.json"),
    ("benchmark", "path", "output/data/selected\\file.json"),
])
def test_receipt_mismatch_and_unsafe_paths_refuse(root, report, section, field, value):
    paths = _receipts(root, _stage(root, report))
    _change_receipt(paths[0], section, field, value)
    assert validate_publication_inputs(root)


@pytest.mark.parametrize("target", [
    "output/data/selected.json", "output/dashboard.html",
    "output/reports/dashboard_benchmark_input.json",
])
def test_symlinked_inputs_refuse(root, report, target):
    _receipts(root, _stage(root, report))
    path = root / target
    original = path.read_bytes()
    backing = root / (path.name + ".backing")
    backing.write_bytes(original)
    path.unlink()
    path.symlink_to(backing)
    assert any("symlink" in issue for issue in validate_publication_inputs(root))


def test_symlinked_parent_directory_refuses(root, report):
    _receipts(root, _stage(root, report))
    folder = root / "output/data"
    backing = root / "backing"
    folder.rename(backing)
    folder.symlink_to(backing, target_is_directory=True)
    assert any("symlink" in issue for issue in validate_publication_inputs(root))


@pytest.mark.parametrize("raw", [b"not JSON", b"[]", b'{"schema_version": 1}', b'{"bad": NaN}'])
def test_invalid_report_never_overwrites_existing_receipt(root, report, raw):
    selected = _stage(root, report)
    paths = _receipts(root, selected)
    previous = paths[0].read_bytes()
    selected.write_bytes(raw)
    with pytest.raises((ValueError, TypeError)):
        write_benchmark_input_receipt("dashboard", selected, project_root=root)
    assert paths[0].read_bytes() == previous
    assert validate_publication_inputs(root)


@pytest.mark.parametrize("raw", [b"[]", b"not JSON", b'{"schema": 1, "schema": 1}'])
def test_malformed_receipt_refuses(root, report, raw):
    paths = _receipts(root, _stage(root, report))
    paths[0].write_bytes(raw)
    assert validate_publication_inputs(root)


def test_writer_requires_real_artifact_and_report_and_known_consumer(root, report):
    selected = _stage(root, report)
    with pytest.raises(ValueError, match="consumer"):
        write_benchmark_input_receipt("unknown", selected, project_root=root)
    with pytest.raises(OSError):
        write_benchmark_input_receipt("dashboard", root / "output/data/missing.json", project_root=root)
    (root / "output/dashboard.html").unlink()
    with pytest.raises(OSError):
        write_benchmark_input_receipt("dashboard", selected, project_root=root)
    assert not (root / "output/reports/dashboard_benchmark_input.json").exists()


def test_writer_refuses_unstaged_internal_and_symlinked_selected_inputs(root, report):
    unstaged = root / "report.json"
    unstaged.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="output/data"):
        write_benchmark_input_receipt("dashboard", unstaged, project_root=root)
    selected = root / "output/data/selected.json"
    selected.symlink_to(unstaged)
    with pytest.raises(ValueError, match="symlink"):
        write_benchmark_input_receipt("dashboard", selected, project_root=root)
    with pytest.raises(ValueError, match="unsafe"):
        write_benchmark_input_receipt("dashboard", root / "output/data/../data/selected.json", project_root=root)
