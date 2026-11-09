"""Real extractive/HTTP method observations and fail-closed schema-2 evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import threading
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from statistics import mean

import pytest

from src.benchmark_cli import main
from src.compiler.metrics import token_f1
from src.config import HarnessConfig
from src.evaluation.accounting import fingerprint_json
from src.evaluation.backend_benchmark import (
    BenchmarkBackend,
    BenchmarkMethod,
    build_benchmark_backends,
    build_benchmark_methods,
    run_backend_benchmark,
    validate_backend_benchmark,
    write_backend_benchmark,
)
from src.evaluation.benchmark_analysis import (
    ANALYSIS_UNIT,
    analyze_benchmark_rows,
    summarize_prompt_exposure,
)
from src.evaluation.dataset import build_research_dataset
from src.evaluation.statistics import clustered_bootstrap_mean
from src.harness import AutoHarness
from src.llm import OllamaLM
from src.module import ExtractiveLM, render_signature_prompt
from src.signatures import ReasonerSignature, TaskCategory

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_backend_benchmark.py"


@pytest.fixture
def loopback():
    """Serve actual ExtractiveLM completions over the real Ollama HTTP protocol."""
    state = {"requests": [], "fail_indices": set(), "length_indices": set(), "bad_indices": set()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(request)
            index = len(state["requests"])
            if index in state["fail_indices"]:
                body = {"error": "private-provider-message-secret"}
                self.send_response(503)
            else:
                body = {"response": ExtractiveLM().complete(request["prompt"]), "done": True, "done_reason": "stop"}
                if index in state["length_indices"]:
                    body["done_reason"] = "length"
                if index in state["bad_indices"]:
                    body["response"] = []
                self.send_response(200)
            data = json.dumps(body).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _resign(payload):
    payload["report_fingerprint"] = fingerprint_json({key: value for key, value in payload.items() if key != "report_fingerprint"})
    return payload


def _local(host):
    return BenchmarkBackend("local", "ollama", "loopback-extractive", OllamaLM(host=host, timeout=2))


@pytest.fixture
def complete_report():
    return run_backend_benchmark([], methods=build_benchmark_methods(("full_context", "harness", "lexical_only")), per_category=2, seeds=(7, 8), limit=8, n_boot=31, analysis_seed=11)


def test_default_remains_harness_and_single_seed_category_order():
    payload = run_backend_benchmark([], per_category=2, seeds=(7,), limit=6)
    assert payload["schema_version"] == 2
    assert [method["name"] for method in payload["methods"]] == ["harness"]
    assert [row["category"] for row in payload["examples"]] == [category.value for category in TaskCategory]
    source = build_research_dataset(per_category=2, seed=7)
    expected = [next(example for example in source if example.task_category == category).example_id for category in TaskCategory]
    assert [row["example_id"] for row in payload["examples"]] == expected
    assert payload["comparisons"] == []  # reference not requested, not a fabricated zero effect
    summary = payload["summaries"][0]
    assert (summary["backend"], summary["method"]) == ("extractive", "harness")
    assert (summary["n_requested"], summary["n_completed"], summary["n_failed"]) == (6, 6, 0)
    assert summary["mean_token_f1"] == mean(row["token_f1"] for row in payload["rows"])
    assert 0 <= summary["p50_latency_seconds"] <= summary["p95_latency_seconds"]
    assert validate_backend_benchmark(payload) is None


def test_balanced_multiseed_plan_and_rotating_schedule(complete_report):
    payload = run_backend_benchmark([], methods=build_benchmark_methods(("full_context", "harness", "adaptive")), per_category=2, seeds=(0, 1, 2), n_boot=19)
    assert payload["n_examples"] == 36
    counts = Counter((row["category"], row["seed"]) for row in payload["examples"])
    assert set(counts.values()) == {2}
    first = payload["examples"][:6]
    assert [row["category"] for row in first] == [category.value for category in TaskCategory]
    assert [row["seed"] for row in first] == [0, 1, 2, 0, 1, 2]
    assert len({row["example_id"] for row in payload["examples"]}) == 36
    names = [method["name"] for method in payload["methods"]]
    for index, example in enumerate(payload["examples"]):
        rows = payload["rows"][index * 3:(index + 1) * 3]
        shift = index % 3
        assert [row["method"] for row in rows] == names[shift:] + names[:shift]
        assert all(row["example_id"] == example["example_id"] for row in rows)
    assert [row["execution_index"] for row in payload["rows"]] == list(range(108))
    repeated = run_backend_benchmark([], methods=build_benchmark_methods(("full_context", "harness", "lexical_only")), per_category=2, seeds=(7, 8), limit=8, n_boot=31, analysis_seed=11)
    for key in ("examples", "cohort", "methods", "dataset_fingerprint", "comparisons"):
        assert repeated[key] == complete_report[key]
    assert [(row["answer"], row["prompt_fingerprints"], row["prompt_characters"]) for row in repeated["rows"]] == [(row["answer"], row["prompt_fingerprints"], row["prompt_characters"]) for row in complete_report["rows"]]


def test_methods_hold_renderer_and_query_fixed_but_change_evidence(loopback):
    host, state = loopback
    base = HarnessConfig(recall_memory=True, max_evidence=2, top_k=2)
    methods = build_benchmark_methods(("full_context", "harness", "lexical_only", "adaptive"), config=base)
    payload = run_backend_benchmark([_local(host)], methods=methods, per_category=4, seeds=(2,), limit=20, n_boot=13)
    assert len(state["requests"]) == 80  # one actual request per local method/example cell
    assert len(payload["rows"]) == 160
    source = {example.example_id: example for example in build_research_dataset(per_category=4, seed=2)}
    baseline = {(row["example_id"], row["method"]): row for row in payload["rows"] if row["backend"] == "extractive"}
    local = [row for row in payload["rows"] if row["backend"] == "local"]
    for observed, request in zip(local, state["requests"]):
        original = baseline[(observed["example_id"], observed["method"])]
        assert original["answer"] == observed["answer"]
        assert original["token_f1"] == observed["token_f1"]
        assert observed["token_f1"] == token_f1(observed["answer"], observed["expected_answer"])
        assert observed["prompt_characters"] == len(request["prompt"])
        assert original["prompt_fingerprints"] == observed["prompt_fingerprints"] == [hashlib.sha256(request["prompt"].encode()).hexdigest()]
        example = source[observed["example_id"]]
        if observed["method"] == "full_context":
            assert request["prompt"] == render_signature_prompt(ReasonerSignature, example.session_history.splitlines(), query=example.query)
        else:
            method = next(method for method in methods if method.name == observed["method"])
            with AutoHarness(config=method.config, lm=ExtractiveLM()) as harness:
                assert observed["answer"] == harness.run(example).answer
    assert any(baseline[(example["example_id"], "full_context")]["prompt_fingerprints"] != baseline[(example["example_id"], "harness")]["prompt_fingerprints"] for example in payload["examples"])
    assert payload["methods"][1]["config"] == base.to_dict()
    assert methods[2].config.lexical_weight == 1.0 and methods[2].config.semantic_weight == 0.0
    assert methods[3].config.adaptive_windows
    assert not base.adaptive_windows and base.lexical_weight is None
    validate_backend_benchmark(payload)


def test_custom_named_configs_and_fingerprints_exclude_names():
    config = HarnessConfig(top_k=2, max_evidence=2)
    methods = [BenchmarkMethod("tight", "harness", config), BenchmarkMethod("same-config", "harness", config)]
    payload = run_backend_benchmark([], methods=methods, limit=1)
    assert payload["methods"][0]["method_fingerprint"] == payload["methods"][1]["method_fingerprint"]
    assert payload["rows"][0]["prompt_fingerprints"] == payload["rows"][1]["prompt_fingerprints"]
    with pytest.raises(ValueError, match="unique"):
        run_backend_benchmark([], methods=methods + methods, limit=1)


def test_group_accounting_and_seed_mean_intervals_recomputed(complete_report):
    payload = complete_report
    for field in ("category", "stratum"):
        for summary in payload["groups"][field]:
            rows = [row for row in payload["rows"] if row["backend"] == summary["backend"] and row["method"] == summary["method"] and row[field] == summary[field]]
            assert summary["n_requested"] == len(rows)
            assert summary["mean_token_f1"] == mean(row["token_f1"] for row in rows)
            assert summary["mean_prompt_characters"] == mean(row["prompt_characters"] for row in rows)
    matrix = {(row["method"], row["example_id"]): row for row in payload["rows"]}
    for contrast in payload["comparisons"]:
        by_seed = defaultdict(list)
        for example in payload["examples"]:
            by_seed[example["seed"]].append(matrix[(contrast["method"], example["example_id"])]["token_f1"] - matrix[("full_context", example["example_id"])]["token_f1"])
        means = {seed: [mean(values)] for seed, values in sorted(by_seed.items())}
        assert contrast["mean_delta"] == mean(values[0] for values in means.values())
        assert contrast["interval"] == clustered_bootstrap_mean(means, resamples=31, seed=11, unit=ANALYSIS_UNIT).to_dict()
        assert contrast["interval"]["small_cluster_warning"] is True
        assert contrast["interval"]["interval_interpretation"] == "descriptive_cluster_resampling_interval"
        assert "p_value" not in contrast and "p_value" not in contrast["interval"]
        assert contrast["wins"] + contrast["ties"] + contrast["losses"] == 8


def test_analysis_weights_seed_means_not_unequal_example_counts():
    # Arithmetic fixture for the pure analysis function, not measured LM evidence.
    examples = [{"example_id": str(index), "seed": seed, "category": "test", "stratum": "test"} for index, seed in enumerate((0, 0, 0, 1))]
    rows = []
    for method in ("full_context", "harness"):
        for example in examples:
            score = 1.0 if method == "harness" and example["seed"] == 0 else 0.0
            rows.append({**example, "backend": "arithmetic", "method": method, "status": "complete", "token_f1": score, "latency_seconds": 0.0, "prompt_characters": 1})
    contrast = analyze_benchmark_rows(rows, backends=["arithmetic"], methods=["full_context", "harness"], examples=examples, reference_method="full_context", n_boot=17, analysis_seed=4)["comparisons"][0]
    assert contrast["mean_delta"] == 0.5  # raw-pair mean would incorrectly be 0.75
    assert contrast["interval"]["estimate"] == 0.5
    assert contrast["interval"]["cluster_count"] == 2


def test_single_represented_seed_has_no_interval():
    methods = build_benchmark_methods(("full_context", "harness"))
    report = run_backend_benchmark([], methods=methods, seeds=(3,), limit=3)
    assert report["comparisons"][0]["n_seed_clusters"] == 1
    assert report["comparisons"][0]["mean_delta"] is not None
    assert report["comparisons"][0]["interval"] is None
    # Planned seeds alone cannot manufacture represented seed clusters.
    limited = run_backend_benchmark([], methods=methods, seeds=(3, 4), limit=1)
    assert limited["comparisons"][0]["interval"] is None


def test_partial_failure_suppresses_paired_estimate_and_preserves_last_good(loopback, tmp_path):
    host, state = loopback
    state["fail_indices"] = {2}
    target = tmp_path / "benchmark.json"
    good = run_backend_benchmark([], limit=2)
    assert write_backend_benchmark(good, target) == target
    original_bytes = target.read_bytes()
    report = run_backend_benchmark([_local(host)], methods=build_benchmark_methods(("full_context", "harness")), seeds=(0, 1), limit=8, n_boot=23)
    assert len(state["requests"]) == 16
    assert report["status"] == "incomplete"
    contrast = next(row for row in report["comparisons"] if row["backend"] == "local")
    assert (contrast["n_requested_pairs"], contrast["n_complete_pairs"], contrast["n_seed_clusters"]) == (8, 7, 2)
    assert contrast["mean_delta"] is None and contrast["interval"] is None
    assert contrast["wins"] + contrast["ties"] + contrast["losses"] == 7
    assert next(row for row in report["comparisons"] if row["backend"] == "extractive")["status"] == "complete"
    summary = next(row for row in report["summaries"] if row["backend"] == "local" and row["method"] == "harness")
    assert (summary["n_requested"], summary["n_completed"], summary["n_failed"]) == (8, 7, 1)
    successes = [row for row in report["rows"] if row["backend"] == "local" and row["method"] == "harness" and row["status"] == "complete"]
    assert summary["mean_token_f1"] == mean(row["token_f1"] for row in successes)
    failed = next(row for row in report["rows"] if row["status"] == "failed")
    assert failed["answer"] is None and failed["token_f1"] is None
    assert failed["error_class"] == "OllamaError" and len(failed["prompt_fingerprints"]) == 1
    assert failed["prompt_characters"] > 0
    assert "private-provider-message-secret" not in json.dumps(report)
    diagnostic = write_backend_benchmark(report, target)
    assert diagnostic == tmp_path / "benchmark.incomplete.json"
    assert target.read_bytes() == original_bytes
    assert json.loads(diagnostic.read_text()) == report
    assert not list(tmp_path.glob("*.tmp"))
    forged = copy.deepcopy(report)
    forged["status"] = "complete"
    with pytest.raises(ValueError, match="status mismatch"):
        validate_backend_benchmark(_resign(forged))
    forged = copy.deepcopy(report)
    next(row for row in forged["comparisons"] if row["backend"] == "local")["mean_delta"] = 0.0
    with pytest.raises(ValueError, match="comparisons"):
        validate_backend_benchmark(_resign(forged))


def test_all_failures_and_provider_incomplete_outputs_have_null_means(loopback):
    host, state = loopback
    state["fail_indices"], state["length_indices"], state["bad_indices"] = {1}, {2}, {3}
    report = run_backend_benchmark([_local(host)], limit=3)
    summary = next(row for row in report["summaries"] if row["backend"] == "local")
    assert len(state["requests"]) == 3
    assert summary["n_failed"] == 3 and summary["status"] == "incomplete"
    assert all(summary[key] is None for key in ("mean_token_f1", "mean_latency_seconds", "p50_latency_seconds", "p95_latency_seconds", "mean_prompt_characters"))
    validate_backend_benchmark(report)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(schema_version=1),
    lambda p: p.update(schema_version=True),
    lambda p: p.update(metric="accuracy"),
    lambda p: p.update(status="skipped"),
    lambda p: p.update(n_examples=True),
    lambda p: p.update(n_examples=99),
    lambda p: p.update(dataset_fingerprint="0" * 64),
    lambda p: p["examples"][0].update(example_id="invented"),
    lambda p: p["examples"][0].update(seed=True),
    lambda p: p["examples"][0].update(stratum="invented"),
    lambda p: p["examples"][0].update(content_fingerprint="0" * 64),
    lambda p: p["examples"].append(p["examples"][0]),
    lambda p: p["rows"].pop(),
    lambda p: p["rows"].__setitem__(1, p["rows"][0]),
    lambda p: p["rows"][0].update(backend="unknown"),
    lambda p: p["rows"][0].update(method="unknown"),
    lambda p: p["rows"][0].update(execution_index=True),
    lambda p: p["rows"][0].update(example_id="unknown"),
    lambda p: p["rows"][0].update(expected_answer="mutated"),
    lambda p: p["rows"][0].update(method_fingerprint="0" * 64),
    lambda p: p["rows"][0].update(latency_seconds=-1),
    lambda p: p["rows"][0].update(latency_seconds=float("inf")),
    lambda p: p["rows"][0].update(latency_seconds=True),
    lambda p: p["rows"][0].update(token_f1=float("nan")),
    lambda p: p["rows"][0].update(token_f1=2),
    lambda p: p["rows"][0].update(token_f1=True),
    lambda p: p["rows"][0].update(answer="a newly invented response"),
    lambda p: p["rows"][0].update(status="skipped"),
    lambda p: p["rows"][0].update(error_class="private error message"),
    lambda p: p["rows"][0].update(prompt_fingerprints=[]),
    lambda p: p["rows"][0].update(prompt_fingerprints=["not-a-hash"]),
    lambda p: p["rows"][0].update(prompt_characters=True),
    lambda p: p["rows"][0].update(prompt_characters=1),
    lambda p: p["rows"][0].update(error_message="private"),
    lambda p: p["summaries"][0].update(status="incomplete"),
    lambda p: p["summaries"][0].update(n_completed=True),
    lambda p: p["summaries"][0].update(n_failed=99),
    lambda p: p["summaries"][0].update(mean_token_f1=-1),
    lambda p: p["summaries"][0].update(p95_latency_seconds=999),
    lambda p: p["summaries"][0].update(mean_prompt_characters=1),
    lambda p: p["groups"]["category"].pop(),
    lambda p: p["groups"]["stratum"][0].update(n_completed=True),
    lambda p: p["comparisons"][0].update(mean_delta=42),
    lambda p: p["comparisons"][0].update(n_seed_clusters=True),
    lambda p: p["comparisons"][0].update(wins=99),
    lambda p: p["comparisons"][0]["interval"].update(low=-42),
    lambda p: p["comparisons"][0]["interval"].update(small_cluster_warning=False),
    lambda p: p["comparisons"][0].update(p_value=0.1),
    lambda p: p["backends"][0].update(provider="other"),
    lambda p: p["backends"][0].update(generation_options={"api_key": "private"}),
    lambda p: p["methods"][1]["config"].update(verify=True),
    lambda p: p["methods"][1]["config"].update(unknown=True),
    lambda p: p["methods"][0].update(config={}),
    lambda p: p["methods"][0].update(method_fingerprint="0" * 64),
    lambda p: p["methods"].append(p["methods"][0]),
    lambda p: p["cohort"].update(seeds=[True, 8]),
    lambda p: p["cohort"].update(seeds=[7, 7]),
    lambda p: p["cohort"].update(limit=0),
    lambda p: p["analysis"].update(resamples=0),
    lambda p: p["analysis"].update(seed=True),
    lambda p: p["analysis"].update(unit="example"),
    lambda p: p["analysis"].update(confidence=1),
    lambda p: p.update(execution_order="method_outer"),
    lambda p: p.update(runtime_provenance=[]),
    lambda p: p["runtime_provenance"]["models"]["extractive"].update(host="private-host"),
    lambda p: p["producer_provenance"].update(source_fingerprint="0" * 64),
    lambda p: p["producer_provenance"]["source_files"][0].update(path="/absolute/checkout.py"),
    lambda p: p["producer_provenance"]["source_files"][0].update(size_bytes=True),
    lambda p: p["producer_provenance"]["source_files"][0].update(sha256="invalid"),
    lambda p: p["producer_provenance"].update(interpretation="authenticated"),
    lambda p: p.update(config={}),
])
def test_validator_recomputes_not_just_checksums(complete_report, mutate):
    payload = copy.deepcopy(complete_report)
    mutate(payload)
    with pytest.raises(ValueError):
        validate_backend_benchmark(_resign(payload))


def test_producer_inventory_is_portable_and_not_reader_source_authentication(complete_report):
    producer = complete_report["producer_provenance"]
    inventory = producer["source_files"]
    assert producer["source_fingerprint"] == fingerprint_json(inventory)
    assert {record["path"] for record in inventory} == {path.relative_to(ROOT).as_posix() for path in (ROOT / "src").rglob("*.py")}
    assert producer["source_scope"] == "conservative_installed_src_python_inventory_not_executed_file_trace"
    for record in inventory:
        assert not Path(record["path"]).is_absolute()
        assert ".." not in Path(record["path"]).parts
        assert record["sha256"] == hashlib.sha256((ROOT / record["path"]).read_bytes()).hexdigest()
        assert record["size_bytes"] == (ROOT / record["path"]).stat().st_size
    assert str(ROOT) not in json.dumps(producer)
    payload = copy.deepcopy(complete_report)
    payload["producer_provenance"]["source_files"][0]["sha256"] = "0" * 64
    payload["producer_provenance"]["source_fingerprint"] = fingerprint_json(payload["producer_provenance"]["source_files"])
    # Historical producers may differ from installed consumers. A checksum is not
    # an authentication signature, and readers do not assert current-byte equality.
    validate_backend_benchmark(_resign(payload))


def test_prompt_observations_are_consistency_not_current_renderer_authentication(complete_report):
    payload = copy.deepcopy(complete_report)
    # A portable reader cannot authenticate these asserted observations by
    # running its own potentially different prompt implementation.
    for row in payload["rows"]:
        row["prompt_fingerprints"] = ["0" * 64]
        row["prompt_characters"] = 123
    payload.update(analyze_benchmark_rows(
        payload["rows"], backends=[backend["name"] for backend in payload["backends"]],
        methods=[method["name"] for method in payload["methods"]], examples=payload["examples"],
        reference_method=payload["analysis"]["reference_method"],
        n_boot=payload["analysis"]["resamples"], analysis_seed=payload["analysis"]["seed"],
    ))
    validate_backend_benchmark(_resign(payload))


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_prompt_exposure_collapses_backends_without_erasing_captured_failures(reverse_rows):
    rows = [
        {"backend": backend, "method": "full_context", "example_id": example_id,
         "status": "complete", "prompt_fingerprints": [fingerprint * 64]}
        for backend in ("first", "second")
        for example_id, fingerprint in (("a", "a"), ("b", "a"), ("c", "c"))
    ]
    rows += [
        {"backend": "first", "method": "harness", "example_id": "a",
         "status": "complete", "prompt_fingerprints": ["a" * 64]},
        {"backend": "second", "method": "harness", "example_id": "a",
         "status": "complete", "prompt_fingerprints": ["a" * 64]},
        {"backend": "first", "method": "harness", "example_id": "b",
         "status": "failed", "prompt_fingerprints": ["b" * 64]},
        {"backend": "second", "method": "harness", "example_id": "b",
         "status": "failed", "prompt_fingerprints": []},
        {"backend": "first", "method": "harness", "example_id": "c",
         "status": "failed", "prompt_fingerprints": []},
        {"backend": "second", "method": "harness", "example_id": "c",
         "status": "failed", "prompt_fingerprints": ["c" * 64]},
    ]
    if reverse_rows:
        rows.reverse()
    original = copy.deepcopy(rows)
    assert summarize_prompt_exposure(
        rows, methods=("full_context", "harness"), example_ids=("a", "b", "c"),
        reference_method="full_context",
    ) == [
        {"method": "full_context", "n_requested_cases": 3, "n_observed_cases": 3,
         "n_unique_prompts": 2, "n_compared_to_reference": 3,
         "n_different_from_reference": 0, "prompt_group": 1},
        {"method": "harness", "n_requested_cases": 3, "n_observed_cases": 3,
         "n_unique_prompts": 3, "n_compared_to_reference": 3,
         "n_different_from_reference": 1, "prompt_group": 2},
    ]
    assert rows == original


def test_prompt_exposure_groups_exact_case_vectors_not_unordered_prompt_sets():
    vectors = {
        "reference": ("a", "b", "a"),
        "swapped": ("b", "a", "a"),
        "same": ("a", "b", "a"),
    }
    rows = [
        {"method": method, "example_id": example_id, "prompt_fingerprints": [fingerprint * 64]}
        for method, vector in vectors.items()
        for example_id, fingerprint in zip(("first", "second", "third"), vector)
    ]
    summaries = summarize_prompt_exposure(
        rows, methods=("swapped", "reference", "same"),
        example_ids=("third", "first", "second"), reference_method="reference",
    )
    assert [row["method"] for row in summaries] == ["swapped", "reference", "same"]
    assert [row["n_unique_prompts"] for row in summaries] == [2, 2, 2]
    assert [row["prompt_group"] for row in summaries] == [1, 2, 2]
    assert [row["n_compared_to_reference"] for row in summaries] == [3, 3, 3]
    assert [row["n_different_from_reference"] for row in summaries] == [2, 0, 0]


def test_prompt_exposure_missing_prompts_never_establish_group_equivalence():
    vectors = {
        "partial": ("a", None, "c"),
        "same_missing": ("a", None, "c"),
        "unobserved": (None, None, None),
        "complete": ("a", "b", "c"),
        "complete_copy": ("a", "b", "c"),
    }
    rows = [
        {"method": method, "example_id": example_id,
         "prompt_fingerprints": [fingerprint * 64] if fingerprint else []}
        for method, vector in vectors.items()
        for example_id, fingerprint in zip(("a", "b", "c"), vector)
    ]
    summaries = summarize_prompt_exposure(
        rows, methods=tuple(vectors), example_ids=("a", "b", "c"),
        reference_method="partial",
    )
    assert [row["n_requested_cases"] for row in summaries] == [3] * 5
    assert [row["n_observed_cases"] for row in summaries] == [2, 2, 0, 3, 3]
    assert [row["n_unique_prompts"] for row in summaries] == [2, 2, 0, 3, 3]
    assert [row["n_compared_to_reference"] for row in summaries] == [2, 2, 0, 2, 2]
    assert [row["n_different_from_reference"] for row in summaries] == [0] * 5
    assert [row["prompt_group"] for row in summaries] == [None, None, None, 1, 1]


def test_prompt_exposure_absent_reference_is_not_an_observed_zero_difference():
    rows = [
        {"method": method, "example_id": "a", "prompt_fingerprints": ["a" * 64]}
        for method in ("selected", "unselected_reference")
    ]
    assert summarize_prompt_exposure(
        rows, methods=("selected", "missing"), example_ids=("a", "b"),
        reference_method="unselected_reference",
    ) == [
        {"method": "selected", "n_requested_cases": 2, "n_observed_cases": 1,
         "n_unique_prompts": 1, "n_compared_to_reference": 0,
         "n_different_from_reference": None, "prompt_group": None},
        {"method": "missing", "n_requested_cases": 2, "n_observed_cases": 0,
         "n_unique_prompts": 0, "n_compared_to_reference": 0,
         "n_different_from_reference": None, "prompt_group": None},
    ]


def test_prompt_exposure_empty_plan_does_not_group_empty_vectors():
    summaries = summarize_prompt_exposure(
        [], methods=("reference", "candidate"), example_ids=(),
        reference_method="reference",
    )
    assert summaries == [
        {"method": method, "n_requested_cases": 0, "n_observed_cases": 0,
         "n_unique_prompts": 0, "n_compared_to_reference": 0,
         "n_different_from_reference": 0, "prompt_group": None}
        for method in ("reference", "candidate")
    ]
    assert summarize_prompt_exposure(
        [], methods=(), example_ids=(), reference_method="reference",
    ) == []


def test_validator_rejects_mutation_before_writing(complete_report, tmp_path):
    target = tmp_path / "report.json"
    write_backend_benchmark(complete_report, target)
    original = target.read_bytes()
    complete_report["rows"][0]["latency_seconds"] += 1
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        write_backend_benchmark(complete_report, target)
    assert target.read_bytes() == original
    for payload in (None, [], {}, {"schema_version": 1}):
        with pytest.raises(ValueError):
            validate_backend_benchmark(payload)


def test_duplicate_backends_and_prompt_disagreement_rejected(complete_report):
    with pytest.raises(ValueError, match="unique"):
        run_backend_benchmark([BenchmarkBackend("extractive", "caller", "x", ExtractiveLM())], limit=1)
    report = run_backend_benchmark([BenchmarkBackend("second", "caller", "extractive", ExtractiveLM())], limit=1)
    report["rows"][1]["prompt_fingerprints"] = ["0" * 64]
    with pytest.raises(ValueError, match="different prompts"):
        validate_backend_benchmark(_resign(report))
    report = copy.deepcopy(complete_report)
    report["backends"].append(report["backends"][0])
    with pytest.raises(ValueError, match="duplicate backend"):
        validate_backend_benchmark(_resign(report))


@pytest.mark.parametrize("kwargs", [
    {"limit": 0}, {"limit": True}, {"per_category": 0}, {"per_category": True},
    {"seeds": (True,)}, {"seeds": ()}, {"seeds": (0, 0)}, {"seeds": "0"},
    {"methods": []}, {"n_boot": 0}, {"n_boot": True}, {"analysis_seed": True}, {"reference_method": ""},
])
def test_run_rejects_invalid_plan_before_attempts(kwargs):
    with pytest.raises(ValueError):
        run_backend_benchmark([], **kwargs)


@pytest.mark.parametrize("names", [("harness", "harness"), ("unknown",), (), "harness"])
def test_method_selector_rejects_invalid_selection(names):
    with pytest.raises(ValueError):
        build_benchmark_methods(names)


@pytest.mark.parametrize("name,kind,config", [
    ("", "harness", HarnessConfig()), ("named", "unknown", None),
    ("named", "harness", None), ("named", "full_context", HarnessConfig()),
    ("named", "harness", HarnessConfig(verify=True)),
])
def test_method_validation_before_execution(name, kind, config):
    with pytest.raises(ValueError):
        BenchmarkMethod(name, kind, config)


@pytest.mark.parametrize("options", [{"nested": {"authorization": "private"}}, {"temperature": float("nan")}, {"value": object()}, []])
def test_secret_or_non_json_options_rejected(options):
    with pytest.raises(ValueError):
        run_backend_benchmark([BenchmarkBackend("custom", "caller", "extractive", ExtractiveLM(), options)], limit=1)


def test_cloud_opt_in_precedes_requests_and_num_ctx_is_ollama_only():
    with pytest.raises(ValueError, match="allow-cloud"):
        build_benchmark_backends(ollama_models=["local"], openrouter_models=["cloud"], observe_models=True)
    with pytest.raises(ValueError, match="allow_cloud"):
        run_backend_benchmark([BenchmarkBackend("cloud", "openrouter", "explicit", ExtractiveLM())], limit=1)
    backends = build_benchmark_backends(ollama_models=["small", "large"], openrouter_models=["explicit"], allow_cloud=True, timeout=4, max_tokens=77, num_ctx=8192)
    assert [backend.name for backend in backends] == ["extractive", "ollama:small", "ollama:large", "openrouter:explicit"]
    assert backends[1].lm.options == {"temperature": 0.0, "num_predict": 77, "num_ctx": 8192}
    assert backends[1].generation_options["num_ctx"] == 8192
    assert "num_ctx" not in backends[-1].generation_options and not backends[0].generation_options
    assert backends[-1].generation_options == {"temperature": 0.0, "timeout": 4, "max_tokens": 77}
    for kwargs in ({"timeout": 0}, {"timeout": float("nan")}, {"max_tokens": 0}, {"num_ctx": 0}, {"num_ctx": True}, {"num_ctx": 2.5}, {"ollama_models": [""]}, {"ollama_models": ["duplicate", "duplicate"]}):
        with pytest.raises(ValueError):
            build_benchmark_backends(**kwargs)


def _cli(*args, cwd=ROOT):
    # Deliberately empty credential environment: this test cannot call cloud.
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], cwd=cwd, env={"THALIA_OPENROUTER_API_KEY": ""}, capture_output=True, text=True, timeout=30)


def test_cli_baseline_and_missing_key_preserve_last_good(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("THALIA_OPENROUTER_API_KEY", "")
    output = tmp_path / "benchmark.json"
    assert main(["--limit", "2", "--output", str(output)]) == 0
    assert str(output) in capsys.readouterr().out
    original = output.read_bytes()
    with pytest.raises(SystemExit) as refused:
        main(["--openrouter-model", "explicit-cloud", "--limit", "2", "--output", str(output)])
    assert refused.value.code == 2
    assert "--allow-cloud" in capsys.readouterr().err
    assert not (tmp_path / "benchmark.incomplete.json").exists()
    assert main(["--openrouter-model", "explicit-cloud", "--allow-cloud", "--limit", "2", "--output", str(output)]) == 1
    diagnostic = tmp_path / "benchmark.incomplete.json"
    streams = capsys.readouterr()
    assert str(diagnostic) in streams.out
    assert "destination preserved" in streams.err
    assert output.read_bytes() == original
    payload = json.loads(diagnostic.read_text())
    assert next(row for row in payload["summaries"] if row["backend"] == "openrouter:explicit-cloud")["n_failed"] == 2
    assert {row["error_class"] for row in payload["rows"] if row["backend"] == "openrouter:explicit-cloud"} == {"OpenRouterError"}
    assert payload["runtime_provenance"]["models"]["openrouter:explicit-cloud"] == {}
    validate_backend_benchmark(payload)


def test_cli_repeatable_methods_and_seeds(tmp_path, capsys):
    output = tmp_path / "comparison.json"
    assert main(["--method", "full_context", "--method", "harness", "--seed", "3", "--seed", "4", "--per-category", "1", "--output", str(output)]) == 0
    capsys.readouterr()
    payload = json.loads(output.read_text())
    assert payload["cohort"]["seeds"] == [3, 4]
    assert [method["name"] for method in payload["methods"]] == ["full_context", "harness"]
    assert payload["n_examples"] == 12 and len(payload["rows"]) == 24
    assert len(payload["comparisons"]) == 1 and payload["comparisons"][0]["interval"] is not None
    validate_backend_benchmark(payload)


def test_imported_cli_default_output_follows_each_callers_cwd(tmp_path, monkeypatch, capsys):
    reports = []
    for directory, seed in (("first", 7), ("second", 8)):
        cwd = tmp_path / directory
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        assert main(["--per-category", "2", "--limit", "2", "--seed", str(seed)]) == 0
        artifact = cwd / capsys.readouterr().out.strip()
        assert artifact == cwd / "output/data/backend_benchmark.json"
        payload = json.loads(artifact.read_text())
        validate_backend_benchmark(payload)
        assert payload["status"] == "complete"
        assert payload["cohort"] == {"per_category": 2, "seeds": [seed], "limit": 2}
        reports.append(payload)
    assert reports[0]["dataset_fingerprint"] != reports[1]["dataset_fingerprint"]


def test_source_cli_runs_outside_checkout_with_caller_relative_output(tmp_path):
    result = _cli("--per-category", 2, "--limit", 2, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    artifact = tmp_path / result.stdout.strip()
    assert artifact == tmp_path / "output/data/backend_benchmark.json"
    payload = json.loads(artifact.read_text())
    validate_backend_benchmark(payload)
    assert payload["status"] == "complete" and payload["n_examples"] == 2
    assert [backend["name"] for backend in payload["backends"]] == ["extractive"]


def test_caller_observation_is_allowlisted_public_metadata():
    backend = BenchmarkBackend("local", "caller", "selected", ExtractiveLM(), {}, {"digest": "observed-local-digest", "ollama_version": "observed-runtime"})
    payload = run_backend_benchmark([backend], limit=1)
    assert payload["runtime_provenance"]["models"]["local"] == backend.model_observation
    assert payload["comparisons"] == []
    with pytest.raises(ValueError, match="allowlisted"):
        run_backend_benchmark([BenchmarkBackend("local", "caller", "selected", ExtractiveLM(), {}, {"host": "private-host"})], limit=1)


def test_cli_malformed_config_is_rejected_without_exposing_content(tmp_path, capsys):
    secret = "private-configuration-sentinel"
    config = tmp_path / "malformed.yaml"
    config.write_text(f"top_k: [{secret}\n", encoding="utf-8")
    output = tmp_path / "never-created.json"
    with pytest.raises(SystemExit) as refused:
        main(["--config", str(config), "--output", str(output)])
    assert refused.value.code == 2
    streams = capsys.readouterr()
    assert secret not in streams.err and "Traceback" not in streams.err
    assert not output.exists()
    assert not (tmp_path / "never-created.incomplete.json").exists()
