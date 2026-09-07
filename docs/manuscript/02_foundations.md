# Foundations: Declarative Pipelines, Long-Context Access, Memory, Search, and Reproducibility {#sec:foundations}

This section analyses the four foundational works and the reproducible-research
substrate, extracting from each the specific design implication THALIA implements.
The works are complementary lenses with distinct evidence roles. DSPy addresses
program structure and optimization, RLMs address context access, the memory-fault
study addresses state mutation, agentic search addresses retrieval policy, and
the template supplies research infrastructure. THALIA's synthesis is an executable
design hypothesis. The sources provide complementary evidence; together they
motivate the executable synthesis without constituting a unified theory of agency.

## DSPy: Typed Program Structure and Compiler Optimization {#sec:found-dspy}

DSPy [@khattab2023dspy] abstracts LM pipelines as imperative computational graphs
in which LMs are invoked through declarative modules. DSPy specifies the required
inputs and outputs through **Signatures**, while modules and optimizers select
the implementation strategy. It decomposes into four primitives: Signatures
(declarative I/O), Modules
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
well-defined metric ([@sec:harness_design]). THALIA adopts the interface idea;
its local MIPRO/GEPA implementations are labelled “style” or “analogue,” while
the optional DSPy runtime is the genuine library path. A typed interface is a
software contract. Answer correctness requires its own outcome measurement.

## Recursive Language Models: Explicit Context Access {#sec:found-rlm}

RLMs [@zhang2025rlm] treat a long prompt as part of an external environment. The
prompt is placed as a variable in a REPL the
model programmatically examines: **peek** at structure, **grep/regex filter** to
narrow the search space, **partition + map** recursive sub-calls over chunks,
**summarize**, and **verify**. The RLM environment is conceptually adjacent to a
standard LM call. THALIA exposes `LMClient.complete(prompt: str) -> str`, while
`REPLEnvironment` owns the explicit peek/grep/window operations. The two protocols
share the external-context idea and have different interfaces.

**Implication for THALIA.** The REPL-environment paradigm maps directly onto the
Inspector stage: load history as a variable, apply grep/regex anchored on query
terms, and emit compact evidence windows plus metadata. The full transcript stays
in the external environment ([@sec:stage-inspector]). `src/stages/inspector.py::REPLEnvironment`
implements `peek`, `grep`, and line-addressable `window` operations.

Context exposure and context use are separate observables. The long-context
literature shows that models can underuse relevant material even when it is
present, especially when its position changes [@liu2024lost]. THALIA records
Inspector recall and Reasoner answer quality separately; a narrowing result is
evidence about exposure, while answer quality requires its own measurement.

## Memory Consolidation: Preserving Episodes and Controlling Drift {#sec:found-memory}

This study [@zhang2026memory] surfaces a failure mode in consolidated agentic
memory: when an LLM continuously rewrites past trajectories into a textual memory
bank, utility *first rises, then degrades*, and can fall below the no-memory
baseline — even when consolidating from ground-truth solutions. The regression
traces to the consolidation step; the underlying experience is a separate factor.
Agents that preserve raw episodes by default and gate consolidation via explicit
Retain/Delete/Consolidate actions roughly double the accuracy of forced-
consolidation counterparts; disabling consolidation entirely matches that regime.
Those values belong to the source study. THALIA records the finding as an
external evidence tier and supplies the local append-only and gated-consolidation
implementation described in [@sec:repro-provenance].

**Implication for THALIA.** Raw episodes are first-class evidence. The Memory Gate
always appends the raw turn to an append-only store and *only* consolidates a
derived MEMORY.md delta when explicitly gated ([@sec:stage-memory]). The
configured per-turn consolidation path is forbidden: the gate in
`src/memory/consolidation.py::should_consolidate` requires both a Reasoner
request and an explicit criterion.

The scope is one safety property within long-term memory. Systems such as
MemGPT [@packer2023memgpt], Mem0 [@chhikara2025mem0], TiMem [@li2026timem],
and APEX-MEM [@banerjee2026apexmem] explore richer memory representations,
temporal organization, and operational policies. They are adjacent comparison
points, not baselines in the present deterministic study. THALIA isolates one
safety property -- preserve the source episode and make consolidation
conditional -- so that it can be tested independently of a model's broader
memory competence.

## Agentic Search: Lexical Anchoring and Context Selection {#sec:found-grep}

This empirical study [@sen2026grep] compares lexical (grep/regex) and semantic
(dense) retrieval across models, harnesses, and tool-calling paradigms on
LongMemEval. The paper reports higher accuracy for grep than vector retrieval
in its own comparisons. That result remains tool-style-dependent, and overall
scores also depend strongly on the harness. We cite the external result and
keep its model/harness comparison in the external evidence tier. Under
increasing session noise, the source studies how the ordering changes; THALIA
uses that motivation for a bounded, local surrogate diagnostic. The source's
magnitude and ranking remain external evidence.

**Implications for THALIA.** (i) Lexical-first, hybrid by default — grep/BM25 as
the inline lane, semantic as fallback. (ii) Weighted Reciprocal Rank Fusion
[@cormack2009rrf] to merge lanes and optional Maximal Marginal Relevance
[@carbonell1998mmr] when diversity re-ranking is requested. (iii) Sparse context
budgeting — inline when the result set fits, file-based overflow otherwise.
(iv) Harness-conditioned lane weighting per detected task category. All four are implemented in
`src/retrieval/` and `src/stages/retriever.py` ([@sec:stage-retriever]).

The retrieval choice is a controlled representation question. Retrieval-augmented
generation couples a retriever
to a generator [@lewis2020rag], but the value of that coupling depends on both
what is surfaced and how the generator uses it. THALIA keeps those stages
separable so that a learned embedder, a different language model, or a different
budget can be evaluated without changing the contract graph.

## Friedman's template for reproducible generative research {#sec:found-template}

The `template/` repository [@friedman2026template] applies infrastructure-as-code to
the research lifecycle: a two-layer architecture separates reusable infrastructure
from self-contained project workspaces, connected by an eight-stage build pipeline
with a Zero-Mock testing policy and a project coverage gate of {{CONFIG_COV_GATE}}%,
cryptographic hashing, and structural validation. Its **documentation duality**
equips every directory with reader-readable `README.md` and machine-readable
`AGENTS.md`, and each module carries a `SKILL.md` aligned with the Model Context
Protocol [@anthropic2025mcp] — the same pattern Hermes uses for its skill
catalog.

**Implication for THALIA.** The harness is built inside `template/` and inherits
its discipline: every stage carries a `SKILL.md`, the eight build stages map onto
the harness's compile-and-validate lifecycle ([@sec:integration]), and the
manuscript's numbers are generated tokens emitted from the live variable map
([@sec:reproducibility]).

The substrate is methodological infrastructure. Its tests and provenance checks
make a claim auditable. Representativeness of deployed conversations requires a
separate sampling and validation design.

![Schematic traceability map with no empirical unit, sample size, or uncertainty interval. Each cited foundation maps to one or more THALIA stages; mappings record conceptual reuse, while source-system validation remains in the cited evidence.](../../output/figures/foundations_map.png){#fig:foundations_map width=90%}
