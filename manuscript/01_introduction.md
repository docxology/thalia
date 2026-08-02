# Introduction: Research Question and Contributions {#sec:introduction}

Long-context agents combine a language model with retrieval, context selection,
memory, and tool orchestration. That composition creates a measurement problem:
an answer can fail when the system fails to surface evidence, the model fails to
use surfaced evidence, memory is rewritten, or the metric rewards the wrong answer
shape. Retrieval-augmented generation already frames
external memory as a complement to parametric knowledge [@lewis2020rag], while
long-context evaluation shows that even models with large windows can use relevant
information unevenly by position [@liu2024lost]. A harness that reports only the
final answer therefore obscures the mechanism that failed.

THALIA treats the harness as a research instrument. It is **declarative** (typed
stages with explicit contracts), **inspectable** (context is external
state that can be queried), **evidence-preserving** (raw episodes are retained),
**lexically anchored** (literal witnesses are retrieved before semantic fallback),
and **compiler-searchable** (bounded configuration choices leave an auditable
trace). The scope is a measurable route from evidence to answer. Universal claims
about agent design require broader comparative evidence.

This manuscript synthesises four research lenses and one reproducible-research
substrate into a single executable method. It then evaluates the method in
separate evidence tiers so deterministic contract validation and model performance
remain distinct claims.

The central methodological move is to make every handoff explicit. The Inspector
emits line-addressed evidence windows with grep patterns and confidence metadata.
The Retriever exposes lexical and surrogate-semantic rankings, fuses them by a
documented score, and records whether evidence is delivered inline or by file.
The Reasoner returns an answer, a task class, a trace, and source citations. The
Memory Gate appends the raw turn before evaluating a derived memory delta. The
Compiler searches a bounded configuration surface and records the full trace.

![Schematic architecture map with no empirical unit, sample size, uncertainty interval, or model dependence. Query and history pass through inspection, retrieval, reasoning, and memory gating; arrows indicate typed data flow. The Compiler is a bounded offline loop with a recorded trace.](../output/figures/thalia_overview.png){#fig:thalia_overview width=95%}

## Four Research Foundations and the Reproducible Substrate

1. **DSPy** [@khattab2023dspy] — prompts as parameterized code; pipelines as typed
   computational graphs that a compiler optimizes against a metric.
2. **Recursive Language Models** [@zhang2025rlm] — place a long prompt in an
   external REPL variable that the model programmatically inspects before answer
   generation.
3. **Agentic search** [@sen2026grep] — grep/BM25 generally outperforms vector
   retrieval in the cited inline comparisons, with the magnitude conditioned by
   harness and tool style; retrieval-plus-orchestration is the correct unit of
   analysis.
4. **Memory consolidation faults** [@zhang2026memory] — continuously rewriting a
   memory bank degrades utility below the no-memory baseline; raw episodes must be
   preserved and consolidation explicitly gated.
5. **`docxology/template`** [@friedman2026template] — a two-layer reproducible-research
   substrate (Zero-Mock testing, coverage gates, cryptographic provenance,
   `AGENTS.md`/`SKILL.md` documentation duality) that THALIA is built inside.

The synthesis also sits within the broader retrieval-and-evaluation literature.
RAG establishes the value of coupling a generator to non-parametric evidence
[@lewis2020rag]; Lost in the Middle demonstrates the gap between evidence
exposure and evidence use [@liu2024lost]; and FActScore shows that lexical
overlap requires a separate factual-precision assessment [@min2023factscore].
THALIA uses these findings as separable measurement surfaces. Its retrieval,
answer, citation, and memory outputs can be inspected independently.

Citation-grounded generation research sharpens this separation. ALCE evaluates
citation recall and precision at the statement/evidence interface and reports
them alongside answer correctness [@gao2023alce]. ARES similarly separates
context relevance, answer faithfulness, and answer relevance in RAG evaluation
[@saadfalcon2024ares]. THALIA adopts the measurement principle while keeping its
offline core deliberately narrower: source-index precision and recall are
audits of declared evidence alignment, and the lexical support proxy remains a
mechanical diagnostic. Sentence-level entailment and human judgments remain
future evidence lanes.

This separation is also important for the planned quality study. LongMemEval
organises long-term memory around information extraction, multi-session and
temporal reasoning, knowledge updates, and abstention [@wu2025longmemeval].
LoCoMo adds very long-term question answering, event summarization, and
multimodal dialogue evaluation [@maharana2024locomo]. These benchmark families
cover complementary memory abilities; their automatic scores cover only part of
factuality and usefulness.
TruthfulQA demonstrates that truthfulness is a distinct failure surface rather
than a synonym for fluent answer generation [@lin2022truthfulqa]. For generated
answers, FActScore's atomic-claim decomposition supplies a more defensible unit
for factual precision than token overlap [@min2023factscore], while
SelfCheckGPT illustrates a separate, sampling-based route for detecting
inconsistency in black-box generations [@manakul2023selfcheckgpt]. THALIA uses
these works as construct boundaries: evidence reachability, answer correctness,
evidence faithfulness, usefulness, abstention, confidence calibration, and
operational readiness are recorded as related but non-interchangeable questions.

The planned confidence and abstention measurements likewise have a statistical
interpretation. Calibration asks whether a reported probability tracks empirical
correctness. Fluency and apparent certainty are separate observables; the
calibration literature shows why that distinction matters [@guo2017calibration]. Selective prediction
frames abstention as a risk--coverage trade-off [@geifman2017selective], and
inter-rater agreement measures label reliability. Construct validity requires
separate evidence that the rubric measures the intended construct
[@artstein2008agreement].
These distinctions motivate the manuscript's refusal to promote the operational
campaign or automatic proxies as a model-quality result.

The Hermes Agent ecosystem [@nous2026hermes; @nous2026selfevolution] supplies the
concrete engineering pattern that ties these together: a strictly-ordered prompt
stack with a *frozen* memory snapshot, an episodic SQLite/FTS5 store [@sqlite2026fts5]
distinct from the consolidated `MEMORY.md`, and a DSPy + GEPA-style evolution
loop [@agrawal2025gepa] that mutates skills against execution traces under hard
constraints.

## Contributions: What We Built, What We Found, and Why It Matters

THALIA is an executable research instrument for long-context memory systems.
Model architecture and state-of-the-art ranking are outside its scope. The
method contribution is a composable measurement boundary that makes evidence
flow, memory mutation, model substitution, and publication artifacts inspectable.

### What we built

Four design contributions define that boundary:

- **A typed contract graph.** The Inspector, Retriever, Reasoner, Memory Gate,
  and Compiler expose explicit inputs, outputs, evidence traces, and scope
  boundaries. Each handoff is testable, and each stage can be inspected without
  inferring its behavior from a final answer ([@sec:harness_design]).
- **Evidence-preserving state management.** The runtime appends raw episodes
  before evaluating gated consolidation, keeps the transcript outside the model
  prompt, and returns cited evidence with the answer. This preserves the source
  material needed to audit retrieval, memory, and answer failures.
- **A deterministic core with replacement lanes.** BM25/grep, hashing-based
  retrieval, weighted reciprocal-rank fusion, SQLite/FTS5 state, and bounded
  MIPRO/GEPA-style search run offline. A one-method LM protocol and a stable
  embedding interface allow genuine neural/DSPy backends and learned retrieval to
  be evaluated under the same stage contracts. The default extractive LM and
  hashing semantic lane remain explicitly labelled as bounded evidence tiers.
- **Source-bound research infrastructure.** Generated variables, formal anchors,
  claim-ledger bindings, figure metadata, artifact manifests, and rendering checks
  connect code, evidence, prose, and publication outputs. The resulting package
  is a reproducible method specification with inspectable evidence and build
  receipts ([@sec:reproducibility]).

### What we found

The experiments answer the three practical questions posed by the harness design:

- **The contract is executable.** The deterministic tier reaches composite
  {{RESULT_COMPOSITE}} on the fixed {{RESULT_NUM_EXAMPLES}}-example set, with
  answer token-F1 {{RESULT_ACCURACY}}, citation-support proxy
  {{RESULT_GROUNDING}}, and efficiency {{RESULT_EFFICIENCY}}. The
  {{RESULT_NUM_CANDIDATES}}-candidate compiler search ties on this easy set. Its
  primary finding is a complete, auditable trace with a deterministic tie rule;
  configuration improvement is unobserved on this distribution.
- **Failure surfaces are measurable before generation.** Tight-budget retrieval,
  evidence funnels, source-index diagnostics, noise probes, and bottleneck tests
  expose how context selection changes the evidence delivered to the Reasoner.
  In the retained bottleneck slice, ranking recall is {{RESULT_BN_RANKING_RECALL}}
  and Inspector recall is {{RESULT_BN_INSPECTOR_RECALL}}. The adaptive policy
  changes neural answer token-F1 from {{RESULT_BN_NEURAL_ACC_LO}} to
  {{RESULT_BN_ADAPTIVE_ACC}} on that slice, providing a targeted context-policy
  result with no general performance estimate.
- **Model substitution changes the result.** In the retained local comparison,
  {{RESULT_NEURAL_MODEL}} changes mean token-F1 from
  {{RESULT_EXTRACTIVE_MEAN_F1}} to {{RESULT_NEURAL_MEAN_F1}}, with paired
  difference {{RESULT_NEURAL_PAIRED_DELTA}} and descriptive interval
  {{RESULT_NEURAL_PAIRED_CI}}. On the external {{RESULT_LME_BENCHMARK}} slice,
  extractive and neural answer token-F1 are {{RESULT_LME_EXT_ACC}} and
  {{RESULT_LME_NEURAL_ACC}}. These are model- and host-specific transfer
  measurements; they are evidence about the replacement lane and its recorded
  configuration.
- **The clearest observed difference is a lexical cited-excerpt/source-exposure
  proxy.** Under the recorded injection probes, THALIA's cited excerpts contain
  the supplied gold value on {{RESULT_INTEGRITY_AUDIT_N}} of
  {{RESULT_INTEGRITY_AUDIT_N}} probes, with direction-normalized effect
  {{RESULT_INTEGRITY_AUDIT_DELTA}} and paired interval
  {{RESULT_INTEGRITY_AUDIT_CI}}. This proxy is not a true-source record,
  recoverable-source test, or claim-level auditability determination. The same
  probes show a poisoning effect of {{RESULT_INTEGRITY_POISON_DELTA}}. The
  composite baseline lift is {{RESULT_INTEGRITY_COMPOSITE_LIFT}} because citation
  support and evidence efficiency increase while raw answer token-F1 ties. These
  observations are narrow and preserve the negative controls needed for further
  testing.

### Why the method matters

The important contribution is a reusable measurement boundary for agentic memory
systems. The harness reports where evidence is selected, how memory is mutated,
which source indices are cited, and when a model-dependent backend changes the
answer. The current evidence identifies operational provenance as the clearest
advantage while showing equality on poisoning and no general answer-quality
advantage. Researchers can therefore vary context policies, retrieval
representations, generators, or memory gates while preserving the surrounding
contracts and provenance. That separation makes a failure diagnosable and an
intervention reproducible.

The most promising research direction is comparative evaluation under fixed
contracts. The current package supplies the executable scaffold for expert-rated
factuality, completeness, faithfulness, usefulness, abstention, calibration,
safety, and production readiness. Those constructs require the separate
protocols and acceptance gates defined in the repository. The present evidence
establishes method integrity and failure localization within the declared tiers;
general model-quality ranking and production certification remain open studies.

## Reading the Architecture and Evidence Tiers

- **[@sec:foundations]** analyses the four foundational works and the substrate.
- **[@sec:hermes]** describes the Hermes prompt-assembly and self-evolution patterns THALIA adopts.
- **[@sec:harness_design]** specifies the {{CONFIG_NUM_STAGES}} stages — the methodology.
- **[@sec:integration]** maps THALIA onto the `template/` build/validation lifecycle.
- **[@sec:active_inference]** relates the architecture to Active Inference.
- **[@sec:evaluation]** reports the deterministic local evaluation, with an explicit scope boundary.
- **[@sec:reference_architecture]** consolidates design principles and the file structure.
- **[@sec:reproducibility]** records the provenance and how to regenerate every artifact.
- **[@sec:operability]** covers the operable surface — configuration, the LM protocol, sessions, and the CLI.
- **[@sec:validation]** reports the executable invariants, fuzz testing, and negative results.
