# Operability and Configuration {#sec:operability}

ATLAS is not only a design — it is operable. This section documents the
configuration system, the real language-model adapters, the persistent multi-turn
session, and the command-line interface. Each is fully tested (Zero-Mock,
including a real in-process HTTP server for the network adapter).

## Configuration {#sec:op-config}

The tunable parameter vector is :class:`HarnessConfig` ([@sec:stage-compiler]). It
is loadable, overridable, and serialisable:

- **File** — `load_config(path)` reads a harness YAML file
  (`config/harness.yaml` ships as the canonical default). The YAML may list fields
  flat or under a `harness:` key; manuscript `config.yaml` keeps renderer metadata
  separate and mirrors selected values only under `project_config.harness`.
- **Environment** — any field is overridable via `ATLAS_<FIELD>` (e.g.
  `ATLAS_TOP_K=4`, `ATLAS_LEXICAL_WEIGHT=0.8 ATLAS_SEMANTIC_WEIGHT=0.2`). Lane
  weights remain both-or-neither; setting only one against an unset pair raises.
- **Round-trip** — `to_dict` / `from_dict` and `save_config` make a config
  serialisable and reproducible; `from_dict` ignores unrecognised keys.

Precedence, lowest to highest: built-in defaults → file → environment → explicit
CLI flags.

This precedence order is part of the reproducibility story. A manuscript render
can point to the checked-in `config/harness.yaml`; a local experiment can override
one field through `ATLAS_*`; and a CLI run can still make an explicit one-off
choice without mutating source files. The resulting configuration is serialisable,
so a compiled or manually selected setting can be saved and compared later.

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
uv run --project working/atlas python working/atlas/scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
```

For real haystacks, the same CLI exposes the opt-in adaptive Inspector controls:

```bash
uv run --project working/atlas python working/atlas/scripts/run_query.py \
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

This matrix is the operational version of the scope boundary. ATLAS can be made
stronger by replacing model and embedding components, but those replacements are
experiments behind documented interfaces, not reasons to weaken the deterministic
method contract.
