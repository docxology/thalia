# Operability and Configuration {#sec:operability}

THALIA is not only a design — it is operable. This section documents the
configuration system, the real language-model adapters, the persistent multi-turn
session, and the command-line interface. Each has dedicated Zero-Mock coverage in
the strict local suite, including a real in-process HTTP server for the network
adapter; this is a tested-path statement, not an assertion that every deployment
integration has been exercised.

## Configuration {#sec:op-config}

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
  Two additional environment variables control the OpenRouter adapter:
  `THALIA_OPENROUTER_API_KEY` (required to activate the adapter; absent → null
  rows in evaluation output) and `THALIA_OPENROUTER_MODEL` (selects the
  OpenRouter model; the current recorded aggregate uses `{{RESULT_OPENROUTER_MODEL}}`).
- **Round-trip** — `to_dict` / `from_dict`, `to_yaml` / `from_yaml`, and
  `save_config` make a config serialisable and reproducible; `from_dict` and
  `from_yaml` ignore unrecognised keys. `to_yaml` is the single serialisation
  path — `save_config` delegates to it, so the YAML representation never drifts
  from the dataclass.

Precedence, lowest to highest: built-in defaults → file → environment → explicit
CLI flags.

This precedence order is part of the reproducibility story. A manuscript render
can point to the checked-in `config/harness.yaml`; a local experiment can override
one field through `THALIA_*`; and a CLI run can still make an explicit one-off
choice without mutating source files. The resulting configuration is serialisable,
so a compiled or manually selected setting can be saved and compared later.

## Composable Pipeline {#sec:op-pipeline}

`AutoHarness` bundles the {{CONFIG_NUM_RUNTIME_STAGES}} runtime stages into one `forward` call. For
callers that need to inspect or modify the stage chain — insert a logging hook,
a custom reranker, or run a partial pipeline — `src/pipeline.py::Pipeline`
exposes the same stages as an explicit, chainable sequence:

```python
from src.pipeline import Pipeline

pipe = (
    Pipeline(config)
    .with_inspector()
    .add_step("log", lambda ctx: (ctx.extras.update({"n": len(ctx.evidence_windows)}), ctx)[1])
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
After `run`, `pipe.intermediates` holds a `(step_name, context)` snapshot after
every step, so intermediate evidence counts, scores, and traces are inspectable
without re-running the pipeline. `scripts/run_pipeline.py` exercises this path
end-to-end and writes the intermediate-step trace to `output/data/`.

## Resource safety {#sec:op-resource-safety}

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
is exercised by the default analysis pipeline, not only by tests.

`AutoHarness` and `Pipeline` expose the same context-manager contract. They close
only stores they created internally; a store supplied by the caller remains the
caller’s responsibility. `EpisodicStore.close()` is idempotent, so cleanup is
safe in both nested context managers and explicit `finally` blocks. The strict
suite runs with `ResourceWarning` promoted to an error to make a leaked SQLite
connection a failing contract rather than a diagnostic afterthought.

The standalone preflight reports independent readiness states for the
deterministic core, DSPy SDK, Ollama server, Gemma model, embedding model,
LongMemEval payload, and template renderer. Optional neural/benchmark states do
not block deterministic operation; the fail-closed artifact validator remains the
local release boundary.

## Package metadata {#sec:op-metadata}

The package exports `__version__` at the top level (`from src import __version__`)
and ships a `py.typed` marker (PEP 561) so downstream type checkers see the full
type annotations. `HarnessOutput.to_dict()` provides JSON serialisation on the
dataclass itself — the CLI delegates to it, so the field mapping has one source
of truth.

## Language-model adapters {#sec:op-lm}

The deterministic core uses the extractive responder, but a real model plugs in
behind the one-method `LMClient` protocol:

- **`CallableLM(fn)`** — wrap any `Callable[[str], str]` (an SDK call, a local
  function). The smallest possible real adapter.
- **`OllamaLM(model, host)`** — call a local Ollama server's `/api/generate`
  endpoint using only the standard library (no third-party dependency). Failures
  raise `OllamaError` rather than degrading into an empty answer, and
  `is_available()` offers a best-effort liveness probe. It is opt-in and never
  invoked by the default core.
- **`configure_openrouter(model, api_key)`** — configure the harness to use an
  OpenRouter-hosted model via the OpenRouter chat completions API. The model is
 controlled by the `THALIA_OPENROUTER_MODEL` environment variable; the API key is
 read from `THALIA_OPENROUTER_API_KEY`. The current recorded aggregate uses
 `{{RESULT_OPENROUTER_MODEL}}`.
  Like `OllamaLM`, this adapter is opt-in and raises on failure rather than
  silently degrading.

Both are validated against a real HTTP server spun up in the test process — the
adapter's request construction and response parsing are exercised for real, with
no mocks.

The adapter boundary is narrow on purpose. A frontier API, local inference server,
or evaluation wrapper only needs to implement `complete(prompt: str) -> str`.
Everything else — evidence selection, citation construction, memory gating,
configuration, and artifact generation — remains unchanged. This is what lets the
deterministic manuscript distinguish method validation from model performance.

## Persistent multi-turn session {#sec:op-session}

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

## Command-line interface {#sec:op-cli}

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
  --adaptive-windows --adaptive-window-ratio {{CONFIG_ADAPTIVE_RATIO}} --json
```

Flags cover the configuration knobs (`--top-k`, `--max-windows`, `--max-evidence`,
`--rrf-k`, `--context-budget`), a `--config` file, inline `--session-history` or a
`--session-file`, and `--json` for machine-readable output. The result reports the
answer, detected task category, delivery mode, and the cited source indices —
making the harness's evidence-grounding inspectable from the shell.

## Extension matrix {#sec:op-extension-matrix}

The intended extension points are stable and narrow:

| Extension | Interface | What changes | What stays fixed |
|-----------|-----------|--------------|------------------|
| Real LM | `LMClient.complete` | answer synthesis quality | Inspector, Retriever, citations, Memory Gate |
| Learned embedder | `SemanticIndex.top_k` | semantic ranking behaviour | lexical lane, RRF, budgets, evaluation protocol |
| Persistent deployment | `Session` paths | storage location and lifecycle | append-only episodes, consolidation policy |
| Search policy | `HarnessConfig` / compiler candidates | retrieval depth and weights | stage interfaces, metrics, manuscript tokens |

This matrix is the operational version of the scope boundary. THALIA can be made
stronger by replacing model and embedding components, but those replacements are
experiments behind documented interfaces, not reasons to weaken the deterministic
method contract.
