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

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21763245.svg)](https://doi.org/10.5281/zenodo.21763245)

> **Status:** public v0.1.0 research release, rendered only when
> explicitly requested through the template pipeline. Runnable
> and covered by the strict local test gate; generated outputs are gitignored. "In-progress"
> describes the project's lifecycle stage (not yet promoted to a public template
> exemplar), independent of the docs/manuscript/package's own publish-readiness —
> see [`PUBLICATION_READINESS.md`](PUBLICATION_READINESS.md) for the current
> assessment of whether *this checkout's* code and manuscript are ready to submit.

> **Release identity:** MIT-licensed source and the rendered manuscript are
> archived in the public Zenodo record
> [10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245), with the
> canonical source at [github.com/docxology/thalia](https://github.com/docxology/thalia).

> **Public release:** v0.1.0 is public on GitHub at the annotated `v0.1.0` tag
> and archived at the DOI above. The exact commit, file checksums, validation
> gates, and release boundary are recorded in
> [`docs/release_receipt.md`](docs/release_receipt.md). This release authority
> does not promote model-quality, integrity-advantage, or production-readiness
> claims; those remain separately gated in [`PUBLICATION_READINESS.md`](PUBLICATION_READINESS.md).

## What THALIA is

THALIA is five composable stages that turn an unstructured LLM agent into a
declarative, inspectable, evidence-grounded, compiler-optimizable pipeline:

1. **Inspector** (Stage 0) — Loads session history as external state into a REPL
   environment, greps for query-anchored evidence, and emits compact evidence
   windows with auditable metadata. The full transcript stays external to the
   model call; only selected windows are forwarded. *Foundation: Recursive
   Language Models.*

2. **Retriever** (Stage 1) — Ranks evidence through a lexical-first hybrid: a
   BM25/grep lane for precise literal matches, a hashing-embedding semantic lane
   for paraphrase coverage, and weighted Reciprocal Rank Fusion to merge them.
   Sparse context budgeting picks inline or file-based delivery.
   *Foundation: Is Grep All You Need?*

3. **Reasoner** (Stage 2) — Produces a typed answer with auditable citation
   support from ranked evidence. Routes multi-hop/code/knowledge-update tasks
   through a deterministic ReAct-style read-integrate selection path and uses one
   model completion; it does not claim hidden chain-of-thought.
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

## Research claim and scope

THALIA is not a benchmark entry — it is a **methodological proposal** supported
by executable contracts and finite diagnostic evaluations: an agentic harness
should be declarative (typed stages, not prompt strings),
inspectable (context is external state you can grep), evidence-grounded (raw
episodes are first-class and never overwritten), lexically anchored (precise
literal retrieval first, semantic coverage second), and compiler-optimized (the
pipeline is searched against a metric, not tweaked by hand).

The evaluation makes two honest scope boundaries explicit:
- The extractive LM's answer-generation behavior bounds token-F1 on these probes
  (a real neural model changes the observed, model-dependent scores).
- The semantic lane is a sub-word hashing surrogate, not a learned dense retriever
  (so the lexical-vs-dense *magnitude* of the agentic-search study is not
  reproduced locally — only the *direction* is).

Recorded measurements include: a held-out before/after optimizer
comparison, a finite context-poisoning probe with equal recorded poisoning rates
and a lexical cited-excerpt/source-exposure proxy, an external
LongMemEval_S benchmark run with descriptive bootstrap intervals, and a bottleneck localisation
showing that, in the retained long-context slice, Inspector context-narrowing —
not full-haystack retrieval ranking — is the observed recall bottleneck. The
adaptive Inspector is evaluated as a fixed policy intervention on that slice;
it is evidence for a composable diagnostic, not a causal or universal guarantee.
The evaluation also includes a finite metric-construct audit that reports the
support proxy beside source-index citation precision and recall, session
reachability, answer token-F1, and evidence efficiency. These measures make
the proxy's observable components explicit while preserving the boundary that
source-index overlap is not sentence-level entailment or answer-quality
assessment.

The v2 research campaign extends this evidence with nested, question-type-balanced
Gemma cohorts at 100/250/500 questions, a matched Hermes sensitivity cohort, a
five-policy Inspector bottleneck study, learned nomic-embed-text ranking
diagnostics, a pre-registered ten-seed synthetic sensitivity lane, and held-out
compiler validation. Live rows and atomic checkpoints are stored under a
user-selected external campaign root; an incomplete tier cannot replace a
retained aggregate, and all model-dependent values remain finite local
observations rather than deterministic or population-level claims.

The separate model-quality lane is deliberately not inferred from that campaign.
It defines a blinded LongMemEval_S protocol with a stratified exploratory pilot
followed by a held-out confirmatory set, two model families, and three
answer/evidence conditions per model. The publication path requires two
independent expert raters and blinded adjudication. A local-LLM-judge runner is
available for reproducible packet, rubric, and parser diagnostics only; its
labels are non-promotable. The study measures answer-level correctness,
completeness, evidence faithfulness, usefulness, abstention, safety, and
calibration, then issues a certificate that is either explicitly promoted or
remains `complete_not_promoted`. Raw answers, evidence packets, annotations, and
adjudications stay under a user-selected external quality root; no quality aggregate
is committed until the expert-rater certificate passes its frozen thresholds and
digest check.
Production readiness is a separate operational gate covering latency, cost,
privacy, rollback, monitoring, drift, and red-team evidence.

## Quick start

```bash
# From the repository root.
uv sync --project . --extra dev
uv run --project . --extra dev python scripts/00_preflight.py
PYTHONWARNINGS=error::ResourceWarning uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing --cov-report=json:output/reports/coverage.json \
  --junitxml=output/reports/pytest.xml --cov-fail-under=90
uv run --project . --extra dev mypy src
uv run --project . --extra dev ruff check src tests scripts

# Regenerate evaluation artifacts and figures.
uv run --project . --extra dev python scripts/run_harness_eval.py  # quick smoke grid
# Publication-size deterministic audit:
uv run --project . --extra dev python scripts/run_harness_eval.py \
  --per-category-values 25 50 100 250 \
  --seeds 0 1 2 3 4 5 6 7 8 9 \
  --n-boot 2000
uv run --project . --extra dev python scripts/run_compiler.py
uv run --project . --extra dev python scripts/run_seed_sensitivity.py
uv run --project . --extra dev python scripts/run_compiler_generalization.py \
  --per-category 10 \
  --seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 \
  --gepa-iterations 4
uv run --project . --extra dev python scripts/analyze_integrity_advantage.py
uv run --project . --extra dev python scripts/run_pipeline.py
uv run --project . --extra dev python scripts/generate_figures.py
uv run --project . --extra dev python scripts/z_generate_manuscript_variables.py
uv run --project . --extra dev python scripts/run_demo.py
uv run --project . --extra dev python scripts/build_dashboard.py
uv run --project . --extra dev python scripts/validate_artifacts.py

# v2 live research (raw evidence stays outside the repository; no promotion by default)
uv run --project . --extra neural python scripts/run_research_campaign.py \
  --output-root /path/to/external/thalia_campaigns
uv run --project . --extra neural python scripts/run_bottleneck_campaign.py \
  --output-root /path/to/external/thalia_campaigns

# model-quality lane (raw answers/annotations stay external; thresholds freeze after pilot)
uv run --project . --extra neural python scripts/run_quality_campaign.py --phase pilot
uv run --project . --extra dev python scripts/analyze_quality.py --help
uv run --project . --extra dev python scripts/freeze_quality_protocol.py --help
uv run --project . --extra dev python scripts/promote_quality_report.py --help
uv run --project . --extra dev python scripts/analyze_production_readiness.py --help
uv run --project . --extra dev python scripts/promote_production_readiness.py --help
uv run --project . --extra dev python scripts/run_seed_sensitivity.py
uv run --project . --extra dev python scripts/run_compiler_generalization.py

# Re-render the PDF and validate output (run LAST, after every artifact above is
# fresh — the PDF embeds the figures/tokens generated by the steps above and
# goes stale silently if this step is skipped).
# Optional external integration: requires the sibling template checkout. The
# adapter creates a temporary exact project link and removes it on exit.
uv run --project ../template python scripts/render_pdf_external.py --validate
```

PDF rendering is an optional external integration. The standalone adapter
removes its temporary project link on exit; the sibling template may still
report its optional-directory output-structure check as a non-fatal warning.
The local PDF, manuscript, figure, token, and artifact checks remain the
authoritative THALIA gates.

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
uv run --project . --extra dev python scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
THALIA_TOP_K=4 uv run --project . --extra dev python scripts/run_query.py --query "..." --config config/harness.yaml
uv run --project . --extra dev python scripts/run_query.py --query "..." --adaptive-windows --adaptive-window-ratio 5
```

```python
# Run these snippets from the standalone THALIA root so `src` is importable.
# Configure: file < env (THALIA_*) < explicit override
from src.config import load_config, default_config
config = load_config("config/harness.yaml").with_(top_k=4)

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

Every deterministic-core mechanism is pure deterministic Python (no unseeded randomness, no
wall-clock, no network). The only judgment step — the Reasoner — sits behind a
one-method `LMClient` protocol whose default is a deterministic extractive
responder. A real LLM, a learned embedder, or real DSPy/GEPA each drop in behind
their respective interface without touching any other stage.

**Two honest scope boundaries** (see the [neural comparison](docs/manuscript/07c_evaluation_baseline_neural_and_context_poisoning.md) and [learned-retrieval diagnostics](docs/manuscript/07d_evaluation_retrieval_learned_embedder_and_noise.md)):
the extractive LM bounds token-F1 accuracy, and the semantic lane is a hashing
sub-word surrogate rather than a learned dense retriever — so the lexical-vs-dense
*magnitude* of the agentic-search study is intentionally not reproduced locally.

## Real DSPy (no mock/stub)

`dspy-ai` is an optional `dev`/`neural` extra. The deterministic core remains
installable without it; when installed, the DSPy integration is always the real
thing, not a stand-in: `to_dspy_signature`
builds a genuine `dspy.Signature` from any THALIA signature, and
[`src/dspy_runtime/`](src/dspy_runtime/) runs a real `dspy.Predict` program and a
real `dspy.BootstrapFewShot` optimizer — both backed by the project's real
deterministic `ExtractiveLM`, so the whole path is offline, reproducible, and
mock-free. The deterministic *core* still never imports `dspy` directly — only
these gated seams do — so the headline results are unchanged either way.

```bash
uv run --project . --extra neural python scripts/run_dspy.py
```

**Real neural LLM (optional).** Point dspy at a live local model and the same path
runs against real generations — no surrogate. With [Ollama](https://ollama.com)
serving a small Gemma, `configure_ollama()` wires `dspy.LM` → litellm → Ollama, and
`run_dspy.py` records its answer (`neural_prediction`) alongside the deterministic one:

```bash
ollama pull gemma3:4b
uv run --project . --extra neural python scripts/run_dspy.py   # adds a real gemma3:4b answer
```

The in-house `MIPRO`/`GEPA` compilers remain the project's own deterministic engine
(honestly labelled "-style"), distinct from this real-dspy path.

## Composability and resource safety

- **Composable Pipeline** (`src/pipeline.py`) — chain stages explicitly, insert
  custom steps, inspect intermediates, or run partial pipelines.
- **Context managers** — `AutoHarness`, `Pipeline`, `MemoryGate`, `Session`, and
  `EpisodicStore` support `with` blocks; caller-owned stores are never closed.
- **Serialisation** — `HarnessOutput.to_dict()`, `HarnessConfig.to_yaml()`/`from_yaml()`
  provide round-trip serialisation from the dataclasses themselves.
- **Type safety** — `py.typed` marker (PEP 561) + `__version__` exported at the
  top level.
- **Formalism traceability** — `data/paper_audit.yaml` and the generated
  `output/reports/formalism_traceability.json` connect equations to resolvable
  implementation symbols, tests, manuscript sections, and composition edges. A
  passing map is an anchor-integrity check, not a blanket proof that every
  scientific assumption or integration is valid.

## Validation

- **Authoritative local gate:** run the standalone command above. It must collect
  tests, meet the 90% `src/` coverage floor, and report optional neural/benchmark
  skips explicitly when their external prerequisites are absent. The generated
  verification summary records the observed test count, coverage, command
  results, and explicit external PDF boundary. The locked dev extra also carries
  the static type-check and lint gates (`mypy src` and `ruff check src tests scripts`).
- **Zero-Mock policy** — no `unittest.mock`, `MagicMock`, or `mocker.patch`.
  HTTP tests use a real in-process server; file tests use real temp files.
- **13 executable invariants** — BM25 idf non-negativity, RRF monotonicity, MMR
  lambda=1 reducing to relevance, episode append-only, consolidation gate strictness,
  harness determinism, answer grounding, query-expansion superset, recall read-only,
  recency-zero noop, static determinism guard, and more.
- **30 registered figures** — all generated deterministically from `src/evaluation`
  and `src/figures`, including the title-page cover visual abstract, the
  per-category component breakdown, the metric-construct-audit heatmap,
  pipeline evidence-flow, GEPA component trajectory, and multi-seed
  sample-size precision audit.
- **Research-grade uncertainty accounting** — fixed-stratum bootstrap intervals,
  whole-seed-cluster paired deltas, Wilson score intervals, exact McNemar tests,
  and a complete named Holm family are serialized into the ledger and surfaced in
  the sample-size and statistical-audit figures. These estimates describe the
  generated machinery benchmark; they are not population claims.
- **Caption and provenance contract** — every registered figure carries a
  renderer-independent caption describing its unit, estimand, uncertainty, data
  tier, and limitation; the manuscript captions are generated/checked alongside
  the figures and tokens.
- **Generated manuscript variables** referenced across the sections — all emitted
  from live code, with the integrity gate rejecting missing or hardcoded result values.

## License and release metadata

The THALIA source code is licensed under the [MIT License](LICENSE). Citation
and archive metadata, including the release DOI, are maintained in
[`CITATION.cff`](CITATION.cff) and `.zenodo.json`. MIT
covers this project's code and does not by itself grant redistribution rights
for external benchmark data, model weights, raw answers, credentials, or other
third-party artifacts. The current release boundary is tracked in
[`docs/release_readiness.md`](docs/release_readiness.md).
Contributor workflow and responsible security reporting are documented in
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md).

## Layout

- `src/` — the harness (signatures, stages, retrieval, memory, compiler) + operability (config, llm, session, cli, pipeline, evaluation, figures)
- `config/harness.yaml` — canonical loadable configuration (overridable via `THALIA_*` env / CLI flags)
- `tests/` — Zero-Mock suite, one file per module; ≥ 90% `src/` coverage gate
- `scripts/` — thin orchestrators (preflight, eval, compile, pipeline, figures, dashboard, demo, manuscript tokens)
- `skills/` — `SKILL.md` per stage (machine-readable capability descriptors)
- `docs/manuscript/` — the full write-up (sections 00–99) with generated `{{…}}` tokens
- `domain_profile.yaml` · `experiment_plan.yaml` · `data/claim_ledger.yaml` · `data/paper_audit.yaml` — evidence and audit registries

See [`AGENTS.md`](AGENTS.md) for the agent-facing technical reference.
