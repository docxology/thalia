"""Real extractive/loopback benchmark accounting and fail-closed artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from src.benchmark_cli import main
from src.compiler.metrics import token_f1
from src.config import HarnessConfig
from src.evaluation.accounting import fingerprint_json
from src.evaluation.backend_benchmark import (
    BenchmarkBackend,
    build_benchmark_backends,
    run_backend_benchmark,
    validate_backend_benchmark,
    write_backend_benchmark,
)
from src.evaluation.dataset import build_research_dataset
from src.llm import OllamaLM
from src.module import ExtractiveLM
from src.signatures import TaskCategory

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_backend_benchmark.py"


@pytest.fixture
def loopback():
    """Serve actual ExtractiveLM completions over the real Ollama HTTP protocol."""
    state = {"requests": [], "fail_indices": set()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(request)
            if len(state["requests"]) in state["fail_indices"]:
                body = {"error": "private-provider-message-secret"}
                self.send_response(503)
            else:
                body = {"response": ExtractiveLM().complete(request["prompt"]), "done": True, "done_reason": "stop"}
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


@pytest.fixture
def complete_report():
    return run_backend_benchmark([], per_category=2, seed=7, limit=6)


def test_seeded_cohort_interleaves_categories_and_keeps_stable_identity(complete_report):
    payload = complete_report
    assert payload["status"] == "complete"
    assert [row["category"] for row in payload["examples"]] == [category.value for category in TaskCategory]
    source = build_research_dataset(per_category=2, seed=7)
    expected = [next(example for example in source if example.task_category == category).example_id for category in TaskCategory]
    assert [row["example_id"] for row in payload["examples"]] == expected
    summary = payload["backends"][0]
    assert summary["name"] == "extractive"
    assert (summary["n_requested"], summary["n_completed"], summary["n_failed"]) == (6, 6, 0)
    assert summary["mean_token_f1"] == pytest.approx(sum(row["token_f1"] for row in payload["rows"]) / 6)
    assert 0 <= summary["p50_latency_seconds"] <= summary["p95_latency_seconds"]
    for row in payload["rows"]:
        assert row["token_f1"] == token_f1(row["answer"], row["expected_answer"])
        assert row["latency_seconds"] >= 0
        assert row["error_class"] is None
    repeated = run_backend_benchmark([], per_category=2, seed=7, limit=6)
    for key in ("examples", "cohort", "config", "config_fingerprint", "dataset_fingerprint"):
        assert repeated[key] == payload[key]
    assert [(row["answer"], row["prompt_fingerprints"]) for row in repeated["rows"]] == [(row["answer"], row["prompt_fingerprints"]) for row in payload["rows"]]
    assert run_backend_benchmark([], per_category=2, seed=8, limit=6)["dataset_fingerprint"] != payload["dataset_fingerprint"]
    assert validate_backend_benchmark(payload) is None


def test_loopback_same_prompt_config_cohort_and_fresh_context(loopback):
    host, state = loopback
    backend = BenchmarkBackend("local", "ollama", "loopback-extractive", OllamaLM(host=host, timeout=2), {"temperature": 0.0})
    config = HarnessConfig(recall_memory=True, max_evidence=2, top_k=2)
    payload = run_backend_benchmark([backend], per_category=2, seed=2, limit=7, config=config)
    assert len(state["requests"]) == 7  # no retry/cache; repeated categories still get fresh examples
    assert len(payload["rows"]) == 14
    assert payload["config"] == config.to_dict()
    baseline = payload["rows"][:7]
    local = payload["rows"][7:]
    for original, observed, request in zip(baseline, local, state["requests"]):
        assert original["example_id"] == observed["example_id"]
        assert original["content_fingerprint"] == observed["content_fingerprint"]
        assert original["answer"] == observed["answer"]
        assert original["token_f1"] == observed["token_f1"]
        assert original["prompt_fingerprints"] == observed["prompt_fingerprints"] == [hashlib.sha256(request["prompt"].encode()).hexdigest()]
    assert payload["backends"][0]["mean_token_f1"] == payload["backends"][1]["mean_token_f1"]
    validate_backend_benchmark(payload)


def test_partial_failure_is_complete_accounting_not_complete_evidence(loopback, tmp_path):
    host, state = loopback
    state["fail_indices"] = {2}
    backend = BenchmarkBackend("local", "ollama", "loopback", OllamaLM(host=host, timeout=2))
    good = run_backend_benchmark([], limit=2)
    target = tmp_path / "benchmark.json"
    assert write_backend_benchmark(good, target) == target
    original_bytes = target.read_bytes()
    report = run_backend_benchmark([backend], limit=3)
    assert len(state["requests"]) == 3
    assert report["status"] == "incomplete"
    summary = report["backends"][1]
    assert (summary["n_requested"], summary["n_completed"], summary["n_failed"]) == (3, 2, 1)
    successes = [row for row in report["rows"][3:] if row["status"] == "complete"]
    assert summary["mean_token_f1"] == pytest.approx(sum(row["token_f1"] for row in successes) / 2)
    failed = report["rows"][4]
    assert failed["answer"] is None and failed["token_f1"] is None
    assert failed["error_class"] == "OllamaError"
    assert len(failed["prompt_fingerprints"]) == 1
    assert "private-provider-message-secret" not in json.dumps(report)
    diagnostic = write_backend_benchmark(report, target)
    assert diagnostic == tmp_path / "benchmark.incomplete.json"
    assert target.read_bytes() == original_bytes
    assert json.loads(diagnostic.read_text()) == report
    assert not list(tmp_path.glob("*.tmp"))
    validate_backend_benchmark(report)
    forged = copy.deepcopy(report)
    forged["status"] = "complete"
    with pytest.raises(ValueError, match="status mismatch"):
        validate_backend_benchmark(_resign(forged))


def test_all_failure_has_null_diagnostic_means(loopback):
    host, state = loopback
    state["fail_indices"] = {1, 2}
    report = run_backend_benchmark([BenchmarkBackend("local", "ollama", "loopback", OllamaLM(host=host, timeout=2))], limit=2)
    summary = report["backends"][1]
    assert summary["n_failed"] == 2
    assert summary["status"] == "incomplete"
    assert all(summary[key] is None for key in ("mean_token_f1", "mean_latency_seconds", "p50_latency_seconds", "p95_latency_seconds"))
    validate_backend_benchmark(report)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(schema_version=2),
    lambda p: p.update(schema_version=True),
    lambda p: p.update(metric="accuracy"),
    lambda p: p.update(status="skipped"),
    lambda p: p.update(n_examples=True),
    lambda p: p.update(n_examples=99),
    lambda p: p.update(dataset_fingerprint="0" * 64),
    lambda p: p.update(config_fingerprint="0" * 64),
    lambda p: p["examples"][0].update(example_id="invented"),
    lambda p: p["examples"][0].update(content_fingerprint="0" * 64),
    lambda p: p["examples"].append(p["examples"][0]),
    lambda p: p["rows"].pop(),
    lambda p: p["rows"].__setitem__(1, p["rows"][0]),
    lambda p: p["rows"][0].update(backend="unknown"),
    lambda p: p["rows"][0].update(example_id="unknown"),
    lambda p: p["rows"][0].update(expected_answer="mutated"),
    lambda p: p["rows"][0].update(config_fingerprint="0" * 64),
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
    lambda p: p["rows"][0].update(error_message="private"),
    lambda p: p["backends"][0].update(status="incomplete"),
    lambda p: p["backends"][0].update(n_completed=True),
    lambda p: p["backends"][0].update(n_failed=99),
    lambda p: p["backends"][0].update(mean_token_f1=-1),
    lambda p: p["backends"][0].update(p95_latency_seconds=999),
    lambda p: p["backends"][0].update(provider="other"),
    lambda p: p["backends"][0].update(generation_options={"api_key": "private"}),
    lambda p: p["config"].update(verify=True),
    lambda p: p["config"].update(unknown=True),
    lambda p: p["cohort"].update(seed=True),
    lambda p: p["cohort"].update(limit=0),
    lambda p: p.update(runtime_provenance=[]),
    lambda p: p.update(paired_comparisons=[]),
])
def test_validator_recomputes_not_just_checksums(complete_report, mutate):
    payload = copy.deepcopy(complete_report)
    mutate(payload)
    with pytest.raises(ValueError):
        validate_backend_benchmark(_resign(payload))


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


def test_duplicate_names_and_different_prompt_hashes_rejected(complete_report):
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
    {"seed": True}, {"config": HarnessConfig(verify=True)},
])
def test_run_rejects_invalid_plan_before_attempts(kwargs):
    with pytest.raises(ValueError):
        run_backend_benchmark([], **kwargs)


@pytest.mark.parametrize("options", [{"nested": {"authorization": "private"}}, {"temperature": float("nan")}, {"value": object()}, []])
def test_secret_or_non_json_options_rejected(options):
    with pytest.raises(ValueError):
        run_backend_benchmark([BenchmarkBackend("custom", "caller", "extractive", ExtractiveLM(), options)], limit=1)


def test_cloud_opt_in_precedes_requests_and_selector_options():
    with pytest.raises(ValueError, match="allow-cloud"):
        build_benchmark_backends(ollama_models=["local"], openrouter_models=["cloud"], observe_models=True)
    with pytest.raises(ValueError, match="allow_cloud"):
        run_backend_benchmark([BenchmarkBackend("cloud", "openrouter", "explicit", ExtractiveLM())], limit=1)
    backends = build_benchmark_backends(ollama_models=["small", "large"], openrouter_models=["explicit"], allow_cloud=True, timeout=4, max_tokens=77)
    assert [backend.name for backend in backends] == ["extractive", "ollama:small", "ollama:large", "openrouter:explicit"]
    assert backends[1].lm.options == {"temperature": 0.0, "num_predict": 77}
    assert backends[-1].generation_options == {"temperature": 0.0, "timeout": 4, "max_tokens": 77}
    for kwargs in ({"timeout": 0}, {"timeout": float("nan")}, {"max_tokens": 0}, {"ollama_models": [""]}, {"ollama_models": ["duplicate", "duplicate"]}):
        with pytest.raises(ValueError):
            build_benchmark_backends(**kwargs)


def _cli(*args, cwd=ROOT):
    # Deliberately empty credential environment: this test can never call cloud.
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
    assert payload["backends"][1]["n_failed"] == 2
    assert {row["error_class"] for row in payload["rows"][2:]} == {"OpenRouterError"}
    assert payload["runtime_provenance"]["models"]["openrouter:explicit-cloud"] == {}
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
        assert payload["cohort"] == {"per_category": 2, "seed": seed, "limit": 2}
        reports.append(payload)
    assert reports[0]["dataset_fingerprint"] != reports[1]["dataset_fingerprint"]
    assert (tmp_path / "first/output/data/backend_benchmark.json").exists()


def test_source_cli_runs_outside_checkout_with_caller_relative_output(tmp_path):
    result = _cli("--per-category", 2, "--limit", 2, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    artifact = tmp_path / result.stdout.strip()
    assert artifact == tmp_path / "output/data/backend_benchmark.json"
    payload = json.loads(artifact.read_text())
    validate_backend_benchmark(payload)
    assert payload["status"] == "complete"
    assert payload["n_examples"] == 2
    assert [backend["name"] for backend in payload["backends"]] == ["extractive"]


def test_caller_observation_is_public_and_not_a_cloud_digest_claim():
    backend = BenchmarkBackend("local", "caller", "selected", ExtractiveLM(), {}, {"digest": "observed-local-digest", "ollama_version": "observed-runtime"})
    payload = run_backend_benchmark([backend], limit=1)
    assert payload["runtime_provenance"]["models"]["local"] == backend.model_observation
    assert "paired_comparisons" not in payload
    assert validate_backend_benchmark(payload) is None
