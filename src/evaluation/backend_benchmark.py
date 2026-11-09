"""Method-aware, sequential LM observations with complete schema-2 accounting.

Prompt characters are not billed tokens; latency is end-to-end cell time, not
throughput, cost or production evidence. Checksums bind bytes, not authenticity.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import tempfile
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any, Iterator, Sequence, cast

from .. import __version__
from ..compiler.metrics import EvalExample, token_f1
from ..config import HarnessConfig
from ..harness import AutoHarness
from ..llm import OllamaLM, OpenRouterLM
from ..module import ExtractiveLM, LMClient, render_signature_prompt
from ..signatures import ReasonerSignature, TaskCategory
from .accounting import (
    file_provenance,
    fingerprint_example_content,
    fingerprint_examples,
    fingerprint_json,
    runtime_provenance,
)
from .benchmark_analysis import ANALYSIS_UNIT, analyze_benchmark_rows
from .dataset import build_research_dataset

EXECUTION_ORDER = "backend_outer; example_cohort_order; method_left_rotation_by_example_index; execution_index_zero_based"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_OBSERVATION_FIELDS = {
    "requested_model", "model", "digest", "modified_at", "size", "details",
    "available", "ollama_version",
}


@dataclass(frozen=True)
class BenchmarkBackend:
    """An explicitly selected client and its public (never credential) metadata."""

    name: str
    provider: str
    model: str
    lm: LMClient
    generation_options: dict[str, Any] = field(default_factory=dict)
    model_observation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkMethod:
    """A named method; full context has no harness configuration."""

    name: str
    kind: str
    config: HarnessConfig | None

    def __post_init__(self) -> None:
        _text(self.name, "method name")
        if self.kind == "full_context":
            if self.config is not None:
                raise ValueError("full_context requires config=None")
        elif self.kind == "harness":
            if not isinstance(self.config, HarnessConfig):
                raise ValueError("harness requires HarnessConfig")
            self.config.validate()
            if self.config.verify:
                raise ValueError("benchmark config.verify must be False (no re-answers)")
        else:
            raise ValueError("unknown method kind")


def build_benchmark_methods(
    names: Sequence[str] = ("harness",), *, config: HarnessConfig | None = None,
) -> list[BenchmarkMethod]:
    """Select unique built-ins, or construct BenchmarkMethod for custom configs."""
    if not names or isinstance(names, str) or len(set(names)) != len(names):
        raise ValueError("method names must be nonempty and unique")
    base = config if config is not None else HarnessConfig()
    selected = []
    for name in names:
        if name == "full_context":
            selected.append(BenchmarkMethod(name, "full_context", None))
        elif name == "harness":
            selected.append(BenchmarkMethod(name, "harness", base))
        elif name == "lexical_only":
            selected.append(BenchmarkMethod(name, "harness", base.with_(lexical_weight=1.0, semantic_weight=0.0)))
        elif name == "adaptive":
            selected.append(BenchmarkMethod(name, "harness", base.with_(adaptive_windows=True)))
        else:
            raise ValueError(f"unknown benchmark method: {name}")
    return selected


class _PromptRecorder:
    """Record the actual submitted prompt without changing it or retaining text."""

    def __init__(self, client: LMClient) -> None:
        self.client = client
        self.fingerprints: list[str] = []
        self.characters: int | None = None

    def complete(self, prompt: str) -> str:
        if self.fingerprints:
            raise ValueError("benchmark cells permit exactly one completion attempt")
        self.fingerprints.append(hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        self.characters = len(prompt)
        return self.client.complete(prompt)


class _SelectedOpenRouter:
    """Defer credentials to the accounted attempt; no probe, cache or retry."""

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


def _seed(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
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


def _same(actual: object, expected: object, label: str) -> None:
    # JSON equality also distinguishes bool/int and rejects extra nested fields.
    if fingerprint_json(actual) != fingerprint_json(expected):
        raise ValueError(f"{label} mismatch")


def _cohort(per_category: int, seeds: Sequence[int], limit: int | None) -> list[EvalExample]:
    _integer(per_category, "per_category", minimum=1)
    if not isinstance(seeds, (list, tuple)) or not seeds:
        raise ValueError("seeds must be a nonempty sequence of unique integers")
    for seed in seeds:
        _seed(seed, "seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")
    if limit is not None:
        _integer(limit, "limit", minimum=1)
    cohorts = [build_research_dataset(per_category=per_category, seed=seed) for seed in seeds]
    groups = [
        [[row for row in cohort if row.task_category == category] for category in TaskCategory]
        for cohort in cohorts
    ]
    ordered = [
        groups[(offset + category_index) % len(seeds)][category_index][index]
        for index in range(per_category)
        for offset in range(len(seeds))
        for category_index, _ in enumerate(TaskCategory)
    ]
    return ordered if limit is None else ordered[:limit]


def _example_plan(examples: Sequence[EvalExample]) -> list[dict[str, Any]]:
    return [
        {
            "example_id": example.example_id,
            "category": cast(TaskCategory, example.task_category).value,
            "stratum": example.stratum, "seed": example.seed,
            "content_fingerprint": fingerprint_example_content(example),
            "expected_answer": example.expected_answer,
        }
        for example in examples
    ]


def _method_plan(method: BenchmarkMethod) -> dict[str, Any]:
    method.__post_init__()
    identity = {"kind": method.kind, "config": method.config.to_dict() if method.config is not None else None}
    return {"name": method.name, **identity, "method_fingerprint": fingerprint_json(identity)}


def _execute(method: BenchmarkMethod, example: EvalExample, recorder: _PromptRecorder) -> str:
    if method.kind == "full_context":
        return recorder.complete(render_signature_prompt(
            ReasonerSignature, example.session_history.splitlines(), query=example.query,
        ))
    with AutoHarness(config=method.config, lm=recorder) as harness:
        return harness.run(example).answer


def _observed_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _producer_provenance() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    # Conservative installed-package inventory, not an executed-file trace.
    # Restrict traversal to src so checkout/venv locations never enter identity.
    paths = (root / "src").rglob("*.py")
    inventory = []
    for path in sorted(paths):
        record = file_provenance(path)
        record["path"] = path.relative_to(root).as_posix()
        inventory.append(record)
    return {
        "source_files": inventory, "source_fingerprint": fingerprint_json(inventory),
        "source_scope": "conservative_installed_src_python_inventory_not_executed_file_trace",
        "package": {"name": "thalia", "version": __version__, "installed_distribution_version": _observed_version("thalia")},
        "python": platform.python_version(),
        "dependencies": {name: _observed_version(name) for name in ("numpy", "matplotlib", "PyYAML", "dspy", "filelock")},
        "interpretation": "portable_source_checksums_not_authentication_or_provider_binary_attestation",
    }


def build_benchmark_backends(
    *, ollama_models: Sequence[str] = (), openrouter_models: Sequence[str] = (),
    timeout: float = 30.0, max_tokens: int = 1024, allow_cloud: bool = False,
    observe_models: bool = False, num_ctx: int | None = None,
) -> list[BenchmarkBackend]:
    """Select the baseline and requested adapters, without completion requests."""
    if openrouter_models and not allow_cloud:
        raise ValueError("OpenRouter selection requires --allow-cloud")
    if _number(timeout, "timeout") == 0:
        raise ValueError("timeout must be positive")
    _integer(max_tokens, "max_tokens", minimum=1)
    if num_ctx is not None:
        _integer(num_ctx, "num_ctx", minimum=1)
    selected = [BenchmarkBackend("extractive", "extractive", "ExtractiveLM", ExtractiveLM())]
    for provider, models in (("ollama", ollama_models), ("openrouter", openrouter_models)):
        for model in models:
            _text(model, "model")
            options: dict[str, Any] = {"temperature": 0.0, "timeout": timeout}
            client: LMClient
            observation = {}
            if provider == "ollama":
                generation = {"temperature": 0.0, "num_predict": max_tokens}
                if num_ctx is not None:
                    generation["num_ctx"] = num_ctx
                options.update(generation)
                client = OllamaLM(model=model, timeout=timeout, options=generation)
            else:
                options["max_tokens"] = max_tokens
                client = _SelectedOpenRouter(model, timeout, max_tokens)
            if provider == "ollama" and observe_models:
                from ..dspy_runtime.adapters import ollama_model_metadata

                observed = ollama_model_metadata(model=model)
                observation = {key: observed.get(key) for key in sorted(_OBSERVATION_FIELDS)}
            selected.append(BenchmarkBackend(f"{provider}:{model}", provider, model, client, options, observation))
    if len({backend.name for backend in selected}) != len(selected):
        raise ValueError("backend names must be unique")
    return selected


def _schedule(
    n_backends: int, n_methods: int, n_examples: int,
) -> Iterator[tuple[int, int, int]]:
    """Yield backend, method and example indices in the recorded execution order."""
    for backend_index in range(n_backends):
        for example_index in range(n_examples):
            rotation = example_index % n_methods
            for method_index in (*range(rotation, n_methods), *range(rotation)):
                yield backend_index, method_index, example_index


def _prepare_benchmark(
    backends: Sequence[BenchmarkBackend], *, methods: Sequence[BenchmarkMethod] | None,
    per_category: int, seeds: Sequence[int], limit: int | None, allow_cloud: bool,
    reference_method: str, n_boot: int, analysis_seed: int,
) -> tuple[list[BenchmarkBackend], list[BenchmarkMethod], list[EvalExample], dict[str, Any]]:
    """Resolve and validate one pure plan, without probing or executing clients."""
    selected = list(backends)
    if not any(backend.provider == "extractive" for backend in selected):
        selected.insert(0, BenchmarkBackend("extractive", "extractive", "ExtractiveLM", ExtractiveLM()))
    if len({backend.name for backend in selected}) != len(selected):
        raise ValueError("backend names must be unique")
    for backend in selected:
        for label in (backend.name, backend.provider, backend.model):
            _text(label, "backend identity")
        for label, value in (("generation_options", backend.generation_options), ("model_observation", backend.model_observation)):
            if not isinstance(value, dict):
                raise ValueError(f"{label} must be a public JSON object")
            _public_json(value)
        if not set(backend.model_observation) <= _OBSERVATION_FIELDS:
            raise ValueError("model_observation contains non-allowlisted fields")
        if (backend.provider == "openrouter" or isinstance(backend.lm, (OpenRouterLM, _SelectedOpenRouter))) and not allow_cloud:
            raise ValueError("OpenRouter selection requires allow_cloud=True")
        if not callable(getattr(backend.lm, "complete", None)):
            raise ValueError("backend lm must implement complete(prompt)")
    chosen = list(methods) if methods is not None else build_benchmark_methods()
    if not chosen or any(not isinstance(method, BenchmarkMethod) for method in chosen):
        raise ValueError("methods must be nonempty BenchmarkMethod selections")
    if len({method.name for method in chosen}) != len(chosen):
        raise ValueError("method names must be unique")
    method_plan = [_method_plan(method) for method in chosen]
    _text(reference_method, "reference_method")
    _integer(n_boot, "n_boot", minimum=1)
    _seed(analysis_seed, "analysis_seed")
    examples = _cohort(per_category, seeds, limit)
    plan = {
        "metric": "token_f1",
        "cohort": {"per_category": per_category, "seeds": list(seeds), "limit": limit},
        "dataset_fingerprint": fingerprint_examples(examples),
        "n_examples": len(examples), "examples": _example_plan(examples),
        "methods": method_plan,
        "backends": [{"name": backend.name, "provider": backend.provider, "model": backend.model,
                      "generation_options": json.loads(json.dumps(backend.generation_options))} for backend in selected],
        "analysis": {"reference_method": reference_method, "resamples": n_boot, "seed": analysis_seed,
                     "confidence": 0.95, "unit": ANALYSIS_UNIT},
        "execution_order": EXECUTION_ORDER,
    }
    return selected, chosen, examples, plan


def build_benchmark_plan(
    backends: Sequence[BenchmarkBackend], *, methods: Sequence[BenchmarkMethod] | None = None,
    per_category: int = 10, seeds: Sequence[int] = (0,), limit: int | None = None,
    allow_cloud: bool = False, reference_method: str = "full_context", n_boot: int = 2000,
    analysis_seed: int = 0,
) -> dict[str, Any]:
    """Return JSON-ready planned identities and attempt bounds, never observations.

    The schedule is identical to execution, including the extractive baseline,
    global cohort limit and method rotation. Counts do not predict successes,
    retained context, billed tokens, cost or elapsed time. No client is called
    and no runtime or producer provenance is collected.
    """
    selected, chosen, examples, plan = _prepare_benchmark(
        backends, methods=methods, per_category=per_category, seeds=seeds, limit=limit,
        allow_cloud=allow_cloud, reference_method=reference_method, n_boot=n_boot,
        analysis_seed=analysis_seed,
    )
    schedule = [
        {"execution_index": index, "backend": selected[backend_index].name,
         "method": chosen[method_index].name, "example_id": examples[example_index].example_id,
         "seed": examples[example_index].seed}
        for index, (backend_index, method_index, example_index) in enumerate(
            _schedule(len(selected), len(chosen), len(examples))
        )
    ]
    n_contrasts = len(chosen) - 1 if reference_method in {method.name for method in chosen} else 0
    return {
        "status": "planned", **plan, "schedule": schedule,
        "counts": {"backends": len(selected), "methods": len(chosen), "examples": len(examples),
                   "planned_attempts": len(schedule),
                   "planned_pairs": len(selected) * n_contrasts * len(examples)},
    }


def run_backend_benchmark(
    backends: Sequence[BenchmarkBackend], *, methods: Sequence[BenchmarkMethod] | None = None,
    per_category: int = 10, seeds: Sequence[int] = (0,), limit: int | None = None,
    allow_cloud: bool = False, reference_method: str = "full_context", n_boot: int = 2000,
    analysis_seed: int = 0,
) -> dict[str, Any]:
    """Execute the complete backend × method × seeded-example plan once.

    Backend-outer ordering avoids model thrashing. Methods rotate left by example
    index. A fresh harness owns each harness cell; full context uses the same
    typed Reasoner template with every history line, without retrieval filtering.
    """
    selected, chosen, examples, planned = _prepare_benchmark(
        backends, methods=methods, per_category=per_category, seeds=seeds, limit=limit,
        allow_cloud=allow_cloud, reference_method=reference_method, n_boot=n_boot,
        analysis_seed=analysis_seed,
    )
    method_plan = planned["methods"]
    dataset_digest = planned["dataset_fingerprint"]
    plan = planned["examples"]
    rows: list[dict[str, Any]] = []
    for backend_index, method_index, example_index in _schedule(len(selected), len(chosen), len(examples)):
        backend, method = selected[backend_index], chosen[method_index]
        example, identity = examples[example_index], plan[example_index]
        recorder = _PromptRecorder(backend.lm)
        started = perf_counter()
        answer, score, error_class = None, None, None
        try:
            answer = _execute(method, example, recorder)
            if not isinstance(answer, str):
                raise TypeError("LM answer must be text")
            if len(recorder.fingerprints) != 1:
                raise ValueError("complete cells require exactly one completion attempt")
            score = token_f1(answer, example.expected_answer)
            status = "complete"
        except Exception as exc:
            answer, score = None, None
            status, error_class = "failed", type(exc).__name__
        rows.append({
            **identity, "backend": backend.name, "method": method.name,
            "method_fingerprint": method_plan[method_index]["method_fingerprint"],
            "dataset_fingerprint": dataset_digest, "execution_index": len(rows),
            "prompt_fingerprints": recorder.fingerprints, "prompt_characters": recorder.characters,
            "answer": answer, "token_f1": score, "latency_seconds": perf_counter() - started,
            "status": status, "error_class": error_class,
        })
    payload = {
        "schema_version": 2, "status": "complete" if all(row["status"] == "complete" for row in rows) else "incomplete",
        "metric": planned["metric"], "cohort": planned["cohort"],
        "dataset_fingerprint": dataset_digest, "n_examples": len(examples), "examples": plan,
        "methods": method_plan, "backends": planned["backends"],
        "rows": rows,
        **analyze_benchmark_rows(rows, backends=[backend.name for backend in selected],
                                 methods=[method.name for method in chosen], examples=plan,
                                 reference_method=reference_method, n_boot=n_boot, analysis_seed=analysis_seed),
        "analysis": planned["analysis"],
        "runtime_provenance": runtime_provenance(
            models={backend.name: backend.model_observation for backend in selected},
            benchmark={"lane": "backend_benchmark", "timing": "end_to_end_cell_seconds"},
        ),
        "producer_provenance": _producer_provenance(), "execution_order": EXECUTION_ORDER,
    }
    payload["report_fingerprint"] = fingerprint_json(payload)
    validate_backend_benchmark(payload)
    return payload


def validate_backend_benchmark(payload: object) -> None:
    """Rebuild schema-2 planning/accounting; reject schema 1 without migration.

    Recorded source inventory is checked structurally, never against the reader's
    current checkout. Checksums are not signatures or authentication evidence.
    Validation never reconstructs prompts or calls any completion client. Prompt
    hashes and character counts establish consistency, not authenticated length.
    """
    try:
        _validate(payload)
    except (KeyError, TypeError, AttributeError, OverflowError, IndexError) as exc:
        raise ValueError("invalid backend benchmark schema") from exc


def _validate_producer(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "source_files", "source_fingerprint", "source_scope", "package", "python", "dependencies", "interpretation",
    }:
        raise ValueError("invalid producer provenance fields")
    files = value["source_files"]
    if not isinstance(files, list) or not files:
        raise ValueError("producer source inventory is required")
    paths = []
    for record in files:
        if set(record) != {"path", "size_bytes", "sha256"}:
            raise ValueError("invalid source inventory fields")
        path = _text(record["path"], "source path")
        portable = PurePosixPath(path)
        if portable.is_absolute() or ".." in portable.parts or "\\" in path or ":" in path or portable.as_posix() != path or not path.startswith("src/") or not path.endswith(".py"):
            raise ValueError("source paths must be portable project-relative Python paths")
        _integer(record["size_bytes"], "source size")
        if not isinstance(record["sha256"], str) or not _SHA256.fullmatch(record["sha256"]):
            raise ValueError("invalid source checksum")
        paths.append(path)
    if paths != sorted(set(paths)):
        raise ValueError("source inventory must be sorted and unique")
    if not {"src/__init__.py", "src/evaluation/backend_benchmark.py", "src/evaluation/benchmark_analysis.py"} <= set(paths):
        raise ValueError("producer inventory omits benchmark package implementation")
    if value["source_scope"] != "conservative_installed_src_python_inventory_not_executed_file_trace":
        raise ValueError("invalid producer inventory scope")
    _same(value["source_fingerprint"], fingerprint_json(files), "producer source fingerprint")
    package = value["package"]
    if not isinstance(package, dict) or set(package) != {"name", "version", "installed_distribution_version"} or package["name"] != "thalia":
        raise ValueError("invalid producer package")
    _text(package["version"], "package version")
    if package["installed_distribution_version"] is not None:
        _text(package["installed_distribution_version"], "installed distribution version")
    _text(value["python"], "producer python")
    dependencies = value["dependencies"]
    if not isinstance(dependencies, dict) or set(dependencies) != {"numpy", "matplotlib", "PyYAML", "dspy", "filelock"}:
        raise ValueError("invalid observed dependency versions")
    for version in dependencies.values():
        if version is not None:
            _text(version, "dependency version")
    if value["interpretation"] != "portable_source_checksums_not_authentication_or_provider_binary_attestation":
        raise ValueError("invalid source provenance interpretation")
    _public_json(value)


def _validate(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("backend benchmark must be an object")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 2:
        raise ValueError("unsupported backend benchmark schema; schema 2 is required")
    if set(payload) != {
        "schema_version", "status", "metric", "cohort", "dataset_fingerprint", "n_examples",
        "examples", "methods", "backends", "rows", "summaries", "groups", "comparisons",
        "analysis", "runtime_provenance", "producer_provenance", "execution_order", "report_fingerprint",
    } or payload["metric"] != "token_f1":
        raise ValueError("invalid backend benchmark fields or metric")
    _same(payload["report_fingerprint"], fingerprint_json({key: value for key, value in payload.items() if key != "report_fingerprint"}), "report fingerprint")
    cohort = payload["cohort"]
    if not isinstance(cohort, dict) or set(cohort) != {"per_category", "seeds", "limit"} or not isinstance(cohort["seeds"], list):
        raise ValueError("invalid cohort specification")
    examples = _cohort(**cohort)
    plan = _example_plan(examples)
    _same(payload["examples"], plan, "planned example identity")
    if _integer(payload["n_examples"], "n_examples", minimum=1) != len(plan):
        raise ValueError("planned example count mismatch")
    _same(payload["dataset_fingerprint"], fingerprint_examples(examples), "dataset fingerprint")
    methods = payload["methods"]
    if not isinstance(methods, list) or not methods:
        raise ValueError("nonempty methods required")
    for method in methods:
        if set(method) != {"name", "kind", "config", "method_fingerprint"}:
            raise ValueError("invalid method fields")
        config = None
        if method["kind"] == "harness":
            if not isinstance(method["config"], dict):
                raise ValueError("invalid harness configuration")
            config = HarnessConfig.from_dict(method["config"])
        elif method["config"] is not None:
            raise ValueError("full_context requires null config")
        chosen = BenchmarkMethod(method["name"], method["kind"], config)
        _same(method, _method_plan(chosen), "method configuration or fingerprint")
    method_names = [method["name"] for method in methods]
    if len(set(method_names)) != len(method_names):
        raise ValueError("duplicate method names")
    backends, rows = payload["backends"], payload["rows"]
    if not isinstance(backends, list) or not backends or not isinstance(rows, list):
        raise ValueError("backends and rows must be lists")
    for backend in backends:
        if set(backend) != {"name", "provider", "model", "generation_options"}:
            raise ValueError("invalid backend identity fields")
        for identity_field in ("name", "provider", "model"):
            _text(backend[identity_field], identity_field)
        if not isinstance(backend["generation_options"], dict):
            raise ValueError("generation_options must be an object")
        _public_json(backend["generation_options"])
    names = [backend["name"] for backend in backends]
    if len(set(names)) != len(names):
        raise ValueError("duplicate backend names")
    if not any(backend["provider"] == "extractive" for backend in backends):
        raise ValueError("extractive baseline is required")
    provenance = payload["runtime_provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {"python", "platform", "machine", "models", "benchmark"}:
        raise ValueError("invalid runtime provenance")
    for runtime_field in ("python", "platform", "machine"):
        _text(provenance[runtime_field], runtime_field)
    if not isinstance(provenance["models"], dict) or set(provenance["models"]) != set(names):
        raise ValueError("runtime model provenance mismatch")
    for observation in provenance["models"].values():
        if not isinstance(observation, dict) or not set(observation) <= _OBSERVATION_FIELDS:
            raise ValueError("non-allowlisted runtime model observation")
    _same(provenance["benchmark"], {"lane": "backend_benchmark", "timing": "end_to_end_cell_seconds"}, "runtime benchmark provenance")
    _public_json(provenance)
    _validate_producer(payload["producer_provenance"])
    _same(payload["execution_order"], EXECUTION_ORDER, "execution order")
    schedule = [
        (names[backend_index], method_names[method_index], plan[example_index])
        for backend_index, method_index, example_index in _schedule(len(names), len(methods), len(plan))
    ]
    if len(rows) != len(schedule):
        raise ValueError("incomplete planned backend/method/example matrix")
    method_digests = {method["name"]: method["method_fingerprint"] for method in methods}
    prompts: dict[tuple[str, str], tuple[str, int]] = {}
    for execution_index, (row, (backend, method, identity)) in enumerate(zip(rows, schedule)):
        if set(row) != {
            *identity, "backend", "method", "method_fingerprint", "dataset_fingerprint", "execution_index",
            "prompt_fingerprints", "prompt_characters", "answer", "token_f1", "latency_seconds", "status", "error_class",
        }:
            raise ValueError("invalid row fields")
        _same({field: row[field] for field in identity}, identity, "row example identity")
        _same((row["backend"], row["method"], row["execution_index"]), (backend, method, execution_index), "planned execution matrix")
        _same(row["dataset_fingerprint"], payload["dataset_fingerprint"], "row dataset fingerprint")
        _same(row["method_fingerprint"], method_digests[method], "row method fingerprint")
        _number(row["latency_seconds"], "latency_seconds")
        hashes = row["prompt_fingerprints"]
        if not isinstance(hashes, list) or len(hashes) > 1 or any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in hashes):
            raise ValueError("invalid prompt fingerprints")
        if hashes:
            characters = _integer(row["prompt_characters"], "prompt_characters", minimum=1)
            key = (identity["example_id"], method)
            observed = (hashes[0], characters)
            # These recorded observations establish cross-backend consistency,
            # not independent authentication of prompt contents or length.
            if key in prompts and prompts[key] != observed:
                raise ValueError("backends received different prompts or prompt character counts")
            prompts[key] = observed
        elif row["prompt_characters"] is not None:
            raise ValueError("unsubmitted prompt must have null characters")
        if row["status"] == "complete":
            if len(hashes) != 1 or not isinstance(row["answer"], str) or row["error_class"] is not None:
                raise ValueError("invalid complete row")
            _number(row["token_f1"], "token_f1", maximum=1.0)
            _same(row["token_f1"], token_f1(row["answer"], row["expected_answer"]), "token F1")
        elif row["status"] == "failed":
            if row["answer"] is not None or row["token_f1"] is not None or not isinstance(row["error_class"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", row["error_class"]):
                raise ValueError("invalid failed row")
        else:
            raise ValueError("invalid row status")
    analysis = payload["analysis"]
    if not isinstance(analysis, dict) or set(analysis) != {"reference_method", "resamples", "seed", "confidence", "unit"}:
        raise ValueError("invalid analysis fields")
    _text(analysis["reference_method"], "reference_method")
    _integer(analysis["resamples"], "resamples", minimum=1)
    _seed(analysis["seed"], "analysis seed")
    _same((analysis["confidence"], analysis["unit"]), (0.95, ANALYSIS_UNIT), "analysis specification")
    rebuilt = analyze_benchmark_rows(rows, backends=names, methods=method_names, examples=plan,
                                     reference_method=analysis["reference_method"], n_boot=analysis["resamples"],
                                     analysis_seed=analysis["seed"])
    for analysis_field, expected in rebuilt.items():
        _same(payload[analysis_field], expected, f"benchmark {analysis_field}")
    expected_status = "complete" if all(row["status"] == "complete" for row in rows) else "incomplete"
    _same(payload["status"], expected_status, "benchmark status")


def write_backend_benchmark(payload: dict[str, Any], path: str | Path) -> Path:
    """Atomically write complete reports; preserve the destination on failure."""
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


__all__ = [
    "BenchmarkBackend", "BenchmarkMethod", "build_benchmark_backends", "build_benchmark_methods",
    "build_benchmark_plan",
    "run_backend_benchmark", "validate_backend_benchmark", "write_backend_benchmark",
]
