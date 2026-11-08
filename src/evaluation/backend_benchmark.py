"""Optional, sequential LMClient observations on one seeded synthetic cohort.

Latency is end-to-end harness time, not throughput, price, or production evidence.
This artifact is deliberately independent of the retained neural/cloud measurements.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Sequence, cast

from ..compiler.metrics import EvalExample, token_f1
from ..config import HarnessConfig
from ..harness import AutoHarness
from ..llm import OllamaLM, OpenRouterLM
from ..module import ExtractiveLM, LMClient
from ..signatures import TaskCategory
from .accounting import (
    fingerprint_config,
    fingerprint_example_content,
    fingerprint_examples,
    fingerprint_json,
    runtime_provenance,
)
from .dataset import build_research_dataset
from .statistics import _quantile


@dataclass(frozen=True)
class BenchmarkBackend:
    """An explicitly selected client and its public (never credential) metadata."""

    name: str
    provider: str
    model: str
    lm: LMClient
    generation_options: dict[str, Any] = field(default_factory=dict)
    model_observation: dict[str, Any] = field(default_factory=dict)


class _PromptRecorder:
    """Compose around the actual client without changing the submitted prompt."""

    def __init__(self, client: LMClient) -> None:
        self.client = client
        self.fingerprints: list[str] = []

    def complete(self, prompt: str) -> str:
        self.fingerprints.append(hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        return self.client.complete(prompt)


class _SelectedOpenRouter:
    """Defer credential validation to the accounted attempt, not backend selection.

    Missing credentials therefore produce failed rows, not a skipped cloud model.
    No availability probe, retry, or completion cache is used.
    """

    def __init__(self, model: str, timeout: float, max_tokens: int) -> None:
        self.model, self.timeout, self.max_tokens = model, timeout, max_tokens

    def complete(self, prompt: str) -> str:
        return OpenRouterLM(
            model=self.model, timeout=self.timeout, max_tokens=self.max_tokens,
            temperature=0.0,
        ).complete(prompt)


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: object, label: str, *, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite nonnegative number")
    if not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
        raise ValueError(f"{label} is outside its finite bounds")
    return float(value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def _public_json(value: object) -> None:
    """Reject credential-bearing metadata rather than serializing client state."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or re.search(
                r"(?i)(secret|credential|password|authorization|api.?key|access.?token)", key
            ):
                raise ValueError("generation metadata must not contain credentials")
            _public_json(item)
    elif isinstance(value, list):
        for item in value:
            _public_json(item)
    elif value is None or isinstance(value, (str, bool)):
        return
    elif isinstance(value, (int, float)) and math.isfinite(value):
        return
    else:
        raise ValueError("generation metadata must be finite public JSON")


def _cohort(per_category: int, seed: int, limit: int | None) -> list[EvalExample]:
    _integer(per_category, "per_category", minimum=1)
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if limit is not None:
        _integer(limit, "limit", minimum=1)
    examples = build_research_dataset(per_category=per_category, seed=seed)
    # The builder groups by category. Round-robin before limiting so a quick run
    # samples across categories instead of silently measuring only the first one.
    groups = [[row for row in examples if row.task_category == category] for category in TaskCategory]
    ordered = [group[index] for index in range(per_category) for group in groups]
    return ordered if limit is None else ordered[:limit]


def _example_plan(examples: Sequence[EvalExample]) -> list[dict[str, Any]]:
    return [
        {
            "example_id": example.example_id,
            "category": cast(TaskCategory, example.task_category).value,
            "content_fingerprint": fingerprint_example_content(example),
            "expected_answer": example.expected_answer,
        }
        for example in examples
    ]


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [row for row in rows if row["status"] == "complete"]
    latencies = sorted(row["latency_seconds"] for row in successes)
    return {
        "status": "complete" if len(successes) == len(rows) else "incomplete",
        "n_requested": len(rows),
        "n_completed": len(successes),
        "n_failed": len(rows) - len(successes),
        "mean_token_f1": mean(row["token_f1"] for row in successes) if successes else None,
        "mean_latency_seconds": mean(latencies) if successes else None,
        "p50_latency_seconds": _quantile(latencies, 0.5) if successes else None,
        "p95_latency_seconds": _quantile(latencies, 0.95) if successes else None,
    }


def build_benchmark_backends(
    *, ollama_models: Sequence[str] = (), openrouter_models: Sequence[str] = (),
    timeout: float = 30.0, max_tokens: int = 1024, allow_cloud: bool = False,
    observe_models: bool = False,
) -> list[BenchmarkBackend]:
    """Select the baseline and requested adapters, with no model requests."""
    if openrouter_models and not allow_cloud:
        raise ValueError("OpenRouter selection requires --allow-cloud")
    if _number(timeout, "timeout") == 0:
        raise ValueError("timeout must be positive")
    _integer(max_tokens, "max_tokens", minimum=1)
    selected = [BenchmarkBackend("extractive", "extractive", "ExtractiveLM", ExtractiveLM())]
    for provider, models in (("ollama", ollama_models), ("openrouter", openrouter_models)):
        for model in models:
            _text(model, "model")
            options = {"temperature": 0.0, "timeout": timeout}
            client: LMClient
            observation = {}
            if provider == "ollama":
                options["num_predict"] = max_tokens
                client = OllamaLM(model=model, timeout=timeout, options={"temperature": 0.0, "num_predict": max_tokens})
            else:
                options["max_tokens"] = max_tokens
                client = _SelectedOpenRouter(model, timeout, max_tokens)
            if provider == "ollama" and observe_models:
                # SDK-free metadata only; omit raw helper errors and endpoint
                # addresses. A failed observation never skips generation.
                from ..dspy_runtime.adapters import ollama_model_metadata

                metadata = ollama_model_metadata(model=model)
                observation = {
                    key: metadata.get(key) for key in (
                        "requested_model", "model", "digest", "modified_at",
                        "size", "details", "available", "ollama_version",
                    )
                }
            selected.append(BenchmarkBackend(f"{provider}:{model}", provider, model, client, options, observation))
    if len({backend.name for backend in selected}) != len(selected):
        raise ValueError("backend names must be unique")
    return selected


def run_backend_benchmark(
    backends: Sequence[BenchmarkBackend], *, per_category: int = 10, seed: int = 0,
    limit: int | None = None, config: HarnessConfig | None = None,
    allow_cloud: bool = False,
) -> dict[str, Any]:
    """Run every planned backend/example once; failures remain diagnostic rows.

    An extractive baseline is prepended if absent. Cloud clients require explicit
    consent even through this Python API. ``verify`` must be off: this lane makes
    one generation attempt per example, never retries or verification re-answers.
    """
    selected = list(backends)
    if not any(backend.provider == "extractive" for backend in selected):
        selected.insert(0, BenchmarkBackend("extractive", "extractive", "ExtractiveLM", ExtractiveLM()))
    if len({backend.name for backend in selected}) != len(selected):
        raise ValueError("backend names must be unique")
    for backend in selected:
        for label in (backend.name, backend.provider, backend.model):
            _text(label, "backend identity")
        if not isinstance(backend.generation_options, dict):
            raise ValueError("generation_options must be a public JSON object")
        _public_json(backend.generation_options)
        if not isinstance(backend.model_observation, dict):
            raise ValueError("model_observation must be a public JSON object")
        _public_json(backend.model_observation)
        if (backend.provider == "openrouter" or isinstance(backend.lm, (OpenRouterLM, _SelectedOpenRouter))) and not allow_cloud:
            raise ValueError("OpenRouter selection requires allow_cloud=True")
        if not callable(getattr(backend.lm, "complete", None)):
            raise ValueError("backend lm must implement complete(prompt)")
    config = config if config is not None else HarnessConfig()
    config.validate()
    if config.verify:
        raise ValueError("benchmark config.verify must be False (no re-answers)")
    examples = _cohort(per_category, seed, limit)
    dataset_digest = fingerprint_examples(examples)
    config_digest = fingerprint_config(config)
    plan = _example_plan(examples)
    rows: list[dict[str, Any]] = []
    summaries = []
    for backend in selected:
        backend_rows = []
        for example, identity in zip(examples, plan):
            recorder = _PromptRecorder(backend.lm)
            started = perf_counter()
            answer, score, error_class = None, None, None
            try:
                with AutoHarness(config=config, lm=recorder) as harness:
                    answer = harness.run(example).answer
                if not isinstance(answer, str):
                    raise TypeError("LM answer must be text")
                score = token_f1(answer, example.expected_answer)
                status = "complete"
            except Exception as exc:
                answer, score = None, None
                status = "failed"
                # No provider message, traceback, URL or credential is retained.
                error_class = type(exc).__name__
            elapsed = perf_counter() - started
            row = {
                **identity, "backend": backend.name, "dataset_fingerprint": dataset_digest,
                "config_fingerprint": config_digest, "prompt_fingerprints": recorder.fingerprints,
                "answer": answer, "token_f1": score, "latency_seconds": elapsed,
                "status": status, "error_class": error_class,
            }
            rows.append(row)
            backend_rows.append(row)
        summaries.append({
            "name": backend.name, "provider": backend.provider, "model": backend.model,
            "generation_options": json.loads(json.dumps(backend.generation_options)),
            **_summary(backend_rows),
        })
    payload = {
        "schema_version": 1, "status": "complete" if all(row["status"] == "complete" for row in rows) else "incomplete",
        "metric": "token_f1", "dataset_fingerprint": dataset_digest,
        "config_fingerprint": config_digest, "n_examples": len(examples),
        "config": config.to_dict(), "cohort": {"per_category": per_category, "seed": seed, "limit": limit},
        "examples": plan, "backends": summaries, "rows": rows,
        "runtime_provenance": runtime_provenance(
            models={backend.name: backend.model_observation for backend in selected},
            benchmark={"lane": "backend_benchmark", "timing": "end_to_end_harness_seconds"},
        ),
    }
    payload["report_fingerprint"] = fingerprint_json(payload)
    validate_backend_benchmark(payload)
    return payload


def validate_backend_benchmark(payload: object) -> None:
    """Reject malformed, mutated or misaccounted reports; allow honest incomplete ones.

    Fingerprints detect accidental mutation, not adversarially re-signed evidence.
    The seeded cohort is rebuilt, so omitted examples cannot masquerade as a
    completed plan by merely editing counts and refreshing a report checksum.
    """
    try:
        _validate(payload)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("invalid backend benchmark schema") from exc


def _validate(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("backend benchmark must be an object")
    required_fields = {
        "schema_version", "status", "metric", "dataset_fingerprint",
        "config_fingerprint", "n_examples", "config", "cohort", "examples",
        "backends", "rows", "runtime_provenance", "report_fingerprint",
    }
    if set(payload) != required_fields:
        raise ValueError("invalid backend benchmark fields")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1 or payload.get("metric") != "token_f1":
        raise ValueError("unsupported backend benchmark version or metric")
    if payload.get("status") not in ("complete", "incomplete"):
        raise ValueError("invalid benchmark status")
    digest = payload.get("report_fingerprint")
    if digest != fingerprint_json({key: value for key, value in payload.items() if key != "report_fingerprint"}):
        raise ValueError("report fingerprint mismatch")
    cohort = payload["cohort"]
    if set(cohort) != {"per_category", "seed", "limit"}:
        raise ValueError("invalid cohort specification")
    examples = _cohort(**cohort)
    plan = _example_plan(examples)
    if payload["examples"] != plan or _integer(payload["n_examples"], "n_examples", minimum=1) != len(plan):
        raise ValueError("planned example identity mismatch")
    if payload["dataset_fingerprint"] != fingerprint_examples(examples):
        raise ValueError("dataset fingerprint mismatch")
    config = HarnessConfig.from_dict(payload["config"])
    if config.to_dict() != payload["config"] or config.verify:
        raise ValueError("invalid benchmark configuration")
    if payload["config_fingerprint"] != fingerprint_config(config):
        raise ValueError("config fingerprint mismatch")
    if not isinstance(payload["runtime_provenance"], dict):
        raise ValueError("runtime_provenance must be an object")
    _public_json(payload["runtime_provenance"])
    summaries, rows = payload["backends"], payload["rows"]
    if not isinstance(summaries, list) or not summaries or not isinstance(rows, list):
        raise ValueError("backends and rows must be nonempty lists")
    names = [_text(backend["name"], "backend name") for backend in summaries]
    if len(set(names)) != len(names):
        raise ValueError("duplicate backend names")
    if not any(backend["provider"] == "extractive" for backend in summaries):
        raise ValueError("extractive baseline is required")
    if len(rows) != len(names) * len(plan):
        raise ValueError("incomplete planned backend/example matrix")
    matrix = {}
    prompts: dict[str, str] = {}
    identities = {row["example_id"]: row for row in plan}
    for row in rows:
        if set(row) != {
            "backend", "example_id", "category", "content_fingerprint",
            "expected_answer", "dataset_fingerprint", "config_fingerprint",
            "prompt_fingerprints", "answer", "token_f1", "latency_seconds",
            "status", "error_class",
        }:
            raise ValueError("invalid row fields")
        name, example_id = row["backend"], row["example_id"]
        key = (name, example_id)
        if name not in names or example_id not in identities or key in matrix:
            raise ValueError("unknown or duplicate backend/example row")
        matrix[key] = row
        if any(row[field] != value for field, value in identities[example_id].items()):
            raise ValueError("row example identity mismatch")
        if any(row[field] != payload[field] for field in ("config_fingerprint", "dataset_fingerprint")):
            raise ValueError("row fingerprint mismatch")
        _number(row["latency_seconds"], "latency_seconds")
        hashes = row["prompt_fingerprints"]
        if not isinstance(hashes, list) or len(hashes) > 1 or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes):
            raise ValueError("invalid prompt fingerprints")
        if hashes:
            if example_id in prompts and hashes[0] != prompts[example_id]:
                raise ValueError("backends received different prompts")
            prompts[example_id] = hashes[0]
        if row["status"] == "complete":
            if len(hashes) != 1 or not isinstance(row["answer"], str) or row["error_class"] is not None:
                raise ValueError("invalid complete row")
            _number(row["token_f1"], "token_f1", maximum=1.0)
            if row["token_f1"] != token_f1(row["answer"], row["expected_answer"]):
                raise ValueError("token F1 does not match answer")
        elif row["status"] == "failed":
            if row["answer"] is not None or row["token_f1"] is not None or not isinstance(row["error_class"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", row["error_class"]):
                raise ValueError("invalid failed row")
        else:
            raise ValueError("invalid row status")
    for backend in summaries:
        if set(backend) != {
            "name", "provider", "model", "generation_options", "status",
            "n_requested", "n_completed", "n_failed", "mean_token_f1",
            "mean_latency_seconds", "p50_latency_seconds", "p95_latency_seconds",
        }:
            raise ValueError("invalid backend summary fields")
        _text(backend["provider"], "provider")
        _text(backend["model"], "model")
        if not isinstance(backend["generation_options"], dict):
            raise ValueError("generation_options must be an object")
        _public_json(backend["generation_options"])
        expected = _summary([matrix[(backend["name"], example["example_id"])] for example in plan])
        for summary_field, value in expected.items():
            if summary_field.startswith("n_"):
                _integer(backend[summary_field], summary_field)
            elif summary_field != "status" and backend[summary_field] is not None:
                _number(backend[summary_field], summary_field, maximum=1.0 if summary_field == "mean_token_f1" else None)
            if backend[summary_field] != value:
                raise ValueError(f"backend summary mismatch: {summary_field}")
    expected_status = "complete" if all(row["status"] == "complete" for row in rows) else "incomplete"
    if payload["status"] != expected_status:
        raise ValueError("benchmark status mismatch")


def write_backend_benchmark(payload: dict[str, Any], path: str | Path) -> Path:
    """Atomically write a complete report; preserve last-good output on failure.

    Incomplete evidence is written to ``<stem>.incomplete.json`` instead and
    returned to the caller. It is never promoted onto the requested destination.
    """
    validate_backend_benchmark(payload)
    target = Path(path)
    if payload["status"] != "complete":
        target = target.with_name(f"{target.stem}.incomplete.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


__all__ = ["BenchmarkBackend", "build_benchmark_backends", "run_backend_benchmark", "validate_backend_benchmark", "write_backend_benchmark"]
