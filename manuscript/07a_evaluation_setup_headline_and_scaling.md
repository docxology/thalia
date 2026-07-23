# Evaluation Protocol: Estimands, Headline Results, and Scaling {#sec:evaluation-setup-headline-scaling}

## Dataset and metric {#sec:eval-setup}

`src.evaluation.build_demo_dataset` defines {{RESULT_NUM_EXAMPLES}} examples,
one per task category (temporal, preference, code, multi-session, knowledge-update,
single-session). Each session embeds the gold answer in one discriminative line
plus distractors, with annotated gold source indices. The composite metric
(`src/compiler/metrics.py`) is the convex combination in [@eq:composite]:
**accuracy** (set-based token-F1 vs. the gold answer, weight
{{CONFIG_WEIGHT_ACC}}), **grounding** (the citation-support proxy, weight
{{CONFIG_WEIGHT_GROUND}}), and **efficiency** (a ranked-window count reward,
weight {{CONFIG_WEIGHT_EFF}}). The exact component definitions and edge cases
are specified once in [@sec:formalism].

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

Grounding ({{RESULT_GROUNDING}}) and efficiency ({{RESULT_EFFICIENCY}}) are high
on this declared finite set: the harness usually cites the expected source and
uses a small evidence set under the operational proxies.
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
descriptive bootstrap interval of {{RESULT_LARGE_COMPOSITE_CI}}, and [@fig:scaling_ci] shows
per-category accuracy with bootstrap intervals — the first view of the harness with
measured dispersion rather than single points. The caveat is explicit: this set is
*realistic-but-synthetic* (templated entities, not human transcripts), so it measures
the machinery's scaling and variance, not real-world accuracy — an external benchmark slice
is the natural next step. What it buys is statistical shape: the strongest and weakest
task categories show visible dispersion (the middle categories overlap); this is a
descriptive pattern, not a significance claim, and adds structure the
{{RESULT_NUM_EXAMPLES}}-example diagnostic could only hint at.

![Token-F1 accuracy per task category on the seeded synthetic {{RESULT_LARGE_N}}-example dataset ({{RESULT_LARGE_PER_CAT}} per category), with {{CONFIG_CI_LEVEL}}% descriptive bootstrap intervals; the dashed line marks the mean category estimate. The observation unit is a generated evaluation example scored by the deterministic extractive responder. Bit-reproducible via a fixed seed, this measures generated-task dispersion and scaling, not real-world accuracy or a learned-model estimate.](../output/figures/scaling_ci.png){#fig:scaling_ci width=70%}

The precision audit extends this single-seed view with {{RESULT_AUDIT_CATEGORY_COUNT}}
balanced sample sizes {{RESULT_AUDIT_SIZES}} and {{RESULT_AUDIT_SEED_COUNT}} independent
fixed seeds: {{RESULT_AUDIT_UNIQUE_N}}
unique synthetic examples and {{RESULT_AUDIT_METHOD_N}} method evaluations. It evaluates lexical-only,
surrogate-semantic-only, and hybrid retrieval on paired examples across {{RESULT_AUDIT_STRATA_COUNT}}
deterministic difficulty strata. The audit records {{RESULT_AUDIT_INTERVAL_LABEL}} within declared strata,
seed-cluster precision checks ({{RESULT_AUDIT_CLUSTER_WARNING}}), {{RESULT_AUDIT_CONFIDENCE}}% Wilson intervals for binary outcomes,
exact paired binary tests, and one named Holm family of size {{RESULT_AUDIT_FAMILY_SIZE}} spanning every sample-size
row, overall paired comparison, and stratum-level paired comparison. A per-example ledger records {{RESULT_AUDIT_FAILURES}} failed method rows and
configuration/dataset fingerprints. This is a stronger accounting layer for
synthetic variance, not a license to generalize beyond the generated task family.

### Estimands and inferential protocol {#sec:eval-statistics}

The primary continuous estimand is the mean composite score over the finite
generated evaluation examples, with the example as the observation unit and the
seed as a design cluster. Method comparisons are paired: hybrid and each baseline
are evaluated on the same stable example IDs, and the reported delta is hybrid
minus baseline. Intervals for marginal method means resample within each declared
difficulty stratum; intervals for paired deltas resample complete seed clusters
while preserving the within-seed pairing. The per-stratum forest therefore shows
the comparison estimand directly, rather than constructing an interval by
subtracting two unrelated marginal limits. Percentile bootstrap intervals follow
the non-parametric resampling tradition of [@efron1979bootstrap].

Binary probe outcomes are summarized with Wilson score intervals [@wilson1927probable]
and paired with the exact McNemar binomial test [@mcnemar1947sampling]. All named
paired tests in this audit, including the stratum slices, enter the same predeclared
Holm step-down family [@holm1979simple]; adjusted values are descriptive controls
for multiplicity, not a license to search for a favourable slice. The precision
planner is an explicit design aid based on the observed dispersion and target
half-width; it is not a power claim for a human or production population.

These estimates belong to separate evidence tiers. The seeded examples test
composable machinery under controlled variation; {{RESULT_LME_BENCHMARK}} tests transfer to
an external benchmark; and neural rows test one recorded local model/configuration.
The tiers are not pooled into a single population estimate, and no synthetic
descriptive interval is used to certify neural or external-benchmark performance.

![Multi-seed sample-size precision audit on the synthetic research grid: method means per generated example with fixed-stratum bootstrap intervals and paired hybrid-minus-baseline deltas whose uncertainty respects {{RESULT_AUDIT_SEED_COUNT}} seed clusters. The horizontal axis is the ledger's total unique-example count; the banner exposes unique examples, method evaluations, failures, and the complete Holm family. All rows are generated from the same deterministic evaluation ledger, so increasing sample size is visible together with the comparison accounting. Intervals are descriptive cluster-resampling diagnostics, not population-coverage guarantees; methods use the deterministic extractive responder and hashing surrogate.](../output/figures/sample_size_precision.png){#fig:sample_size_precision width=100%}

![Exact paired composite-score delta per generated example at the largest audited synthetic row: hybrid-minus-lexical and hybrid-minus-surrogate-semantic within each difficulty stratum, with whole-seed-cluster {{RESULT_AUDIT_CONFIDENCE}}% descriptive intervals and Holm-adjusted q-values. The accounting panel reports {{RESULT_AUDIT_SEED_COUNT}} seed clusters, {{RESULT_AUDIT_STRATA_COUNT}} strata, the resampling design, failure count, and the complete family of size {{RESULT_AUDIT_FAMILY_SIZE}}. The finite extractive-plus-hashing evaluation is not a population estimate, and the small-cluster warning limits inferential interpretation.](../output/figures/statistical_audit.png){#fig:statistical_audit width=100%}

The pre-registered sensitivity extension is separate from the five-seed headline:
it covers {{RESULT_SEED_SENSITIVITY_UNIQUE_N}} unique generated examples across
{{RESULT_SEED_SENSITIVITY_SEEDS}} seed clusters and {{RESULT_SEED_SENSITIVITY_EVALUATIONS}}
method evaluations. Hybrid-minus-lexical has mean paired delta
{{RESULT_SEED_HYBRID_LEXICAL_DELTA}} (permutation p={{RESULT_SEED_HYBRID_LEXICAL_P}}),
and hybrid-minus-surrogate-semantic has mean paired delta
{{RESULT_SEED_HYBRID_SEMANTIC_DELTA}} (p={{RESULT_SEED_HYBRID_SEMANTIC_P}}). These are
finite generated-task sensitivity results; the small-cluster warning
{{RESULT_SEED_SENSITIVITY_WARNING}} for this extension, and neither it nor the
headline is a population estimate.
