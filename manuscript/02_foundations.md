# Foundational Research {#sec:foundations}

This section analyses the four foundational works and the reproducible-research
substrate, extracting from each the specific design implication THALIA implements.

## DSPy: declarative language-model pipelines {#sec:found-dspy}

DSPy [@khattab2023dspy] abstracts LM pipelines as imperative computational graphs
in which LMs are invoked through declarative modules. Rather than hard-coded
prompt templates discovered by trial and error, DSPy specifies *what* must be
produced — typed inputs and outputs via **Signatures** — rather than *how*. It
decomposes into four primitives: Signatures (declarative I/O), Modules
(`Predict`, `ChainOfThought` [@wei2022cot], `ReAct` [@yao2023react], …),
Programs (modules wired into graphs), and Optimizers (compilers that tune
instructions and few-shot examples against a metric). One prominent
optimizer, MIPROv2, bootstraps few-shot candidates,
proposes instruction variants, and searches the combined space with Bayesian
optimization.

**Implication for THALIA.** Separate program structure from optimization strategy.
Deterministic code handles parsing, filtering, routing, and tool dispatch; the
model handles judgment. Each stage — inspector, retriever, reasoner, memory gate —
is a first-class typed signature with explicit input/output fields
(`src/signatures/`), and the whole pipeline is exposed to an optimizer with a
well-defined metric ([@sec:harness_design]).

## Recursive Language Models {#sec:found-rlm}

RLMs [@zhang2025rlm] treat a long prompt as part of an external environment rather
than as direct neural input. The prompt is placed as a variable in a REPL the
model programmatically examines: **peek** at structure, **grep/regex filter** to
narrow the search space, **partition + map** recursive sub-calls over chunks,
**summarize**, and **verify**. The external interface is identical to a standard LM
call, so `rlm.completion(messages)` is a drop-in replacement.

**Implication for THALIA.** The REPL-environment paradigm maps directly onto the
Inspector stage: load history as a variable, apply grep/regex anchored on query
terms, and emit only compact evidence windows plus metadata — never the full
context ([@sec:stage-inspector]). `src/stages/inspector.py::REPLEnvironment`
implements `peek`, `grep`, and line-addressable `window` operations.

## Memory consolidation faults {#sec:found-memory}

This study [@zhang2026memory] surfaces a failure mode in consolidated agentic
memory: when an LLM continuously rewrites past trajectories into a textual memory
bank, utility *first rises, then degrades*, and can fall below the no-memory
baseline — even when consolidating from ground-truth solutions. The regression
traces to the consolidation step, not the underlying experience. Agents that
preserve raw episodes by default and gate consolidation via explicit
Retain/Delete/Consolidate actions roughly double the accuracy of forced-
consolidation counterparts; disabling consolidation entirely matches that regime
(reported by the source but not independently reproduced by THALIA — see
[@sec:repro-provenance]).

**Implication for THALIA.** Raw episodes are first-class evidence. The Memory Gate
always appends the raw turn to an append-only store and *only* consolidates a
derived MEMORY.md delta when explicitly gated ([@sec:stage-memory]). Automatic
per-turn consolidation — the documented failure mode — is structurally impossible:
`src/memory/consolidation.py::should_consolidate` requires both a Reasoner request
and an explicit criterion.

## Agentic search: is grep all you need? {#sec:found-grep}

This empirical study [@sen2026grep] compares lexical (grep/regex) and semantic
(dense) retrieval across models, harnesses, and tool-calling paradigms on
LongMemEval. Its abstract reports that grep generally yields higher accuracy than
vector retrieval in the study's comparisons, while overall scores still depend
strongly on the harness and tool-calling style. We cite that external result but
do not independently reproduce its model/harness comparison here. Under
increasing session noise, the source studies how the ordering changes; THALIA
uses that motivation for a bounded, local surrogate diagnostic rather than
importing the source's magnitude or treating its ranking as universal.

**Implications for THALIA.** (i) Lexical-first, hybrid by default — grep/BM25 as
the inline lane, semantic as fallback. (ii) Weighted Reciprocal Rank Fusion
[@cormack2009rrf] to merge lanes and optional Maximal Marginal Relevance
[@carbonell1998mmr] when diversity re-ranking is requested. (iii) Sparse context
budgeting — inline when the result set fits, file-based overflow otherwise.
(iv) Harness-conditioned lane weighting per detected task category. All four are implemented in
`src/retrieval/` and `src/stages/retriever.py` ([@sec:stage-retriever]).

## `docxology/template`: reproducible generative research {#sec:found-template}

The `template/` repository [@aii2026template] applies infrastructure-as-code to
the research lifecycle: a two-layer architecture separates reusable infrastructure
from self-contained project workspaces, connected by an eight-stage build pipeline
with a Zero-Mock testing policy and a project coverage gate of {{CONFIG_COV_GATE}}%,
cryptographic hashing, and structural validation. Its **documentation duality**
equips every directory with human-readable `README.md` and machine-readable
`AGENTS.md`, and each module carries a `SKILL.md` aligned with the Model Context
Protocol [@anthropic2025mcp] — the same pattern Hermes uses for its skill
catalog.

**Implication for THALIA.** The harness is built inside `template/` and inherits
its discipline: every stage carries a `SKILL.md`, the eight build stages map onto
the harness's compile-and-validate lifecycle ([@sec:integration]), and the
manuscript's numbers are generated tokens, not hand-typed values
([@sec:reproducibility]).

![Schematic foundations-to-THALIA stage map. Each foundation work maps to one or more THALIA stages, colour-coded by the stage palette. This diagram records conceptual provenance, not observations: there is no sample unit, sample size, uncertainty method, model estimate, or population claim.](../output/figures/foundations_map.png){#fig:foundations_map width=90%}
