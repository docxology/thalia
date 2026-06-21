# Evaluation: Setup, Headline Results, and Scaling {#sec:evaluation-setup-headline-scaling}

## Dataset and metric {#sec:eval-setup}

`src.evaluation.build_demo_dataset` defines {{RESULT_NUM_EXAMPLES}} examples,
one per task category (temporal, preference, code, multi-session, knowledge-update,
single-session). Each session embeds the gold answer in one discriminative line
plus distractors, with annotated gold source indices. The composite metric
(`src/compiler/metrics.py`) is a convex combination of **accuracy** (token-F1 vs.
gold answer, weight {{CONFIG_WEIGHT_ACC}}), **grounding** (cited the expected source and is supported
by the cited excerpts, weight {{CONFIG_WEIGHT_GROUND}}), and **efficiency** (fewer evidence windows for
the same answer, weight {{CONFIG_WEIGHT_EFF}}):

\begin{equation}
\label{eq:composite}
M = {{CONFIG_WEIGHT_ACC}}\,\mathrm{acc} + {{CONFIG_WEIGHT_GROUND}}\,\mathrm{ground} + {{CONFIG_WEIGHT_EFF}}\,\mathrm{eff},
\qquad
\mathrm{eff} = \max\!\left(0,\; 1 - \tfrac{|\text{ranked}|}{{{CONFIG_EFFICIENCY_SCALE}}}\right).
\end{equation}

The dataset is intentionally diagnostic rather than large. It checks whether each
stage receives the right kind of pressure: the Inspector must recover a line from
history; the Retriever must rank that line under lexical, surrogate-semantic, and
hybrid modes; the Reasoner must cite it; the Memory Gate must avoid unwanted
consolidation; and the Compiler must evaluate a repeatable metric. This makes the
evaluation a methods test, not a population estimate. The fixed examples are small
enough for every run to be inspected, and the expected source indices make
grounding failures concrete instead of rhetorical.

Three controls keep the protocol honest. First, every result number in this
section is generated from `src/manuscript_variables.py`, not hand-entered. Second,
the headline comparison uses the default slack retrieval budget, while the
diagnostic sweeps state when they switch to a tight budget. Third, the local
semantic lane is always described as a hashing surrogate; the experiment never
uses the word "dense" for that lane without the surrogate caveat.

## Headline results {#sec:eval-headline}

On the default configuration (top-k {{CONFIG_TOP_K}}, max-evidence
{{CONFIG_MAX_EVIDENCE}}, RRF $k = {{CONFIG_RRF_K}}$), the headline metric
components are reported in [@tbl:headline_results].

| Component | Value |
|-----------|-------|
| Composite | {{RESULT_COMPOSITE}} |
| Accuracy (token-F1) | {{RESULT_ACCURACY}} |
| Grounding | {{RESULT_GROUNDING}} |
| Efficiency | {{RESULT_EFFICIENCY}} |

: Headline metric components on the {{RESULT_NUM_EXAMPLES}}-example dataset under the default configuration. {#tbl:headline_results}

Grounding ({{RESULT_GROUNDING}}) and efficiency ({{RESULT_EFFICIENCY}}) are high:
the harness reliably cites the expected source and uses a small evidence set.
Accuracy ({{RESULT_ACCURACY}}) is moderate because the *deterministic* extractive
LM returns a whole transcript line (e.g. an assistant confirmation) rather than a
minimal span — token-F1 against the terse gold string is therefore bounded. This is
a property of the LM, not the pipeline: [@sec:eval-neural] measures it directly by
dropping a real neural model into the Reasoner slot and holding every other stage
fixed.

## Scaling and variance {#sec:eval-scaling}

The {{RESULT_NUM_EXAMPLES}}-example set above is a determinism showcase, but it
supports no statistics. To put error bars on the machinery we add a **seeded,
balanced large dataset** ({{RESULT_LARGE_N}} examples, {{RESULT_LARGE_PER_CAT}} per
task category) from `src.evaluation.build_large_dataset`: a fixed seed makes it
bit-reproducible, so "larger" costs nothing in determinism — the determinism-vs-scale
tension is only apparent. On it the composite is {{RESULT_LARGE_COMPOSITE}} with a {{CONFIG_CI_LEVEL}}%
bootstrap CI of {{RESULT_LARGE_COMPOSITE_CI}}, and [@fig:scaling_ci] shows
per-category accuracy with bootstrap intervals — the first view of the harness with
real dispersion rather than single points. The caveat is explicit: this set is
*realistic-but-synthetic* (templated entities, not human transcripts), so it measures
the machinery's scaling and variance, not real-world accuracy — a real benchmark slice
is the natural next step. What it buys is statistical shape: the strongest and weakest
task categories separate outside their confidence intervals (the middle categories
overlap), confirming structure the {{RESULT_NUM_EXAMPLES}}-example diagnostic could only
hint at.

![Per-task-category accuracy on the seeded {{RESULT_LARGE_N}}-example dataset ({{RESULT_LARGE_PER_CAT}} per category) with {{CONFIG_CI_LEVEL}}% bootstrap confidence intervals; the dashed line marks mean category accuracy on the same axis. Realistic-but-synthetic, bit-reproducible via a fixed seed — variance and scaling, not a real-world accuracy claim.](../output/figures/scaling_ci.png){#fig:scaling_ci width=70%}
