## Compiler Search, Method Diagnostics, and Synthesis {#sec:evaluation-compiler-added-methods-summary}

### Bounded Compiler Search {#sec:eval-compiler}

[@fig:compiler_convergence] shows the MIPRO-style search over
{{RESULT_NUM_CANDIDATES}} candidate configurations. Every candidate reaches the
same composite to full floating-point precision: {{RESULT_COMPILED_SCORE}}. The
answer token-F1, citation-support, and efficiency components are bit-identical
across the search trace. The equality follows from the data and metric contract:
each configuration retrieves the same gold spans, and the compact dataset produces
only a few evidence windows, below every candidate's `max_evidence` cap. The three
components therefore remain constant across retrieval depths.

The reported configuration, top-k {{RESULT_COMPILED_TOP_K}} and max-evidence
{{RESULT_COMPILED_MAX_EVIDENCE}}, is the first configuration reaching the shared
maximum under the deterministic tie rule. This result describes selection under an
equal score. The GEPA-style optimizer reaches the same plateau through reflective
mutation, and its full trace is recorded for audit. A harder distribution with
competitive evidence windows supplies the conditions under which retrieval depth
can change the score; the tight-budget ablation and MMR sweep provide local
examples of that regime.

#### Held-Out Compiler Generalization {#sec:eval-compiler-generalization}

The compiler claim is tested separately from the easy in-sample trace. Across
{{RESULT_COMPILER_SEEDS}} fixed generated-task seeds, each split contains
{{RESULT_COMPILER_TRAIN_N}} training and {{RESULT_COMPILER_HOLDOUT_N}} held-out
examples. The held-out composite means are:

| method | held-out composite | delta vs. baseline |
|:--|--:|--:|
| baseline | {{RESULT_COMPILER_BASELINE_HOLDOUT}} | — |
| MIPRO-style | {{RESULT_COMPILER_MIPRO_HOLDOUT}} | {{RESULT_COMPILER_MIPRO_DELTA}} |
| GEPA-style | {{RESULT_COMPILER_GEPA_HOLDOUT}} | {{RESULT_COMPILER_GEPA_DELTA}} |

The aggregate accounts for {{RESULT_COMPILER_ACCOUNTED_N}} executed example
evaluations, including {{RESULT_COMPILER_CANDIDATE_N}} candidate configurations
evaluated on training data alongside the final holdout scores. The small observed
MIPRO-style held-out change and the GEPA-style null result are finite
generated-task observations. They characterize this seeded split family;
generalization to an external benchmark or production workload requires a
separately sampled evaluation.

Two further diagnostics close the section. The RRF lane-weight sweep
([@fig:rrf_sensitivity]) records a non-monotonic dip near the balanced midpoint
under the *tight* budget; every weight remains tied under the slack default. The
consolidation curves ([@fig:consolidation]) provide a mechanism schematic for the
memory-fault discussion in [@zhang2026memory]. They encode the design expectation
that forced per-turn consolidation can degrade utility as memory accumulates and
that episodic-first gating can preserve a useful baseline. The schematic carries
no observed memory trajectory.

![MIPRO-style compiler trace for {{RESULT_NUM_CANDIDATES}} candidate configurations on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo. The observation unit is a candidate configuration; each candidate reaches composite {{RESULT_COMPILED_SCORE}}, and the inset shows the constant weighted answer token-F1, citation-support, and efficiency components. The selected top-k {{RESULT_COMPILED_TOP_K}} and max-evidence {{RESULT_COMPILED_MAX_EVIDENCE}} follow the deterministic first-achieving tie rule. The trace is a finite project-source diagnostic.](../../output/figures/compiler_convergence.png){#fig:compiler_convergence width=70%}

The GEPA-style optimizer is designed to move when a harder distribution exposes a
weak component: it reflects on that component and mutates accordingly.
[@fig:gepa_trajectory] shows the reflective run. Each iteration plots answer
token-F1, citation support, efficiency, and the composite; the open halo marks the
component identified as weakest at that step and targeted by the next bounded
mutation. The composite plateaus on the easy set while the component trace records
the optimizer's decision path. Readers can inspect the mutation strategy directly
in the generated trace and its provenance fields.

![GEPA-style component trajectory over a deterministic compiler run on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo. The observation unit is an optimizer iteration; solid lines show answer token-F1, citation support, and efficiency, the dashed line shows the composite, and the open halo marks the weakest component selected for the next bounded mutation. The trace records an algorithmic decision path and carries no sampling estimate.](../../output/figures/gepa_trajectory.png){#fig:gepa_trajectory width=70%}

![Weighted RRF sensitivity on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo under the tight retrieval budget. The observation unit is a tested lexical weight; the line reports composite score across the feasible weight sweep, with the highest tied settings and the change from the maximum annotated. The slack default budget yields a flat score because every setting retains the same gold evidence. This finite deterministic sweep describes budget-conditioned ranking behaviour.](../../output/figures/rrf_sensitivity.png){#fig:rrf_sensitivity width=70%}

![Mechanism schematic for memory utility across turns. The curves encode the design expectation that forced per-turn consolidation can accumulate harmful derived memory while episodic-first gating preserves a useful trajectory. Values are illustrative indices tied to the mechanism discussion in [@zhang2026memory]; the panel contains no observed trajectory, sample, model estimate, or population estimand.](../../output/figures/consolidation_curve.png){#fig:consolidation width=70%}

### Added-Method Diagnostics {#sec:eval-added}

Four further figures characterise the pipeline and the added methods. The
**evidence funnel** ([@fig:evidence_funnel]) quantifies the narrowing from raw
session lines through Inspector windows and ranked evidence to cited sources. The
**per-category breakdown** ([@fig:category_breakdown]) locates composite variation
across the {{CONFIG_NUM_CATEGORIES}} task classes. The **noise-scaling** curves
([@fig:noise_scaling]) plot each lane's composite as distractor lines accumulate;
under the default RRF weights, hybrid and lexical traces coincide in this finite
probe. The dashed hybrid trace remains visible above the lexical trace in the
rendered figure and the value table records the equality. The **MMR tradeoff**
([@fig:mmr_tradeoff]) sweeps $\lambda$ in [@eq:mmr] from pure diversity to pure
relevance under the same tight retrieval budget
(`top_k={{CONFIG_TIGHT_TOP_K}}`, `max_evidence={{CONFIG_TIGHT_MAX_EVIDENCE}}`) as
the ablation and noise study. The pure-diversity endpoint receives a selection
penalty because dissimilarity can evict the discriminative span from the retained
evidence; the curve reaches its plateau once relevance receives a positive weight.
The slack budget supplies the flat reference regime.

![Evidence narrowing funnel for the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo. The observation unit is a query; bars show mean line counts at raw session, Inspector-window, ranked-evidence, and cited-source boundaries, while annotations report Inspector and citation retention. The panel measures context narrowing and source exposure; answer quality uses the separate token-F1 and support estimands.](../../output/figures/evidence_funnel.png){#fig:evidence_funnel width=70%}

The funnel is a mean view. [@fig:pipeline_flow] shows the per-example evidence
path for the {{RESULT_NUM_EXAMPLES}} demo examples, one per task category, with
counts at Inspector windows, Retriever-ranked evidence, and Reasoner-cited
sources. Each bar triplet exposes the exact transition contributing to the funnel
means. A matched ranked and cited count indicates full source selection for that
example; a lower cited count identifies a concrete support gap for inspection.

![Per-example evidence path across pipeline stages for the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo. The observation unit is an example: blue bars show Inspector windows, green bars show hybrid ranked evidence, and pink bars show Reasoner citations for each task category. The annotation reports citation retention and marks ranked-to-cited gaps. The panel is a deterministic source-exposure diagnostic.](../../output/figures/pipeline_flow.png){#fig:pipeline_flow width=70%}

![Composite score by task category for the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo, with one example per category. Each bar is the declared weighted combination of answer token-F1, citation-support, and evidence-count efficiency. The observation unit is a generated example and the panel is a deterministic diagnostic of category-specific failure modes.](../../output/figures/category_breakdown.png){#fig:category_breakdown width=70%}

The composite is a sum of three declared components. [@fig:category_components]
decomposes each category into the weighted answer token-F1, citation-support, and
efficiency terms defined in [@eq:composite]. The code and multi-session categories
carry the lowest answer-token-F1 component in this extractive-LM run; the support
and efficiency contributions remain separately visible. The pattern is consistent
with the answer ceiling documented in [@sec:eval-neural] and identifies the
component that a stronger generator would need to change.

![Weighted component audit by category for the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo. Stacks show {{CONFIG_WEIGHT_ACC}}·answer token-F1 in blue, {{CONFIG_WEIGHT_GROUND}}·citation-support proxy in green, and {{CONFIG_WEIGHT_EFF}}·evidence-count efficiency in pink; their sum equals the composite in [@eq:composite]. The observation unit is a generated example, and the extractive responder bounds the answer token-F1 component.](../../output/figures/category_components.png){#fig:category_components width=70%}

![Composite score by retrieval lane and distractor level on the fixed synthetic demo. Lexical false-friend lines are appended under the tight budget (`top_k={{CONFIG_TIGHT_TOP_K}}`, `max_evidence={{CONFIG_TIGHT_MAX_EVIDENCE}}`); the observation unit is an example-level score aggregated across the six demo cases. The semantic trace uses the deterministic hashing surrogate, so the ordering describes this finite mechanical probe and its recorded budget regime.](../../output/figures/noise_scaling.png){#fig:noise_scaling width=70%}

![MMR composite across the full diversity-to-relevance lambda sweep on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo under the tight retrieval budget. The observation unit is a tested lambda setting; the pure-diversity endpoint carries the measured selection penalty, and the curve reaches its plateau as relevance receives weight. The slack budget supplies the flat reference regime.](../../output/figures/mmr_tradeoff.png){#fig:mmr_tradeoff width=70%}

### Added-Method Ablations {#sec:eval-ablation}

[@fig:method_ablation] reports the composite for the base pipeline and each added
retrieval method (query expansion, recency weighting, MMR), plus the combined
configuration, on the single-turn dataset. The ablation uses the same *tight*
retrieval budget (`top_k={{CONFIG_TIGHT_TOP_K}}`,
`max_evidence={{CONFIG_TIGHT_MAX_EVIDENCE}}`) as the MMR sweep and noise study.
The loose default budget retrieves every gold span for every condition, producing
the expected equality reference. The tight budget creates a selection contest in
which each method can change the evidence that survives.

The experiment keeps the generated dataset and scoring rule fixed. Recency
weighting has the highest observed composite in this finite run because recency
promotes the discriminative span into the surviving evidence. Query expansion is
mildly lower as extra terms dilute an already precise query, and MMR is close to
the base configuration on this small set. Memory recall uses a separate populated
episodic-store contract; recall and harness tests exercise a fact held only in the
episodic store and verify its appearance in answer citations.

![Added-method ablation on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo under the tight retrieval budget. The observation unit is a configuration; bars show composite for the base pipeline, query expansion, recency weighting, MMR, and the combined setting. Recency weighting is highest in this run, expansion is lower, and MMR is near the base. The extractive responder and hashing surrogate define the evidence tier.](../../output/figures/method_ablation.png){#fig:method_ablation width=70%}

### Integrity-Advantage Screen: Current Findings and Open Tests {#sec:eval-integrity-advantage}

The integrity screen ranks endpoint-specific comparisons by claimability. Positive
effects use the declared direction of each endpoint, and the source rows retain
their native units. Binary probe effects use exact paired McNemar tests with Wilson
intervals for the two condition rates and paired bootstrap intervals for the rate
differences. The compiler comparison resamples seed
clusters. The neural comparison uses its recorded paired aggregate. Aggregate
comparisons without matched rows remain point estimates.

![Endpoint-level integrity-advantage screen. The observation units remain separate: binary probe effects use direction-normalized rate differences; continuous panels retain composite, token-F1, and context-policy units. Filled markers show recorded intervals, open markers show point-only aggregates, and the lower panel retains the two condition rates with Wilson intervals. Positive effects favor the left condition. Rows are not pooled. The legacy injection “auditability” row is a lexical cited-excerpt/source-exposure proxy, not a source-record-recovery or claim-level-auditability test; raw and exploratory-Holm paired p-values are displayed where available.](../../output/figures/integrity_advantage_audit.png){#fig:integrity_advantage_audit width=100%}

The strongest current screen row is the legacy lexical cited-excerpt/source-exposure
proxy under the recorded injection probes. THALIA's cited excerpts contain the
supplied gold value on every one of the {{RESULT_INTEGRITY_AUDIT_N}} probes,
giving a direction-normalized paired rate difference of
{{RESULT_INTEGRITY_AUDIT_DELTA}}, raw exact $p={{RESULT_INTEGRITY_AUDIT_P}}$, and
exploratory Holm-adjusted $p={{RESULT_INTEGRITY_AUDIT_ADJ_P}}$; the paired bootstrap
interval is {{RESULT_INTEGRITY_AUDIT_CI}}. The naive baseline emits no cited
excerpts in this comparison. This finite lexical contrast does not demonstrate
source-record recovery, citation entailment, claim-level auditability, or answer
quality.

The same probes show no poisoning-rate advantage: the direction-normalized
poisoning effect is {{RESULT_INTEGRITY_POISON_DELTA}} because both conditions
record the same poisoned count; raw exact $p={{RESULT_INTEGRITY_POISON_P}}$,
exploratory Holm-adjusted $p={{RESULT_INTEGRITY_POISON_ADJ_P}}$, and the paired
bootstrap interval is {{RESULT_INTEGRITY_POISON_CI}}.
The composite baseline comparison supplies a separate,
conditional orchestration result. Its lift is {{RESULT_INTEGRITY_COMPOSITE_LIFT}}
while raw answer token-F1 ties; citation support and evidence efficiency supply
the lift. The composite therefore measures the declared evidence-and-efficiency
utility function rather than a general answer-quality gain.

Three results are promising research leads. The learned embedder improves
paraphrase recall by {{RESULT_INTEGRITY_LEARNED_DELTA}} on the paired probe set,
with raw exact $p={{RESULT_INTEGRITY_LEARNED_P}}$, exploratory Holm-adjusted
$p={{RESULT_INTEGRITY_LEARNED_ADJ_P}}$, and paired bootstrap interval
{{RESULT_INTEGRITY_LEARNED_CI}}. The adaptive context policy
improves the recorded external-slice aggregate by {{RESULT_INTEGRITY_ADAPTIVE_DELTA}}
across {{RESULT_INTEGRITY_ADAPTIVE_N}} retained questions, but the source
aggregate lacks paired question-level rows. The MIPRO-style held-out change is
{{RESULT_INTEGRITY_COMPILER_DELTA}} with a descriptive cluster interval of
{{RESULT_INTEGRITY_COMPILER_CI}}, raw sign-flip $p={{RESULT_INTEGRITY_COMPILER_P}}$,
and exploratory Holm-adjusted $p={{RESULT_INTEGRITY_COMPILER_ADJ_P}}$ across
{{RESULT_COMPILER_SEEDS}} seed clusters. These results motivate replication; they do not yet
support promoted general advantages.

The local neural comparison provides a negative control for broad answer claims:
the neural-minus-extractive token-F1 effect is {{RESULT_INTEGRITY_NEURAL_DELTA}},
with interval {{RESULT_INTEGRITY_NEURAL_CI}}, raw $p={{RESULT_INTEGRITY_NEURAL_P}}$,
and exploratory Holm-adjusted $p={{RESULT_INTEGRITY_NEURAL_ADJ_P}}$. The interval
spans zero. Current evidence therefore records a finite lexical source-exposure
contrast and a conditional composite lift. General answer quality, a
poisoning-rate advantage, model superiority, and population-level performance
remain unestablished.

### Discussion: Findings, Contributions, and Evidence Boundaries {#sec:eval-summary}

This study evaluates THALIA as a research instrument across deterministic, neural,
and external-benchmark tiers. Five findings organize the discussion.

- **Contract integrity.** The typed stage graph, append-before-consolidate memory
  rule, formal anchors, generated variables, and artifact checks execute as one
  reproducible path. The deterministic contract is tested on
  {{RESULT_NUM_EXAMPLES}} examples across all task categories.
- **Controlled diagnostics localize failure.** The deterministic tier records
  citation-support and efficiency by retrieval lane, noise-scaling behavior,
  added-method responses, and compiler traces. Tight budgets create observable
  selection differences; the slack budget supplies an equality reference. The
  metric-construct audit separates answer token-F1, the blended support proxy,
  source-index precision/recall, reachability, and efficiency.
- **Model transfer changes the outcome.** The local backend comparison and the
  external {{RESULT_LME_BENCHMARK}} slice show model dependence. The extractive LM
  bounds token-F1 in the deterministic lane, while the neural backend changes
  answer behavior under recorded host and model settings.
- **The clearest current difference is lexical cited-excerpt/source exposure.** The
  integrity screen shows that the recorded cited excerpts contain the supplied gold
  value under the injection probes, while the poisoning endpoint remains equal
  across conditions. This is not true-source recovery or claim-level auditability.
  The composite baseline lift is conditional on citation support and evidence
  efficiency; raw answer token-F1 ties. Answer quality and a poisoning-rate
  advantage remain open questions.
- **Context narrowing is an intervention surface.** The bottleneck study links
  the retained loss to Inspector recall. In the retained slice, ranking recall is
  {{RESULT_BN_RANKING_RECALL}} and Inspector recall is
  {{RESULT_BN_INSPECTOR_RECALL}}; the adaptive context policy changes neural answer
  token-F1 from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_ADAPTIVE_ACC}} while
  compact-context outputs remain unchanged. This result motivates controlled
  context-policy experiments under fixed generators and retrieval contracts.

The important contribution is a reusable, source-bound measurement boundary. A
typed, lexically anchored, episodic-first, compiler-assisted pipeline preserves
raw evidence, records its transformations, and exposes model and embedding
interfaces for targeted experiments. The package therefore supports reproducible
method comparison and failure localization within the declared tiers.

The promising extensions are broader task families, learned retrieval, stronger
generators, and preregistered interventions over context budgets and memory gates.
The current implementation supplies stable contracts for those comparisons. The
answer-level labels needed to rank general model quality remain unmeasured.

#### Model Quality, Causal Robustness, and Production Readiness Require Separate Evidence {#sec:eval-instrument-vs-model}

The deterministic tier measures execution, lexical overlap, source exposure, and
context access. Source-index precision and recall measure declared citation-set
alignment. Sentence-level entailment, factual completeness, usefulness,
calibration, abstention, safety, causal robustness, and production reliability
remain unmeasured by these observables.

The typed quality protocol specifies the missing evidence: a prespecified target,
stronger baselines, held-out questions, two blinded expert ratings, adjudication,
atomic-claim support labels, calibration and agreement analysis, and a fail-closed
certificate. The production protocol separately evaluates latency, cost, failures,
privacy, model pinning, rollback, monitoring, drift, and red-team coverage.
Neither certificate is present in the current result layer.

This separation gives the manuscript a clear forward path. Researchers can keep
the contracts fixed while varying models, embeddings, context policies, and memory
gates, then attach the appropriate expert and operational acceptance records. The
present evidence establishes an auditable instrument and localized diagnostics;
broader quality and production claims remain open studies.
