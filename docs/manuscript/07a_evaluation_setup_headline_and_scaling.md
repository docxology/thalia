## Experimental Design and Statistical Estimands {#sec:evaluation-setup-headline-scaling}

### Synthetic Dataset and Metric Contract {#sec:eval-setup}

`src.evaluation.build_demo_dataset` defines {{RESULT_NUM_EXAMPLES}} examples,
one per task category (temporal, preference, code, multi-session, knowledge-update,
single-session). Each session embeds the gold answer in one discriminative line
plus distractors, with annotated gold source indices. The composite metric
(`src/compiler/metrics.py`) is the convex combination in [@eq:composite]:
**answer token-F1** (set-based token-F1 vs. the gold answer, weight
{{CONFIG_WEIGHT_ACC}}), **citation-support proxy** (the citation-support proxy, weight
{{CONFIG_WEIGHT_GROUND}}), and **efficiency** (a ranked-window count reward,
weight {{CONFIG_WEIGHT_EFF}}). The exact component definitions and edge cases
are specified once in [@sec:formalism].

The dataset is intentionally diagnostic and compact. It checks whether each
stage receives the right kind of pressure: the Inspector must recover a line from
history; the Retriever must rank that line under lexical, surrogate-semantic, and
hybrid modes; the Reasoner must cite it; the Memory Gate must avoid unwanted
consolidation; and the Compiler must evaluate a repeatable metric. This makes the
evaluation a methods test. The fixed examples are small
enough for every run to be inspected, and the expected source indices make
reachability failures concrete. Its labels cover expected source indices and
lexical answer strings; adjudicated quality and atomic factuality labels belong to
the separate quality protocol [@min2023factscore].

Three controls keep the protocol honest. First, every result number in this
section is generated from `src/manuscript_variables.py`. Second,
the headline comparison uses the default slack retrieval budget, while the
diagnostic sweeps state when they switch to a tight budget. Third, the local
semantic lane is always described as a hashing surrogate; learned dense retrieval
is labelled as a separate evidence tier.

### Headline Deterministic Results {#sec:eval-headline}

On the default configuration (top-k {{CONFIG_TOP_K}}, max-evidence
{{CONFIG_MAX_EVIDENCE}}, RRF $k = {{CONFIG_RRF_K}}$), the headline metric
components are reported in [@tbl:headline_results].

| Component | Value |
|-----------|-------|
| Composite | {{RESULT_COMPOSITE}} |
| Answer token-F1 | {{RESULT_ACCURACY}} |
| Citation-support proxy | {{RESULT_GROUNDING}} |
| Efficiency | {{RESULT_EFFICIENCY}} |

: Headline metric components on the {{RESULT_NUM_EXAMPLES}}-example dataset under the default configuration. {#tbl:headline_results}

Citation-support proxy ({{RESULT_GROUNDING}}) and efficiency ({{RESULT_EFFICIENCY}}) are high
on this declared finite set under their operational proxies: the harness usually
cites the expected source and uses a small evidence set. Factuality and user value
require separate adjudicated outcomes.
Answer token-F1 ({{RESULT_ACCURACY}}) is bounded because the *deterministic*
extractive LM returns a whole transcript line, such as an assistant confirmation,
while the annotation contains a minimal span. Token-F1 against the terse gold string measures lexical
agreement with the annotation. Adjudicated semantic correctness is a separate
outcome. This behaviour belongs to the selected Reasoner and metric; [@sec:eval-neural]
tests the model boundary directly while holding the other stages fixed.

### Scaling, Uncertainty, and Inferential Limits {#sec:eval-scaling}

The {{RESULT_NUM_EXAMPLES}}-example set above is a determinism showcase. To
characterize dispersion in the machinery we add a **seeded,
balanced large dataset** ({{RESULT_LARGE_N}} examples, {{RESULT_LARGE_PER_CAT}} per
task category) from `src.evaluation.build_large_dataset`: a fixed seed makes it
bit-reproducible, so scale and determinism coexist on this path. On it the
composite is {{RESULT_LARGE_COMPOSITE}} with a {{CONFIG_CI_LEVEL}}%
descriptive bootstrap interval of {{RESULT_LARGE_COMPOSITE_CI}}, and [@fig:scaling_ci] shows
per-category answer token-F1 with bootstrap intervals — the first view of the harness with
measured dispersion across category rows. The caveat is explicit: this set is
*realistic-but-synthetic* (templated entities; observational transcripts form a
separate tier), so it measures the machinery's scaling and variance. An external benchmark slice
is the natural next step. What it buys is statistical shape: the strongest and weakest
task categories show visible dispersion (the middle categories overlap). This is a
descriptive pattern with no significance estimand, and it adds structure the
{{RESULT_NUM_EXAMPLES}}-example diagnostic could only hint at.

![Answer token-F1 per task category on the seeded synthetic {{RESULT_LARGE_N}}-example dataset ({{RESULT_LARGE_PER_CAT}} per category), with {{CONFIG_CI_LEVEL}}% descriptive bootstrap intervals; the dashed line marks the mean category estimate. The unit is a generated evaluation example scored by the deterministic extractive responder. A fixed seed makes the generated-task dispersion and scaling reproducible; real-world answer quality and learned-model transfer require separate evidence.](../../output/figures/scaling_ci.png){#fig:scaling_ci width=70%}

The precision audit extends this single-seed view with {{RESULT_AUDIT_CATEGORY_COUNT}}
task categories and four balanced per-category sample sizes {{RESULT_AUDIT_SIZES}}, across {{RESULT_AUDIT_SEED_COUNT}} independent
fixed seeds: {{RESULT_AUDIT_UNIQUE_N}}
unique synthetic examples and {{RESULT_AUDIT_METHOD_N}} method evaluations. It evaluates lexical-only,
surrogate-semantic-only, and hybrid retrieval on paired examples across {{RESULT_AUDIT_STRATA_COUNT}}
deterministic difficulty strata. The audit records {{RESULT_AUDIT_INTERVAL_LABEL}} within declared strata,
seed-cluster precision checks ({{RESULT_AUDIT_CLUSTER_WARNING}}), {{RESULT_AUDIT_CONFIDENCE}}% Wilson intervals for binary outcomes,
exact paired binary tests, and one named Holm family of size {{RESULT_AUDIT_FAMILY_SIZE}} spanning every sample-size
row, overall paired comparison, and stratum-level paired comparison. A per-example ledger records {{RESULT_AUDIT_FAILURES}} failed method rows and
configuration/dataset fingerprints. This strengthens accounting for finite
synthetic variation. Generalization beyond the generated task family requires
external data.

#### Estimands, Resampling, and Paired Inference {#sec:eval-statistics}

The primary continuous estimand is the mean composite score over the finite
generated evaluation examples, with the example as the observation unit and the
seed as a design cluster. Method comparisons are paired: hybrid and each baseline
are evaluated on the same stable example IDs, and the reported delta is hybrid
minus baseline. Intervals for marginal method means resample within each declared
difficulty stratum; intervals for paired deltas resample complete seed clusters
while preserving the within-seed pairing. The paired point estimate is the mean of
the complete seed-cluster deltas, so the estimand and its interval use the same
cluster-level unit even when cluster sizes differ. The per-stratum forest
shows the comparison estimand directly. Subtracting two unrelated marginal limits
would define a different quantity. Percentile bootstrap intervals follow
the non-parametric resampling tradition of [@efron1979bootstrap].

The seed-cluster intervals are deliberately descriptive: the publication audit
uses a finite number of independent seed clusters. The manuscript reports that
design limitation; independent replication remains a separate requirement. The quality
protocol later uses question clusters for the same reason:
paired condition contrasts use the question as the observation unit, with
model/condition rows retained as paired records.

Binary probe outcomes are summarized with Wilson score intervals [@wilson1927probable]
and paired with the exact McNemar binomial test [@mcnemar1947sampling]. All named
paired tests in this audit, including the stratum slices, enter the same predeclared
Holm step-down family [@holm1979simple]; adjusted values provide descriptive
control of the declared family. The precision planner is an explicit design aid
based on observed dispersion and target half-width. Population power requires a
separate design.

These estimates belong to separate evidence tiers. The seeded examples test
composable machinery under controlled variation; {{RESULT_LME_BENCHMARK}} tests
transfer to an external benchmark; and neural rows test one recorded local
model/configuration. Each tier retains its own estimand and evidence boundary.
Synthetic descriptive intervals describe the seeded machinery tier. Neural and
external-benchmark performance require their own evidence. A reproducible harness run establishes that the measurement path is
functioning. A quality claim requires a validated target construct, appropriate
labels, and comparisons defined by the separate quality protocol.

![Composite means and paired deltas across audited synthetic sample sizes. Fixed-stratum intervals summarize method means, and paired hybrid-minus-baseline intervals respect {{RESULT_AUDIT_SEED_COUNT}} seed clusters. The horizontal axis is the ledger's total unique-example count; the banner exposes rows, method evaluations, failures, and the complete Holm family. All rows come from the same deterministic evaluation ledger. Intervals are descriptive cluster-resampling diagnostics; methods use the deterministic extractive responder and hashing surrogate.](../../output/figures/sample_size_precision.png){#fig:sample_size_precision width=100%}

![Paired composite-score effects at the largest audited synthetic row: hybrid-minus-lexical and hybrid-minus-surrogate-semantic within each difficulty stratum, with whole-seed-cluster {{RESULT_AUDIT_CONFIDENCE}}% descriptive intervals and Holm-adjusted p-values. Delta and p-value labels, the zoomed observed range, and the zero reference line expose the small effects. The accounting panel reports {{RESULT_AUDIT_SEED_COUNT}} seed clusters, {{RESULT_AUDIT_STRATA_COUNT}} strata, the resampling design, failures, and the complete family of size {{RESULT_AUDIT_FAMILY_SIZE}}. The finite extractive-plus-hashing study is a descriptive experiment; its finite cluster design limits population interpretation.](../../output/figures/statistical_audit.png){#fig:statistical_audit width=100%}

The pre-registered sensitivity extension is a separate ten-seed design from the publication audit:
it covers {{RESULT_SEED_SENSITIVITY_UNIQUE_N}} unique generated examples across
{{RESULT_SEED_SENSITIVITY_SEEDS}} seed clusters and {{RESULT_SEED_SENSITIVITY_EVALUATIONS}}
method evaluations. Hybrid-minus-lexical has mean paired delta
{{RESULT_SEED_HYBRID_LEXICAL_DELTA}} (sign-flip randomization p={{RESULT_SEED_HYBRID_LEXICAL_P}}),
and hybrid-minus-surrogate-semantic has mean paired delta
{{RESULT_SEED_HYBRID_SEMANTIC_DELTA}} (sign-flip randomization p={{RESULT_SEED_HYBRID_SEMANTIC_P}}). These are
finite generated-task sensitivity results; the small-cluster warning
{{RESULT_SEED_SENSITIVITY_WARNING}} for this extension, and neither it nor the
headline is a population estimate.
