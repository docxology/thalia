# THALIA — Agent Reference

Agent-facing technical reference for the THALIA auto-harness. This is an
in-progress, local-only research project under `projects/working/`; it is not
discovered or rendered by the template pipeline by default. Project source is
tracked in this private sidecar; generated `output/` artifacts are gitignored and
must not be committed to the public template checkout.

## What THALIA is

A DSPy + Hermes auto-harness: five composable stages (Inspector, Retriever,
Reasoner, Memory Gate, Compiler), each a typed `Signature` backed by a `SKILL.md`,
with a deterministic offline core. See [`README.md`](README.md) for the overview
and [`manuscript/`](manuscript/) for the full design rationale.

## Architecture invariants (do not break)

1. **Business logic lives in `src/`.** Scripts are thin orchestrators: they handle
   I/O and call `src/` functions. Never implement algorithms in `scripts/`.
2. **The LM is behind a protocol.** The only model-calling code in the
   deterministic core is the Reasoner via `src.module.LMClient`. The default
   `ExtractiveLM` is deterministic. Do not import an LLM SDK in the core. The
   optional, gated DSPy seams (`src/compiler/gepa.py`, `src/dspy_runtime/`) may
   import `dspy`, but the core never imports them and never depends on `dspy`.
3. **Raw episodes are never overwritten.** `EpisodicStore` is append-only.
   Consolidation produces a *derived* MEMORY.md delta only, and only when both the
   Reasoner flag and an explicit criterion hold.
4. **Determinism.** No unseeded RNG, no wall-clock branching, no network. Identical
   inputs must reproduce identical outputs (asserted in tests).
5. **Zero-Mock tests.** No `unittest.mock` / `MagicMock`. Use real data, real
   SQLite, real temp files. Selecting a real fallback path (e.g. toggling
   `fts_available`) is allowed; faking call boundaries is not.
6. **Coverage gate.** `src/` ≥ 90% (`pyproject.toml`). Run the suite before changes.

## Module map

| Path | Responsibility |
|------|----------------|
| `src/signatures/` | Signature framework (`framework.py`), payloads (`payloads.py`), stage contracts (`stages.py`) |
| `src/manuscript_integrity.py` | Manuscript `{{TOKEN}}` coverage + crossref validation |
| `src/module.py` | `Module`, `Predict`, `Prediction`, `LMClient`, `ExtractiveLM`, prompt rendering, `tokenize` |
| `src/config.py` | `HarnessConfig` + `load_config`/`save_config`/`apply_env_overrides` + `to_yaml`/`from_yaml` |
| `src/llm.py` | Real LM adapters: `CallableLM`, `OllamaLM` (stdlib HTTP), `OllamaError` |
| `src/session.py` | `Session` — persistent multi-turn conversation (file-backed, context-manager safe) |
| `src/pipeline.py` | `Pipeline` — composable explicit stage chain with intermediates + custom steps |
| `src/cli.py` | Query CLI: `run_query`, `build_parser`, `resolve_config`, `main` |
| `src/retrieval/lexical.py` | BM25 + grep + key-phrase extraction |
| `src/retrieval/semantic.py` | Hashing-embedding cosine (deterministic surrogate) |
| `src/retrieval/fusion.py` | Weighted Reciprocal Rank Fusion |
| `src/stages/inspector.py` | Stage 0 + `REPLEnvironment` |
| `src/stages/retriever.py` | Stage 1 (hybrid + budgeting) |
| `src/routing.py` | `classify_task` — deterministic task-category routing |
| `src/stages/reasoner.py` | Stage 2 |
| `src/stages/memory_gate.py` | Stage 3 (episodic-first) |
| `src/memory/episodic_store.py` | SQLite (+FTS5) append-only store (context-manager safe) |
| `src/memory/consolidation.py` | Gated consolidation logic |
| `src/compiler/metrics.py` | `harness_metric`, dataset/eval primitives |
| `src/compiler/mipro.py` | MIPRO-style config search |
| `src/compiler/gepa.py` | GEPA-style reflective evolution + skill constraints + DSPy signature bridge |
| `src/dspy_runtime/` | Real DSPy runtime (gated): `adapters.py` (parse/render), `runtime.py` (configure + program builders), `live_eval.py` (opt-in neural eval) |
| `src/retrieval/learned.py` | Optional learned dense embedder (Ollama) + dense-RAG baseline (gated) |
| `src/harness.py` | `AutoHarness`, `build_run_fn` (incl. opt-in `adaptive_windows`) |
| `src/evaluation/` | `dataset.py` (+ seeded `build_large_dataset`), `budget.py`, `experiments.py`, `bundle.py` (`run_full_eval`), `ablation.py` (no-harness baseline, weight-sensitivity, memory, injection), `scaling.py` (bootstrap CIs), `longmemeval.py` (real benchmark loader + bottleneck analysis) |
| `src/figures/` | `plots.py` (data-driven matplotlib), `diagrams.py` (architecture figures), `manifest.py` (figure SSOT) |
| `src/evaluation/schemas.py` | Typed payloads for committed JSON → plot pipeline |
| `src/manuscript_variables.py` | `{{…}}` token generation (reads committed aggregate JSONs) |

## Commands

```bash
# Tests + coverage (authoritative gate; confirm collected > 0 and coverage >= 90%)
uv run --project working/thalia pytest working/thalia/tests/ \
  --cov=working/thalia/src --cov-report=term-missing --cov-fail-under=90

# Single test
uv run --project working/thalia pytest working/thalia/tests/test_harness.py -v

# Regenerate artifacts (thin orchestrators; print output paths)
uv run --project working/thalia python working/thalia/scripts/run_harness_eval.py
uv run --project working/thalia python working/thalia/scripts/run_compiler.py
uv run --project working/thalia python working/thalia/scripts/run_pipeline.py
uv run --project working/thalia python working/thalia/scripts/generate_figures.py
uv run --project working/thalia python working/thalia/scripts/build_dashboard.py
uv run --project working/thalia python working/thalia/scripts/z_generate_manuscript_variables.py

# Run a query (configurable: file < THALIA_* env < CLI flags)
uv run --project working/thalia python working/thalia/scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json

# Real DSPy runtime (needs the `dspy` extra; otherwise prints a notice and exits 0)
uv pip install --python working/thalia/.venv/bin/python "dspy-ai>=2.5"
uv run --project working/thalia python working/thalia/scripts/run_dspy.py

# Record the real extractive-vs-neural measurement (needs a live Ollama model);
# writes data/neural_eval.json, which the backend-comparison figure + §07 tokens read
uv run --project working/thalia python working/thalia/scripts/run_neural_eval.py

# Other gated recorders (each writes a committed aggregate JSON read by figures + tokens):
uv run --project working/thalia python working/thalia/scripts/run_learned_retrieval.py    # learned dense embedder vs surrogate
uv run --project working/thalia python working/thalia/scripts/run_injection_probe.py       # context-poisoning resistance + neural row

# Real LongMemEval_S benchmark (download once, then record); needs Ollama for neural rows:
bash working/thalia/scripts/get_longmemeval.sh
uv run --project working/thalia python working/thalia/scripts/run_longmemeval.py            # accuracy/grounding/composite + bootstrap CIs
uv run --project working/thalia python working/thalia/scripts/run_longmemeval_bottleneck.py # ranking-vs-Inspector recall, max_windows sweep, adaptive fix
```

## Extension points

- **Real LM:** pass any object with `complete(prompt: str) -> str` as `lm=` to
  `AutoHarness` / `Reasoner`.
- **Real embedder:** replace `src/retrieval/semantic.py::SemanticIndex` (same
  `top_k(query, k)` contract).
- **Real DSPy:** install the `dspy` extra. Two real seams open up without changing
  the core: `to_dspy_signature` (THALIA signature → real `dspy.Signature`) and the
  full `src/dspy_runtime/` runtime — a real `dspy.Predict` program and a real
  `dspy.BootstrapFewShot` optimizer, both backed by the real deterministic
  `ExtractiveLM` (no mock/stub; offline and reproducible). Run via `scripts/run_dspy.py`.
- **Real neural LLM:** `configure_ollama(model="gemma3:4b")` wires `dspy.LM` → litellm
  → a live local Ollama model (e.g. `ollama pull gemma3:4b`), so the same dspy program
  runs against real generations. `ollama_model_available()` gates it; `run_dspy.py`
  records the neural answer, and `TestRealNeuralDspy` validates real Gemma output.
- **Composable Pipeline:** `src/pipeline.py::Pipeline` exposes the four stages as
  an inspectable, chainable sequence. Insert custom steps between stages, inspect
  intermediates, or run partial pipelines (e.g. Inspector-only). See
  `tests/test_pipeline.py` for usage patterns.
- **Context managers:** `Session` and `EpisodicStore` both support `with` blocks
  so resources are always cleaned up, even on exceptions.
- **Serialisation:** `HarnessOutput.to_dict()` and `HarnessConfig.to_yaml()`/`from_yaml()`
  provide round-trip serialisation without duplicating field mappings.
- **Type safety:** `src/py.typed` marks the package as PEP 561 typed; `__version__`
  is exported at the top level.

## Scope honesty

Two boundaries are load-bearing and must be preserved in any prose: (1) the
extractive LM bounds accuracy; (2) the semantic lane is a sub-word surrogate, so
the lexical-vs-dense magnitude of the agentic-search study is not reproduced
locally. Do not let generated or edited text claim otherwise. The in-house
`MIPRO`/`GEPA` compilers are the project's own deterministic engine, honestly
labelled "-style"/"analogue" — not a fake of `dspy`. When `dspy` is installed,
`src/dspy_runtime/` runs the *real* dspy `Predict`/optimizer; the deterministic
core and the headline results remain extractive-bounded as documented. Citations marked
"as provided" in `manuscript/references.bib` come from the commissioning brief.
