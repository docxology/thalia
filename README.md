# ATLAS — Agentic Typed-pipeline with Lexical And Structured stages

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

## Quick start

```bash
# From the repository root.
uv run --project working/atlas python working/atlas/scripts/00_preflight.py
uv run --project working/atlas pytest working/atlas/tests/ \
  --cov=working/atlas/src --cov-fail-under=90

# Regenerate evaluation artifacts and figures.
uv run --project working/atlas python working/atlas/scripts/run_harness_eval.py
uv run --project working/atlas python working/atlas/scripts/run_compiler.py
uv run --project working/atlas python working/atlas/scripts/generate_figures.py
uv run --project working/atlas python working/atlas/scripts/build_dashboard.py
uv run --project working/atlas python working/atlas/scripts/z_generate_manuscript_variables.py
uv run --project working/atlas python working/atlas/scripts/run_demo.py
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

## Operate it

```bash
# One-shot query from the shell (text or --json); flags/env/file all configure it.
uv run --project working/atlas python working/atlas/scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
ATLAS_TOP_K=4 uv run --project working/atlas python working/atlas/scripts/run_query.py --query "..." --config working/atlas/config/harness.yaml
uv run --project working/atlas python working/atlas/scripts/run_query.py --query "..." --adaptive-windows --adaptive-window-ratio 5
```

```python
# Run these snippets from the atlas dir (`cd working/atlas`) so `src` is importable.
# Configure: file < env (ATLAS_*) < explicit override
from src.config import load_config, default_config
config = load_config("working/atlas/config/harness.yaml").with_(top_k=4)

# Real LM: wrap any callable, or call a local Ollama server (stdlib only)
from src.llm import CallableLM, OllamaLM
from src.harness import AutoHarness
AutoHarness(config=config, lm=CallableLM(lambda prompt: my_model(prompt)))
# AutoHarness(lm=OllamaLM(model="gemma3:4b"))  # opt-in; raises on failure, never silent

# Persistent multi-turn session (survives process restart)
from src.session import Session
s = Session(db_path="episodes.db", memory_path="MEMORY.md")
s.ask("My wifi password is bluefish42")
print(s.ask("What is the wifi password?").answer)  # retrieves the earlier turn
s.close()
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
not a stand-in: `to_dspy_signature` builds a genuine `dspy.Signature` from any ATLAS
signature, and [`src/dspy_runtime.py`](src/dspy_runtime.py) runs a real `dspy.Predict`
program and a real `dspy.BootstrapFewShot` optimizer — both backed by the project's
real deterministic `ExtractiveLM`, so the whole path is offline, reproducible, and
mock-free. The deterministic core and headline results are unchanged.

```bash
uv pip install --python working/atlas/.venv/bin/python "dspy-ai>=2.5"
uv run --project working/atlas python working/atlas/scripts/run_dspy.py
```

**Real neural LLM (optional).** Point dspy at a live local model and the same path
runs against real generations — no surrogate. With [Ollama](https://ollama.com)
serving a small Gemma, `configure_ollama()` wires `dspy.LM` → litellm → Ollama, and
`run_dspy.py` records its answer (`neural_prediction`) alongside the deterministic one:

```bash
ollama pull gemma3:4b
uv run --project working/atlas python working/atlas/scripts/run_dspy.py   # adds a real gemma3:4b answer
```

The in-house `MIPRO`/`GEPA` compilers remain the project's own deterministic engine
(honestly labelled "-style"), distinct from this real-dspy path.

## Layout

- `src/` — the harness (signatures, stages, retrieval, memory, compiler) + operability (config, llm, session, cli, evaluation, figures)
- `config/harness.yaml` — canonical loadable configuration (overridable via `ATLAS_*` env / CLI flags)
- `tests/` — Zero-Mock suite, one file per module; ≥ 90% `src/` coverage gate
- `scripts/` — thin orchestrators (preflight, eval, compile, figures, dashboard, demo, manuscript tokens)
- `skills/` — `SKILL.md` per stage (machine-readable capability descriptors)
- `manuscript/` — the full write-up (sections 00–99) with generated `{{…}}` tokens
- `domain_profile.yaml` · `experiment_plan.yaml` · `data/claim_ledger.yaml` — advisory overlays

See [`AGENTS.md`](AGENTS.md) for the agent-facing technical reference.
