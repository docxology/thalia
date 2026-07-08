# Abstract {#sec:abstract}

<style>
body {
  max-width: 1120px !important;
  padding: 10px 14px !important;
}
a,
.toc a {
  color: #b00020 !important;
}
</style>

**THALIA** — Typed Harness with Analytical Lexical-Integrated Architecture — is a
typed, declaratively-specified agentic harness that fuses four research
threads with a reproducible-research substrate. From DSPy [@khattab2023dspy] it
takes the principle that prompts are parameterized code: every stage is a typed
*signature* specifying *what* to produce, not *how*. From Recursive Language
Models [@zhang2025rlm] it takes context-as-external-state: an Inspector loads
session history into a small REPL, greps for query-anchored evidence, and
forwards only compact windows — never the full context. From the agentic-search
study [@sen2026grep] it takes lexical-first hybrid retrieval: a BM25/grep lane,
a semantic lane, and weighted Reciprocal Rank Fusion [@cormack2009rrf]. From the
memory-consolidation-fault study [@zhang2026memory] it takes episodic-first
memory: raw episodes are never overwritten, and consolidation into a MEMORY.md
snapshot is explicitly gated. The fifth stage is a Compiler that treats the
harness itself as an optimizable program, searching parameter settings and
recording trace-reflective mutations rather than relying on ad-hoc prompt
tweaking [@nous2026selfevolution].

The contribution is **architectural and reproducible**, not a new model. THALIA is
implemented as {{CONFIG_NUM_STAGES}} composable stages, each a first-class
signature backed by a machine-readable `SKILL.md`, with the language-model layer
abstracted behind a protocol whose default is a deterministic extractive
responder. This makes the entire harness runnable and testable offline with zero
mocks: the suite exercises every stage on real data and SQLite, pins published
numbers through generated tokens, and validates source-to-render path hygiene. The
method is not a single heuristic but a contract stack: typed signatures constrain
interfaces; deterministic routing chooses reasoning style; retrieval lanes expose
ranked evidence and delivery mode; the Memory Gate records raw episodes before it
can summarize; and the Compiler emits an auditable optimization trace.

On a {{RESULT_NUM_EXAMPLES}}-example LongMemEval-style dataset the default
configuration reports composite {{RESULT_COMPOSITE}} (accuracy
{{RESULT_ACCURACY}}, grounding {{RESULT_GROUNDING}}, efficiency
{{RESULT_EFFICIENCY}}); the MIPRO-style search evaluates
{{RESULT_NUM_CANDIDATES}} candidate configurations and ties to full precision on
this easy set — an auditable trace, not a measured win. The genuinely adaptive step
is exercised separately by a real `dspy.BootstrapFewShot` optimiser over a real
`dspy.Predict` program; and dropping a real neural model ({{RESULT_NEURAL_MODEL}})
and dropping a real neural model ({{RESULT_NEURAL_MODEL}}, served locally through
Ollama) into the Reasoner slot — every other stage held fixed — raises mean
token-F1 from {{RESULT_EXTRACTIVE_MEAN_F1}} to {{RESULT_NEURAL_MEAN_F1}},
concentrated on the categories extraction cannot synthesise. (A second, harder
cloud validation against `tencent/hy3-preview` via OpenRouter is reported in
[@sec:eval-openrouter]: there the neural model *underperforms* on token-F1 because
concise correct answers are penalised by the metric, while winning the synthesis
and multi-hop cases extraction structurally cannot — the same LM-bounded-ceiling
story, not a second measured lift.) Beyond the synthetic set we run the **real
LongMemEval_S benchmark** [@wu2025longmemeval] ({{RESULT_LME_N_EXT}} questions over
~115k-token haystacks): accuracy collapses (extractive {{RESULT_LME_EXT_ACC}}, neural
{{RESULT_LME_NEURAL_ACC}}; {{CONFIG_CI_LEVEL}}% bootstrap CIs), and — localising the failure rather than
assuming it — we show the bottleneck is the Inspector's context-narrowing, not retrieval
ranking (the committed full-haystack aggregate recovers the evidence; per-mode
learned-embedder rows remain gated on a working local embedder). An opt-in **adaptive Inspector**
that scales the narrowing budget with context size then recovers most of that gap
automatically on the neural subset — up to the manually-tuned best
({{RESULT_BN_NEURAL_ACC_LO}} → {{RESULT_BN_ADAPTIVE_ACC}}) — while remaining a bit-for-bit
no-op on compact contexts. We are explicit about two scope boundaries: the
default extractive responder bounds span-level accuracy, and the local semantic
lane is a deterministic hashing surrogate, so the lexical-vs-dense *magnitude* of
[@sen2026grep] is not reproduced here — that requires a learned embedder, which
drops into the same interface. THALIA thus operationalises the design principles of
all four works inside one enforced, provenance-tracked pipeline built on
`docxology/template` [@aii2026template].

**Keywords:** declarative pipelines, recursive language models, agentic search,
reciprocal rank fusion, episodic memory, gated consolidation, compiler
optimization, reproducible research.
