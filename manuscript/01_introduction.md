# Introduction {#sec:introduction}

Large-language-model agents are usually built by accreting prompt strings,
retrieval heuristics, memory summaries, and tool-calling exceptions until a demo
works. That practice does not compose, does not transfer, and degrades silently:
interfaces remain implicit, memory rewrites can erase the raw evidence that made a
fact true, and retrieval failures are hard to distinguish from reasoning failures.
ATLAS takes the opposite stance. An agentic harness should be **declarative**
(typed stages, not prompt strings), **inspectable** (context is external state you
can grep, not an opaque blob stuffed into a neural call), **evidence-grounded**
(raw episodes are first-class and never overwritten), **lexically anchored**
(precise literal retrieval first, semantic coverage second), and
**compiler-optimized** (the pipeline is searched against a metric, not tweaked by
hand).

This manuscript synthesises four foundational works and one infrastructure
substrate into a single coherent system, then implements that system as runnable,
deterministic, fully-tested code.

The central methodological move is to make every handoff explicit. The Inspector
does not "summarize context"; it emits line-addressed evidence windows with grep
patterns and confidence metadata. The Retriever does not "find relevant context";
it exposes lexical and surrogate-semantic rankings, fuses them by a documented
score, and records whether evidence is delivered inline or by file. The Reasoner
does not return an untyped blob; it returns an answer, a task class, a trace, and
source citations. The Memory Gate cannot rewrite history; it appends the raw turn
first and only then decides whether a derived memory delta is warranted. The
Compiler does not rewrite source code or mutate prose; it searches a bounded
configuration surface and records the full trace.

## The four foundations and the substrate

1. **DSPy** [@khattab2023dspy] — prompts as parameterized code; pipelines as typed
   computational graphs that a compiler optimizes against a metric.
2. **Recursive Language Models** [@zhang2025rlm] — treat a long prompt as a
   variable in a REPL the model programmatically inspects, rather than as direct
   neural input.
3. **Agentic search** [@sen2026grep] — grep/BM25 generally outperforms vector
   retrieval in the cited inline comparisons, but the result is harness- and
   tool-style-dependent; retrieval-plus-orchestration is the correct unit of
   analysis.
4. **Memory consolidation faults** [@zhang2026memory] — continuously rewriting a
   memory bank degrades utility below the no-memory baseline; raw episodes must be
   preserved and consolidation explicitly gated.
5. **`docxology/template`** [@aii2026template] — a two-layer reproducible-research
   substrate (Zero-Mock testing, coverage gates, cryptographic provenance,
   `AGENTS.md`/`SKILL.md` documentation duality) that ATLAS is built inside.

The Hermes Agent ecosystem [@nous2026hermes; @nous2026selfevolution] supplies the
concrete engineering pattern that ties these together: a strictly-ordered prompt
stack with a *frozen* memory snapshot, an episodic SQLite/FTS5 store distinct from
the consolidated `MEMORY.md` [@sqlite2026fts5], and a DSPy + GEPA-style evolution
loop [@agrawal2025gepa] that mutates skills against execution traces under hard
constraints.

## What ATLAS contributes

ATLAS is not a new model and makes no SOTA claim. Its contribution is a clean,
composable, *operational* embodiment of these principles:

- **Five stages, each a typed signature.** Inspector, Retriever, Reasoner, and
  Memory Gate are the runtime; the Compiler operates on them offline
  ([@sec:harness_design]).
- **A methods-first harness boundary.** Stage contracts live in `src/signatures/`,
  execution logic lives in `src/stages/` and `src/compiler/`, and the manuscript
  reports the same objects the tests exercise. The artifact is therefore a
  runnable method specification, not just a conceptual architecture diagram.
- **A deterministic core.** Every mechanism — BM25/grep, hashing-embedding cosine,
  weighted RRF, REPL-style narrowing, the SQLite episodic store, gated
  consolidation, and the MIPRO/GEPA search loops — is pure, deterministic Python.
  The only judgment step (the Reasoner) sits behind a one-method language-model
  protocol whose default is a deterministic extractive responder. A real LLM, or
  real DSPy/GEPA, drops in without touching the rest.
- **Reproducibility by construction.** The harness is built inside `template/`:
  Zero-Mock tests, a {{CONFIG_COV_GATE}}% coverage gate on `src/`, machine-readable `SKILL.md`
  descriptors per stage, and a manuscript whose every result number is a generated
  token ([@sec:reproducibility]).

The evaluation should be read accordingly. It is a deterministic local validation
of method composition, not a benchmark claim about learned retrievers or frontier
language models. The default Reasoner is intentionally extractive, and the
semantic lane is intentionally a hashing surrogate so the entire stack can run
offline. Those are the two replacement boundaries: a real model and a learned embedder
can be inserted behind stable interfaces without changing the Inspector, Memory
Gate, Compiler, tests, or manuscript-variable path.

## Reader's guide

- **[@sec:foundations]** analyses the four foundational works and the substrate.
- **[@sec:hermes]** describes the Hermes prompt-assembly and self-evolution patterns ATLAS adopts.
- **[@sec:harness_design]** specifies the {{CONFIG_NUM_STAGES}} stages — the methodology.
- **[@sec:integration]** maps ATLAS onto the `template/` build/validation lifecycle.
- **[@sec:active_inference]** relates the architecture to Active Inference.
- **[@sec:evaluation]** reports the deterministic local evaluation, with an explicit scope boundary.
- **[@sec:reference_architecture]** consolidates design principles and the file structure.
- **[@sec:reproducibility]** records the provenance and how to regenerate every artifact.
