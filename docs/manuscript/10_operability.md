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

Query precedence, lowest to highest: built-in defaults → file → environment →
explicit CLI flags. The benchmark deliberately loads base `--config` without
environment overrides to keep the method configuration explicit.

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

## Optional Backend and Method Benchmark {#sec:op-backend-benchmark}

`BenchmarkBackend(name, provider, model, lm, generation_options,
model_observation)` describes a real caller-supplied `LMClient` and public
metadata. Frozen `BenchmarkMethod(name, kind, config)` separates context selection
from backend identity. `build_benchmark_methods(names, config=base)` selects
`harness`, `full_context`, `lexical_only`, or `adaptive`; custom named harness
configs are allowed. Harness kinds require validated `verify=False` configs,
while full context requires no harness config.

`run_backend_benchmark(backends, methods=..., seeds=..., per_category=...,
limit=..., reference_method=..., n_boot=..., analysis_seed=...)` replaces the old
singular `seed` and run-level `config` interface without compatibility aliases.
Each seed's research cohort is built independently, preserving category/stratum
and stable identity. Deterministic category/seed interleaving precedes the global
limit. The runner prepends extractive when absent, executes backend-outer with
rotated method order, and records the schedule and contiguous execution indices.

Full context directly submits every history line to the real selected LM using
the same typed `ReasonerSignature` renderer/query as harness arms. It bypasses
Inspector/Retriever, not the provider boundary. Harness arms use fresh
context-managed `AutoHarness` state per cell. Thus selected context changes,
while full submission is not a provider context-retention guarantee. Each cell
has one attempt, with no retries, warm-up, benchmark cache or verification
re-answer.

```bash
# Installed command; no checkout-relative path or DSPy prerequisite.
thalia-benchmark --ollama-model gemma3:1b \
  --method full_context --method harness --method lexical_only \
  --method adaptive --seed 0 --seed 1 --seed 2 \
  --per-category 2 --num-ctx 8192 --timeout 120 --max-tokens 1024 \
  --n-boot 2000 --analysis-seed 0 --reference-method full_context \
  --output output/data/backend_local.json

# Source consumer selection is explicit and offline.
uv run --project . --extra dev python scripts/build_dashboard.py \
  --backend-benchmark output/data/backend_local.json
uv run --project . --extra dev python \
  scripts/z_generate_manuscript_variables.py \
  --benchmark-report output/data/backend_local.json
```

Model, method and seed flags are repeatable; defaults select extractive with
`harness` and the default cohort seed. Optional `--config PATH` loads base YAML
without harness environment overrides. `--num-ctx` requests Ollama context only,
not a measured retention limit. `--n-boot`, `--analysis-seed` and
`--reference-method` control descriptive paired analysis; they do not set model
generation randomness. Cloud requires explicit `--openrouter-model` and
`--allow-cloud`, plus an authorized process-environment key; neither a key nor
consent alone selects cloud. Python selection likewise requires `allow_cloud=True`.
Callers remain responsible for authorized behavior of custom clients.

Schema two separates backend metadata, method configs/fingerprints, example
identities, rows, cell summaries, category/stratum groups and within-backend
paired contrasts. Portable producer-source inventory and observed runtime/
dependency/model metadata bind source scope, not authenticity. Schema one is
rejected rather than silently upgraded; preserve old release artifacts.
The validator rebuilds the seeded plan and recomputes accounting, prompt
agreement, token-F1, summaries/groups and paired statistics. Failed rows retain
null answer/score and safe exception class only, never raw provider errors.

Comparisons estimate the unweighted mean of per-seed mean paired F1 deltas.
Any missing planned pair suppresses both mean delta and interval. A complete
single-seed contrast has no interval; multi-seed clustered intervals retain the
small-cluster warning. If the reference method is not selected, comparisons are
not requested. These are descriptive finite contrasts, not significance, power,
model ranking or promotion.

Complete reports are atomically written to the requested caller-relative path;
incomplete reports go to a sidecar, preserving the last good file. The CLI prints
the actual path and returns nonzero on incomplete runs. Select that sidecar
explicitly in both consumers rather than mistaking an old complete file for a
fresh success. Manuscript observation and contrast tables use generated tokens;
missing evidence is labelled not recorded, not fabricated.

Prompt characters are not billed tokens. Latency is observed end-to-end cell
execution, including method/client work and cleanup, not throughput, price or a
service-level guarantee. Host load, cold starts, serving caches and runtime
versions remain uncontrolled. `docs/backend_benchmark.md` records migration and
the Claim-Evidence Audit; `docs/local_method_study.md` declares a local plan, not
measured outcomes. Historical DSPy/cloud cohorts remain separate, and no expert
quality or production certificate is implied.


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
