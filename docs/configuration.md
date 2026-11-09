# Configuration

The tunable parameter vector is `HarnessConfig` (`src/config.py`). It is frozen,
hashable, validated on construction, and serialisable.

## Fields

| Field | Default | Meaning |
| --- | --- | --- |
| `max_windows` | 15 | Inspector cap on emitted windows |
| `top_k` | 8 | Retriever cap on ranked evidence |
| `rrf_k` | 60 | RRF damping constant |
| `lexical_weight` / `semantic_weight` | null/null | Lane weights (both-or-neither; null → per-category defaults) |
| `context_budget_tokens` | 2048 | Inline-delivery token budget |
| `max_evidence` | 5 | Reasoner cap on evidence considered |
| `rerank` | `rrf` | Re-ranking strategy: `rrf` or `mmr` |
| `mmr_lambda` | 0.7 | MMR relevance/diversity tradeoff [0,1] |
| `verify` | false | Reasoner grounding-verification pass |
| `grounding_threshold` | 0.3 | Min answer-in-evidence support before re-answering |
| `partition_threshold` | 40 | Inspector record count above which recursion runs |
| `partition_size` | 10 | Block size for recursive partitioning |
| `query_expansion` | false | Pseudo-relevance-feedback query expansion |
| `expansion_terms` | 5 | Feedback terms appended when expanding |
| `recency_weight` | 0.0 | Recency bonus in [0,1] favouring later turns |
| `recall_memory` | false | Consult episodic store + MEMORY.md for evidence |
| `recall_limit` | 3 | Maximum recalled evidence windows |
| `adaptive_windows` | false | Scale the Inspector window budget with context size (no-op on compact contexts) |
| `adaptive_window_ratio` | 5 | When adaptive: keep ~one window per this many session lines |

## Query configuration sources and precedence

Lowest to highest: **built-in defaults → YAML file → `THALIA_*` environment →
explicit CLI flags**.

- **File:** `load_config(path)` reads `config/harness.yaml` (flat, or under a
  `harness:` key). `save_config(config, path)` writes YAML.
- **Environment:** every field maps to `THALIA_<FIELD>` (e.g. `THALIA_TOP_K=4`,
  `THALIA_RERANK=mmr`, `THALIA_VERIFY=true`). Booleans accept `1/true/yes/on` and
  `0/false/no/off`. Lane weights stay both-or-neither.
- **CLI:** `--top-k`, `--max-windows`, `--max-evidence`, `--rrf-k`,
  `--context-budget`, `--rerank`, `--mmr-lambda`, `--verify`, `--query-expansion`,
  `--recency-weight`, `--recall-memory`, `--adaptive-windows`,
  `--adaptive-window-ratio`, plus `--config`.

The four boolean flags also accept `--no-verify`, `--no-query-expansion`,
`--no-recall-memory`, and `--no-adaptive-windows`. Either spelling is an explicit
highest-precedence choice; omitting a flag preserves the file/environment value.
For example, `THALIA_VERIFY=true thalia --query "..." --no-verify` disables the
optional second completion for that invocation without changing saved settings.

## Programmatic

```python
from src.config import load_config, default_config
cfg = load_config("config/harness.yaml").with_(top_k=4, rerank="mmr")
cfg2 = default_config().with_(verify=True, grounding_threshold=0.5)
```

`with_(**changes)` returns a validated copy; `to_dict`/`from_dict` round-trip a
config (unknown keys ignored).

### YAML serialisation

`HarnessConfig` carries its own `to_yaml()` and `from_yaml(text)` methods so the
serialisation logic lives on the dataclass rather than scattered across helpers:

```python
# Serialise
yaml_str = cfg.to_yaml()                    # returns a YAML string
save_config(cfg, "config/harness.yaml")     # delegates to cfg.to_yaml()

# Deserialise
cfg3 = HarnessConfig.from_yaml(yaml_str)    # flat or under a `harness:` top-level key
cfg4 = load_config("config/harness.yaml")   # delegates to HarnessConfig.from_yaml()
```

`save_config` is a thin wrapper that ensures the parent directory exists and writes
the output of `to_yaml()` — it does not contain its own serialisation logic.

## Provider selection is separate

Harness-field precedence does not select a provider. Direct `LMClient` adapters
are supplied as `AutoHarness(config=cfg, lm=...)`:

```python
from src.harness import AutoHarness
from src.llm import OllamaLM, OpenRouterLM

with AutoHarness(config=cfg, lm=OllamaLM(model="gemma3:4b")) as harness:
    result = harness.forward(query="...", session_history="...")
# Explicit cloud alternative:
# OpenRouterLM(model="tencent/hy3-preview")
```

`OpenRouterLM` reads `THALIA_OPENROUTER_API_KEY` from the process environment
unless `api_key=` is supplied. There is no `THALIA_OPENROUTER_MODEL` selection
contract; use `model=` or the common benchmark's `--openrouter-model`.
Do not place keys in generation options or committed configuration.
`configure_openrouter(model=..., api_key=...)` is a separate optional **global
DSPy** configuration function, not an `AutoHarness` adapter.

The [common benchmark](backend_benchmark.md) documents its independent CLI
backend/model, generation, configuration, and output controls. A key alone never
opts its CLI into cloud calls. Live latency and generations lie outside the
deterministic-core guarantee.

## Benchmark configuration is explicit

`thalia-benchmark --config PATH` loads base `HarnessConfig` YAML with
`apply_env=False`; unlike the query CLI, `THALIA_*` harness overrides are not
applied. An omitted file uses built-in defaults. A selected harness-derived method
rejects `verify=True` before inference to preserve one completion attempt per cell.
Full-context-only selection has no harness configuration and ignores that unused
base setting.

Repeat `--method` to select `harness`, `full_context`, `lexical_only`, or
`adaptive` (default `harness`). The base config applies to harness arms;
lexical-only sets scoring weights to 1/0 and adaptive enables adaptive windows.
Full context has no harness config and submits all history through the same
typed renderer/query. It is not guaranteed provider retention.

Zero-weight scoring lanes do not run or contribute fusion membership/ranks.
Explicit PRF query expansion remains independent BM25 work, and explicit MMR
may use semantic representations. A zero semantic scoring weight therefore does
not promise zero semantic computation for every possible base configuration.

Repeat `--seed` for cohort seeds (default 0); these are not model RNG seeds.
`--n-boot`, `--analysis-seed`, and `--reference-method` control descriptive paired
analysis, defaulting to 2000, 0, and `full_context`. If that reference is not
selected, comparisons are not requested. Optional positive `--num-ctx` requests
Ollama context only; it is not forwarded to cloud or a retention guarantee.
`--max-tokens` and `--timeout` remain request controls, not whole-run guarantees.
`--plan` resolves the same cohort, methods, backend identities and execution
schedule offline, prints planned JSON, and exits without model observation or
completion calls and without writing the requested report destination.

Python callers use `build_benchmark_methods(names, config=base)` followed by
`run_backend_benchmark(..., methods=methods, seeds=(...))`. Removed singular
`seed` and run-level `config` arguments have no compatibility shim. Schema 1 is
rejected; preserve old evidence and choose a new schema-2 destination. See
[`backend_benchmark.md`](backend_benchmark.md) for accounting and interpretation.
