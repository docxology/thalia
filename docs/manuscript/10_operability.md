# Operability: Configuration, Sessions, Adapters, and CLI {#sec:operability}

THALIA is an operable design. This section documents the
configuration system, the real language-model adapters, the persistent multi-turn
session, and the command-line interface. Each has dedicated Zero-Mock coverage in
the strict local suite, including a real in-process HTTP server for the network
adapter. The suite covers the local tested path; deployment integrations require
their own acceptance checks.

## Configuration Precedence and Validation {#sec:op-config}

The tunable parameter vector is :class:`HarnessConfig` ([@sec:stage-compiler]). It
is loadable, overridable, and serialisable:

- **File** — `load_config(path)` reads a harness YAML file
  (`config/harness.yaml` ships as the canonical default). The YAML may list fields
  flat or under a `harness:` key; manuscript `config.yaml` keeps renderer metadata
  separate and mirrors selected values only under `project_config.harness`.
- **Environment** — any field is overridable via `THALIA_<FIELD>`. Three example
  overrides are:
  - `THALIA_TOP_K=<integer>` for the retrieval depth.
  - `THALIA_LEXICAL_WEIGHT=<lexical>` for the lexical lane weight.
  - `THALIA_SEMANTIC_WEIGHT=<semantic>` for the semantic lane weight.
  Lane weights remain both-or-neither; setting only one against an unset pair
  raises.
  Provider credentials are separate from harness-field overrides:
  `THALIA_OPENROUTER_API_KEY` supplies an OpenRouter key. Model selection is an
  explicit adapter `model=` argument or benchmark `--openrouter-model` option,
  not a `THALIA_OPENROUTER_MODEL` environment variable. Credentials alone never
  select a cloud backend for the common benchmark.
- **Round-trip** — `to_dict` / `from_dict`, `to_yaml` / `from_yaml`, and
  `save_config` make a config serialisable and reproducible; `from_dict` and
  `from_yaml` ignore unrecognised keys. `to_yaml` is the single serialisation
  path — `save_config` delegates to it, so the YAML representation stays identical
  from the dataclass.

Precedence, lowest to highest: built-in defaults → file → environment → explicit
CLI flags.

This precedence order is part of the reproducibility story. A manuscript render
can point to the checked-in `config/harness.yaml`; a local experiment can override
one field through `THALIA_*`; and a CLI run can still make an explicit one-off
choice without mutating source files. The resulting configuration is serialisable,
so a compiled or manually selected setting can be saved and compared later.

## Composable Pipeline and Stage Inspection {#sec:op-pipeline}

`AutoHarness` bundles the {{CONFIG_NUM_RUNTIME_STAGES}} runtime stages into one `forward` call. For
callers that need to inspect or modify the stage chain — insert a logging hook,
a custom reranker, or run a partial pipeline — `src/pipeline.py::Pipeline`
exposes the same stages as an explicit, chainable sequence:

```python
from src.pipeline import Pipeline

pipe = (
    Pipeline(config)
    .with_inspector()
    .add_step(
        "log",
        lambda ctx: (
            ctx.extras.update({"n": len(ctx.evidence_windows)}), ctx
        )[1],
    )
    .with_retriever()
    .with_reasoner()
    .with_memory_gate()
)
out = pipe.run(query="What is the wifi password?", session_history="...")
for step_name, ctx in pipe.intermediates:
    print(step_name, ctx.extras)
```

Each `with_*` method appends one stage and returns `self` for chaining;
`add_step` inserts an arbitrary callable that receives and returns a
`PipelineContext` (a mutable state bag with an `extras` dict for custom data).
After `run`, `pipe.intermediates` returns defensive deep copies of the
`(step_name, context)` snapshots, so inspection cannot mutate the recorded trace.
Partial chains intentionally retain absent-stage state; constructing
`HarnessOutput` afterward is not another runtime step. The offline Compiler
remains the additional architectural stage, not part of `with_all_stages()`.
`scripts/run_pipeline.py` writes this composition trace to `output/data/`.

## Resource Safety and Context-Manager Cleanup {#sec:op-resource-safety}

`Session` and `EpisodicStore` both implement the context-manager protocol
(`__enter__` / `__exit__`), so resources are always cleaned up — even when an
exception propagates mid-turn:

```python
with Session(db_path="episodes.db", memory_path="MEMORY.md") as s:
    s.ask("My wifi password is bluefish42")
    s.ask("What is the wifi password?")
# episodic store closed + MEMORY.md flushed automatically
```

The demo script (`src/demo.py`) uses this pattern, so the context-manager path
is exercised by the default analysis pipeline as well as the test suite.

`AutoHarness` and `Pipeline` expose the same context-manager contract. They close
only stores they created internally; a store supplied by the caller remains the
caller’s responsibility. `EpisodicStore.close()` is idempotent, so cleanup is
safe in both nested context managers and explicit `finally` blocks. The strict
suite runs with `ResourceWarning` promoted to an error to make a leaked SQLite
connection fails the resource contract.

The standalone preflight reports independent readiness states for the
deterministic core, DSPy SDK, Ollama server, Gemma model, embedding model,
LongMemEval payload, and template renderer. Optional neural/benchmark states remain
independent of deterministic operation; the fail-closed artifact validator remains
the local release boundary.

## Package Metadata and Type Distribution {#sec:op-metadata}

The package exports `__version__` at the top level (`from src import __version__`)
and ships a `py.typed` marker (PEP 561) so downstream type checkers see the full
type annotations. `HarnessOutput.to_dict()` provides JSON serialisation on the
dataclass itself — the CLI delegates to it, so the field mapping has one source
of truth.

## Language-Model Protocol and Adapters {#sec:op-lm}

The deterministic core uses the extractive responder, but a real model plugs in
behind the one-method `LMClient` protocol:

- **`CallableLM(fn)`** — wrap any `Callable[[str], str]` (an SDK call, a local
  function). The smallest possible real adapter.
- **`OllamaLM(model, host)`** — call a local Ollama server's `/api/generate`
  endpoint using only the standard library (no third-party dependency). Failures
  raise `OllamaError`; the adapter emits no empty answer on error. The
  `is_available()` method offers a best-effort liveness probe. The adapter is
  opt-in and the default core leaves it unused.
- **`OpenRouterLM(model=..., api_key=...)`** — the direct `LMClient` adapter
  in `src.llm`, using the OpenRouter chat-completions endpoint without DSPy.
  An omitted key is read from `THALIA_OPENROUTER_API_KEY`; missing credentials,
  transport failures, and malformed completion content raise `OpenRouterError`.
  Pass `model=` explicitly to select the provider model.
- **`configure_openrouter(model=..., api_key=...)`** — the separate optional
  `src.dspy_runtime` function configures global DSPy state through
  `dspy.LM` and litellm. It does not inject an LM into `AutoHarness`.

The direct Ollama/OpenRouter adapters have real in-process HTTP-server tests for
request construction and response parsing; those tests are not live-provider
quality checks and do not establish the DSPy configuration function's behavior.
Live neural DSPy tests require an explicit opt-in in addition to their SDK,
server, and model prerequisites; generation does not occur during collection.
Optional DSPy test classes skip when the SDK is absent.

```bash
THALIA_LIVE_TESTS=1 \
  uv run --project . --extra dev python -m pytest \
  tests/test_dspy_runtime.py -k TestRealNeuralDspy
```

The adapter boundary is narrow on purpose. A frontier API, local inference server,
or evaluation wrapper only needs to implement `complete(prompt: str) -> str`.
Everything else — evidence selection, citation construction, memory gating,
configuration, and artifact generation — remains unchanged. This is what lets the
deterministic manuscript distinguish method validation from model performance.

## Optional Common Backend Benchmark {#sec:op-backend-benchmark}

`BenchmarkBackend(name, provider, model, lm, generation_options,
model_observation)` describes a real caller-supplied `LMClient` and public
metadata. `run_backend_benchmark(backends, per_category=..., seed=...,
limit=..., config=...)` supplies the same seeded, category-round-robin cohort
to every backend. It prepends extractive when absent, rejects `verify=True`,
and uses a fresh context-managed `AutoHarness` per example. One completion
attempt per row preserves an observable failure denominator.

```bash
# Baseline + explicitly selected local model; no DSPy prerequisite.
uv run --project . python scripts/run_backend_benchmark.py \
  --ollama-model gemma3:4b --per-category 2 --seed 0 \
  --output output/data/backend_local.json

# Optional paid/network path; process environment key required.
uv run --project . python scripts/run_backend_benchmark.py \
  --ollama-model gemma3:4b --openrouter-model tencent/hy3-preview \
  --allow-cloud --per-category 2 --seed 0 --timeout 120 --max-tokens 512 \
  --output output/data/backend_local_cloud.json
```

Both model flags are repeatable. Without them the CLI runs only extractive;
neither credentials nor `--allow-cloud` alone select cloud. `--limit` caps the
round-robin cohort; `--per-category` and `--seed` define it. The CLI uses default
`HarnessConfig`; custom configuration is a Python API input, not a CLI
`--config` option. Python OpenRouter selection also requires explicit
`allow_cloud=True`. Callers remain responsible for authorized behavior of custom
clients whose network use cannot be inferred from the protocol.

`validate_backend_benchmark(payload)` checks schema, planned identity, prompt
agreement, accounting, finite scores/times, recomputed token-F1 and summaries,
and report fingerprints. Honest incomplete evidence remains valid diagnostic
input. `write_backend_benchmark(payload, path)` atomically writes complete
reports to the requested destination and incomplete reports to an `.incomplete`
sidecar, preserving a previous complete file. The CLI prints the actual path and
returns nonzero for incomplete runs. A preserved older file is not a fresh success.

The separate artifact records each requested backend/example, null answer and
score on failure, error class only, model/options, dataset/config/content/prompt
identity, and runtime provenance. Summaries expose requested/completed/failed
counts and successful-only F1 and latency means/quantiles; null summaries mean
no successful rows, not zero performance. Failed backends are not complete paired
estimates. No retained empirical aggregate or publication claim is promoted.

`build_dashboard.py --backend-benchmark PATH` validates and displays this optional
artifact offline; otherwise it reads the default benchmark path only if present.
Missing/incomplete state is explicit. Timing is observed end-to-end harness
execution, not token throughput, price, or a production service-level guarantee.
Network, serving, cold-start, caching, hardware, and sequential order effects
remain uncontrolled. Matched identity permits finite descriptive comparison;
quality or cloud/local superiority requires a separate adjudicated design.
The detailed schema and short Claim-Evidence Audit are in
`docs/backend_benchmark.md`.


## Persistent Multi-Turn Sessions {#sec:op-session}

:class:`Session` wraps the harness with disk-backed state so a conversation
survives process restarts: episodes persist to a SQLite file, the consolidated
MEMORY.md is read at start and re-written on consolidation, and the running
transcript is reconstructed from stored episodes so the Inspector can retrieve
evidence from earlier turns. Reopening a session resumes turn IDs without
collision (via the harness `start_turn`). A worked restart — store a fact, close,
reopen in a fresh session, and retrieve the fact — is asserted in the test suite.

Session persistence also makes memory audit practical. The transcript can be
reconstructed from raw episodes, while MEMORY.md remains a derived convenience
layer. If a future answer depends on a remembered fact, the relevant raw turn can
still be recovered and cited.

## Query CLI and Configuration Resolution {#sec:op-cli}

`scripts/run_query.py` (logic in `src/cli.py`) runs a single query against the
harness:

```bash
uv run --project . --extra dev python scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
```

For real haystacks, the same CLI exposes the opt-in adaptive Inspector controls:

```bash
uv run --project . --extra dev python scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-file long_session.txt \
  --adaptive-windows --adaptive-window-ratio {{CONFIG_ADAPTIVE_RATIO}} \
  --json
```

Flags cover the configuration knobs (`--top-k`, `--max-windows`, `--max-evidence`,
`--rrf-k`, `--context-budget`), a `--config` file, inline `--session-history` or a
`--session-file`, and `--json` for machine-readable output. The result reports the
answer, detected task category, delivery mode, and the cited source indices —
making the harness's evidence-grounding inspectable from the shell.

## Optional SDK Cache Trust Boundary {#sec:op-cache-trust}

The optional DSPy stack retains an unresolved third-party pickle-cache
advisory. THALIA's SDK configurators disable persistent disk caching before
configuring a backend; in-memory caching remains available. This prevents
those helpers from replaying persisted SDK entries, not a patch to the
dependency or an authentication guarantee for existing cache files. Callers
that configure DSPy independently must disable persistent caching before
model calls and must not load untrusted/shared caches. The SDK-free query
and common-backend commands do not import DSPy or use its cache. The
[security policy](https://github.com/docxology/thalia/blob/v{{CURRENT_RELEASE_VERSION}}/SECURITY.md)
records the advisory and boundary; release validation is not security
certification.

## Extension Points and Replacement Lanes {#sec:op-extension-matrix}

The intended extension points are stable and narrow:

| Extension | Interface | What changes | What stays fixed |
|-----------|-----------|--------------|------------------|
| Real LM | `LMClient.complete` | answer synthesis quality | Inspector, Retriever, citations, Memory Gate |
| Learned embedder | `SemanticIndex.top_k` | semantic ranking behaviour | lexical lane, RRF, budgets, evaluation protocol |
| Persistent deployment | `Session` paths | storage location and lifecycle | append-only episodes, consolidation policy |
| Search policy | `HarnessConfig` / compiler candidates | retrieval depth and weights | stage interfaces, metrics, manuscript tokens |

This matrix is the operational version of the scope boundary. THALIA can be made
stronger by replacing model and embedding components. Those replacements are
experiments behind documented interfaces, and the deterministic method contract
remains fixed.
