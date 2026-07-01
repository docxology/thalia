# THALIA — Agentic Typed-pipeline with Lexical And Structured stages

A typed agentic harness that fuses DSPy's compiler-driven optimization
with the Hermes Agent layered-memory and trace-evolution ecosystem, built inside
the [`docxology/template`](https://github.com/docxology/template) reproducible-
research substrate. Prompts are parameterized code (typed signatures); context is
inspectable external state (RLM-style Inspector); memory is episodic-first evidence
(gated consolidation); retrieval is a lexical-anchored hybrid (BM25/grep +
hashing-embedding + weighted RRF); and the pipeline records bounded optimization
traces through structured search (MIPRO-style) and trace-reflective evolution
(GEPA-style).

> **Status:** in-progress, local-only research project (`projects/working/`),
> rendered only when explicitly requested through the template pipeline. Runnable
> and fully tested in isolation; generated outputs are gitignored.

## What THALIA is

THALIA is five composable stages that turn an unstructured LLM agent into a
declarative, inspectable, evidence-grounded, compiler-optimizable pipeline:

1. **Inspector** (Stage 0) — Loads session history as external state into a REPL
   environment, greps for query-anchored evidence, and emits compact evidence
   windows with auditable metadata. The full context is never forwarded to a
   neural call. *Foundation: Recursive Language Models.*

2. **Retriever** (Stage 1) — Ranks evidence through a lexical-first hybrid: a
   BM25/grep lane for precise literal matches, a hashing-embedding semantic lane
   for paraphrase coverage, and weighted Reciprocal Rank Fusion to merge them.
   Sparse context budgeting picks inline or file-based delivery.
   *Foundation: Is Grep All You Need?*

3. **Reasoner** (Stage 2) — Produces a grounded, typed answer from ranked
   evidence. Routes multi-hop/code/knowledge-update tasks through a
   ReAct-style read-integrate loop, everything else through chain-of-thought.
   The only language-model boundary sits behind a one-method `LMClient` protocol.
   *Foundation: DSPy.*

4. **Memory Gate** (Stage 3) — Always appends the raw episode to an append-only
   SQLite store; only conditionally consolidates into a derived MEMORY.md
   snapshot when both the Reasoner requests it AND an explicit criterion holds.
   Raw episodes are never overwritten. *Foundation: Memory consolidation faults.*

5. **Compiler** (Stage 4, offline) — Treats the harness itself as an optimizable
   program: MIPRO-style exhaustive config search + GEPA-style trace-reflective
   evolution. Records the full search trace, not just the winner.
   *Foundation: DSPy + Hermes self-evolution.*

## What THALIA proves

THALIA is not a benchmark entry — it is a **methodological argument**: that an
agentic harness should be declarative (typed stages, not prompt strings),
inspectable (context is external state you can grep), evidence-grounded (raw
episodes are first-class and never overwritten), lexically anchored (precise
literal retrieval first, semantic coverage second), and compiler-optimized (the
pipeline is searched against a metric, not tweaked by hand).

The evaluation makes two honest scope boundaries explicit:
- The extractive LM bounds token-F1 accuracy (a real neural model raises it,
  concentrated on the hardest categories).
- The semantic lane is a sub-word hashing surrogate, not a learned dense retriever
  (so the lexical-vs-dense *magnitude* of the agentic-search study is not
  reproduced locally — only the *direction* is).

Real measurements on real data include: a held-out before/after optimizer lift,
context-poisoning resistance with citation auditability, a real LongMemEval_S
benchmark run with bootstrap CIs, and a bottleneck localisation showing the
Inspector's context-narrowing — not retrieval ranking — is the recall bottleneck
on long-context haystacks, fixable via the adaptive Inspector.

## Quick start

```bash
# From the repository root.
uv run --project working/thalia python working/thalia/scripts/00_preflight.py
uv run --project working/thalia pytest working/thalia/tests/ \
  --cov=working/thalia/src --cov-fail-under=90

# Regenerate evaluation artifacts and figures.
uv run --project working/thalia python working/thalia/scripts/run_harness_eval.py
uv run --project working/thalia python working/thalia/scripts/run_compiler.py
uv run --project working/thalia python working/thalia/scripts/run_pipeline.py
uv run --project working/thalia python working/thalia/scripts/generate_figures.py
uv run --project working/thalia python working/thalia/scripts/build_dashboard.py
uv run --project working/thalia python working/thalia/scripts/z_generate_manuscript_variables.py
uv run --project working/thalia python working/thalia/scripts/run_demo.py
```

## The five stages

| Stage | Role | Module | Foundation |
|-------|------|--------|------------|
| 0 Inspector | RLM-style context narrowing | `src/stages/inspector.py` | Recursive Language Models |
| 1 Retriever | Lexical-first hybrid + RRF | `src/stages/retriever.py` | Is Grep All You Need? |
| 2 Reasoner | Typed declarative reasoning | `src/stages/reasoner.py` | DSPy |
| 3 Memory Gate | Episodic-first, gated consolidation | `src/stages/memory_gate.py` | Memory consolidation faults |
| 4 Compiler | MIPRO search + GEPA evolution | `src/compiler/` | DSPy + Hermes self-evolution |

## Design in one example

```python
from src.harness import AutoHarness

harness = AutoHarness()
out = harness.forward(
    query="What is the wifi password?",
    session_history="User: my wifi password is bluefish42\nAssistant: noted",
)
print(out.answer, out.task_category.value, out.delivery_mode.value)
print([c.source_index for c in out.evidence_citations])
```

## Composable Pipeline

For custom stage wiring, insert hooks, or run partial pipelines:

```python
from src.pipeline import Pipeline

pipe = (
    Pipeline()
    .with_inspector()
    .add_step("log", lambda ctx: (ctx.extras.update({"n": len(ctx.evidence_windows)}), ctx)[1])
    .with_retriever()
    .with_reasoner()
    .with_memory_gate()
)
out = pipe.run(query="What is the wifi password?", session_history="User: my wifi password is bluefish42")
# Inspect intermediate state after each step
for step_name, ctx in pipe.intermediates:
    print(step_name, ctx.extras)
```

## Operate it

```bash
# One-shot query from the shell (text or --json); flags/env/file all configure it.
uv run --project working/thalia python working/thalia/scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
THALIA_TOP_K=4 uv run --project working/thalia python working/thalia/scripts/run_query.py --query "..." --config working/thalia/config/harness.yaml
uv run --project working/thalia python working/thalia/scripts/run_query.py --query "..." --adaptive-windows --adaptive-window-ratio 5
```

```python
# Run these snippets from the thalia dir (`cd working/thalia`) so `src` is importable.
# Configure: file < env (THALIA_*) < explicit override
from src.config import load_config, default_config
config = load_config("working/thalia/config/harness.yaml").with_(top_k=4)

# Real LM: wrap any callable, or call a local Ollama server (stdlib only)
from src.llm import CallableLM, OllamaLM
from src.harness import AutoHarness
AutoHarness(config=config, lm=CallableLM(lambda prompt: my_model(prompt)))
# AutoHarness(lm=OllamaLM(model="gemma3:4b"))  # opt-in; raises on failure, never silent

# Persistent multi-turn session (survives process restart; context-manager safe)
from src.session import Session
with Session(db_path="episodes.db", memory_path="MEMORY.md") as s:
    s.ask("My wifi password is bluefish42")
    print(s.ask("What is the wifi password?").answer)  # retrieves the earlier turn
    print(s.turn_count)  # 2
# episodic store closed + MEMORY.md flushed automatically
```

## Deterministic by construction

Every mechanism is pure deterministic Python (no unseeded randomness, no
wall-clock, no network). The only judgment step — the Reasoner — sits behind a
one-method `LMClient` protocol whose default is a deterministic extractive
responder. A real LLM, a learned embedder, or real DSPy/GEPA each drop in behind
their respective interface without touching any other stage.

**Two honest scope boundaries** (see [`manuscript/07_evaluation.md`](manuscript/07_evaluation.md)):
the extractive LM bounds token-F1 accuracy, and the semantic lane is a hashing
sub-word surrogate rather than a learned dense retriever — so the lexical-vs-dense
*magnitude* of the agentic-search study is intentionally not reproduced locally.

## Real DSPy (no mock/stub)

Install the optional `dspy` extra and the DSPy integration becomes the real thing,
not a stand-in: `to_dspy_signature` builds a genuine `dspy.Signature` from any THALIA
signature, and [`src/dspy_runtime.py`](src/dspy_runtime.py) runs a real `dspy.Predict`
program and a real `dspy.BootstrapFewShot` optimizer — both backed by the project's
real deterministic `ExtractiveLM`, so the whole path is offline, reproducible, and
mock-free. The deterministic core and headline results are unchanged.

```bash
uv pip install --python working/thalia/.venv/bin/python "dspy-ai>=2.5"
uv run --project working/thalia python working/thalia/scripts/run_dspy.py
```

**Real neural LLM (optional).** Point dspy at a live local model and the same path
runs against real generations — no surrogate. With [Ollama](https://ollama.com)
serving a small Gemma, `configure_ollama()` wires `dspy.LM` → litellm → Ollama, and
`run_dspy.py` records its answer (`neural_prediction`) alongside the deterministic one:

```bash
ollama pull gemma3:4b
uv run --project working/thalia python working/thalia/scripts/run_dspy.py   # adds a real gemma3:4b answer
```

The in-house `MIPRO`/`GEPA` compilers remain the project's own deterministic engine
(honestly labelled "-style"), distinct from this real-dspy path.

## Composability and resource safety

- **Composable Pipeline** (`src/pipeline.py`) — chain stages explicitly, insert
  custom steps, inspect intermediates, or run partial pipelines.
- **Context managers** — `Session` and `EpisodicStore` both support `with` blocks
  so resources are always cleaned up, even on exceptions.
- **Serialisation** — `HarnessOutput.to_dict()`, `HarnessConfig.to_yaml()`/`from_yaml()`
  provide round-trip serialisation from the dataclasses themselves.
- **Type safety** — `py.typed` marker (PEP 561) + `__version__` exported at the
  top level.
- **Every public method is runtime-called** — a reachability trace confirms zero
  test-only or dead-code symbols in `src/`.

## Validation

- **571 tests pass** (586 collected; 15 are optional DSPy/Ollama-gated skips that
  pass once those extras are installed), **98.1% coverage** on `src/` (gate: 90%).
- **Zero-Mock policy** — no `unittest.mock`, `MagicMock`, or `mocker.patch`.
  HTTP tests use a real in-process server; file tests use real temp files.
- **13 executable invariants** — BM25 idf non-negativity, RRF monotonicity, MMR
  lambda=1 reducing to relevance, episode append-only, consolidation gate strictness,
  harness determinism, answer grounding, query-expansion superset, recall read-only,
  recency-zero noop, static determinism guard, and more.
- **19 manuscript figures** — all generated deterministically from `src/evaluation`,
  including three new visualizations: per-category component breakdown, pipeline
  evidence-flow, and GEPA component trajectory.
- **85 manuscript `{{TOKEN}}` variables** referenced across the sections — all
  generated from live code, zero missing.

## Layout

- `src/` — the harness (signatures, stages, retrieval, memory, compiler) + operability (config, llm, session, cli, pipeline, evaluation, figures)
- `config/harness.yaml` — canonical loadable configuration (overridable via `THALIA_*` env / CLI flags)
- `tests/` — Zero-Mock suite, one file per module; ≥ 90% `src/` coverage gate
- `scripts/` — thin orchestrators (preflight, eval, compile, pipeline, figures, dashboard, demo, manuscript tokens)
- `skills/` — `SKILL.md` per stage (machine-readable capability descriptors)
- `manuscript/` — the full write-up (sections 00–99) with generated `{{…}}` tokens
- `domain_profile.yaml` · `experiment_plan.yaml` · `data/claim_ledger.yaml` — advisory overlays

See [`AGENTS.md`](AGENTS.md) for the agent-facing technical reference.
