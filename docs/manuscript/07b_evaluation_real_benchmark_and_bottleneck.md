## External Benchmark Transfer and Bottleneck Diagnosis {#sec:evaluation-real-benchmark-bottleneck}

### LongMemEval_S Transfer Slice {#sec:eval-real}

Long-term conversational-memory evaluation has multiple valid target constructs.
LoCoMo evaluates very long conversations through question answering, event
summarization, and multimodal dialogue [@maharana2024locomo]; LongMemEval
organises a complementary set of information-extraction, multi-session,
temporal, knowledge-update, and abstention tasks [@wu2025longmemeval]. THALIA
uses LongMemEval_S for this transfer lane because its current adapter binds the
benchmark's labelled answer sessions to the existing evidence-window contract.
The comparison is a transfer diagnostic within that adapter; it is not a
cross-benchmark ranking.

The synthetic results test machinery on the generated task family. The transfer
check is an external benchmark. We run the harness over
**{{RESULT_LME_BENCHMARK}}** [@wu2025longmemeval] — {{RESULT_LME_N_EXT}} questions over long,
multi-session haystacks — mapped onto the same `EvalExample` contract
(`src.evaluation.longmemeval`), scored with **answer token-F1** and two separate
evidence diagnostics: a citation-support proxy for cited excerpts and binary
**session reachability** (did the surfaced evidence include a line from the gold
session?). Because the benchmark labels evidence at the session level, reachability
is an **upper bound** on stricter line-level attribution. Both diagnostics measure
exposure or citation support; entailment and adjudicated answer quality require
separate labels. This is external data, so these results are reproducible from
*code plus the downloaded benchmark*. The benchmark dependency is recorded as a
deliberate boundary of the self-contained thesis.

The external-benchmark comparison ([@fig:longmemeval]) is deliberately a transfer
diagnostic. Extractive answer token-F1 is lower in this retained slice at
{{RESULT_LME_EXT_ACC}} {{RESULT_LME_EXT_ACC_CI}} — versus the synthetic
{{RESULT_LARGE_ACCURACY}} {{RESULT_LARGE_ACCURACY_CI}} on the same token-F1
component — indicating that the synthetic construct is easier than this retained
slice and that the extractive default is below the target usefulness of this
long-context task. The result bounds answer phrasing under the selected Reasoner;
the localisation below assesses evidence reachability separately.
Three findings follow, now with recorded benchmark statistics ({{RESULT_LME_N_EXT}} questions,
{{CONFIG_CI_LEVEL}}% descriptive bootstrap intervals):

1. **A real neural model changes this retained slice.** Dropping `{{RESULT_LME_MODEL}}` into the
   Reasoner ({{RESULT_LME_N_NEURAL}} questions, the Inspector windowing first) raises
   answer token-F1 to {{RESULT_LME_NEURAL_ACC}} {{RESULT_LME_NEURAL_ACC_CI}} — a descriptive ~{{RESULT_LME_NEURAL_RATIO}}×
   point-estimate contrast. The extractive and neural rows have different retained
   sample sizes, so they form separate backend summaries. Their bootstrap
   intervals describe the retained slices and carry no interval-overlap decision
   rule. The synthetic set showed a tie ([@sec:eval-baseline]);
   this retained external-benchmark slice is harder and model-dependent.
2. **Evidence reachability is the bottleneck in this retained slice; ranking loss
   is smaller once evidence is exposed.** The citation-support proxy is {{RESULT_LME_GROUNDING}}
   {{RESULT_LME_GROUNDING_CI}}; the separate extractive session-reachability
   diagnostic is {{RESULT_LME_SESSION_REACHABILITY}}
   {{RESULT_LME_SESSION_REACHABILITY_CI}}. Answer token-F1 in this evaluation is
   constrained by what is surfaced. We expected a learned
   dense embedder to be the fix; [@sec:eval-bottleneck] shows the committed
   full-haystack ranking reaches a gold evidence line in {{RESULT_BN_RANKING_RECALL}} of
   the retained cases. In this diagnostic, the larger observed loss is upstream, in
   the Inspector's aggressive context-narrowing, and widening that window is
   associated with recovered session reachability and answer token-F1.
3. **The evidence scope.** {{RESULT_LME_NEURAL_ACC}} is a low absolute number: this
   retained run combines deterministic selection with model-dependent generation;
   the run is a THALIA transfer diagnostic. A hosted-LLM memory-system comparison
   on {{RESULT_LME_BENCHMARK}} would be a separate study. It establishes that the *machinery* runs
   on external long-token haystacks, that the
   architecture's plug-in points behave as designed under real load, and that the
   observed failures motivate improvements to context policy and answer quality.

![{{RESULT_LME_BENCHMARK}} in separate answer token-F1, citation-support-proxy, and optional session-reachability panels for the extractive and neural Reasoners, with {{CONFIG_CI_LEVEL}}% descriptive bootstrap intervals ({{RESULT_LME_N_EXT}} extractive questions, {{RESULT_LME_N_NEURAL}} neural). Retained slices have different sample sizes, so each interval summarizes its own backend observations. Session reachability is an upper-bound exposure measure because any line from the gold session counts; citation-support measures source overlap and requires separate entailment labels. Benchmark SHA-256, retained status {{RESULT_LME_BENCHMARK_STATUS}}, and model digest are recorded in `data/longmemeval_results.json`; neural values are model-dependent and carry host-specific provenance.](../output/figures/longmemeval.png){#fig:longmemeval width=70%}

### What the Transfer Test Identifies {#sec:eval-model-quality}

The external slice is the manuscript's closest approach to a model-quality
measurement. It remains a transfer diagnostic; a quality certificate requires
the separate adjudication protocol. Its answer token-F1 asks whether the answer shares normalized
tokens with the benchmark answer; its citation metric asks whether evidence
reaches the labelled session. Neither asks a quality judge whether the answer is
complete, faithful, well calibrated, or useful. Factuality evaluation decomposes
generated text into atomic claims and supplies labels for factual support
[@min2023factscore].

Citation evaluation provides a second validity boundary. ALCE's statement-level
citation recall and precision use entailment judgments over cited passages
[@gao2023alce], while ARES evaluates context relevance, answer faithfulness,
and answer relevance as distinct RAG dimensions [@saadfalcon2024ares]. The
THALIA aggregate currently records source-index precision and recall in the
campaign schema and displays their deterministic analogue in
the metric-construct-audit heatmap in the formalism section. Those measures expose citation-set behavior;
they do not replace the planned expert labels for entailment, completeness, or
usefulness.

The benchmark also separates two failure surfaces that long-context work has shown
can diverge. A model may receive the right evidence but underuse it, or retrieval
can leave relevant evidence outside the model's context [@liu2024lost].
THALIA's Inspector and Retriever diagnostics make that separation visible for the
retained slice. The interventions are local, the model is fixed within each
recorded run, and the neural rows form separate backend summaries across the
retained questions. The appropriate conclusion is conditional: the harness
identifies a plausible bottleneck and a testable intervention, while model quality
awaits stronger answer-correctness labels and broader comparators.

This is a construct-validity boundary. A quality claim needs an answer-level
target and a label protocol that
distinguishes atomic factual support from coverage, usefulness, and safe
abstention. FActScore motivates the atomic-claim distinction
[@min2023factscore]; TruthfulQA shows why truthfulness deserves an explicit
failure surface [@lin2022truthfulqa]; and SelfCheckGPT demonstrates that
black-box consistency checks are themselves a different diagnostic from
adjudication [@manakul2023selfcheckgpt]. The result is a measurement
stack: reachability asks whether relevant evidence was exposed, correctness asks
whether the answer is right, faithfulness asks whether its claims are supported,
and usefulness asks whether it serves the task. A single lexical-overlap number
identifies one construct within this stack. This multi-faceted design also follows
long-form QA evaluation work showing that automatic metrics require answer-level
judgments of properties such as comprehensiveness
[@xu2023lfqaeval].

### Expert-Rated Quality Gate {#sec:eval-quality-protocol}

The repository now specifies the quality study as a separate lane. The quality
protocol keeps an exploratory,
question-type-stratified pilot separate from the held-out confirmatory set. After
pilot review, the rubric, primary adjudicated correctness estimand, thresholds,
missing-data rules, safety criteria, and confirmatory question identifiers are
frozen in the experiment-plan source of truth.

The live matrix compares Gemma and Hermes under the default THALIA harness, a
no-harness full-context baseline, and an oracle-evidence baseline. The latter
exposes the labelled evidence session without adding a gold answer field, so
evidence exposure remains distinct from answer quality. Each output is retained
with its raw answer, citations, evidence indices, confidence response, latency,
failure state, model digest, generation options, configuration fingerprint, and
code fingerprint outside the repository. Publication annotations use two
independent expert raters who receive packets with model and condition identifiers
removed; a blinded expert adjudicator resolves disagreements before a row enters
analysis.

The repository also contains a pinned local-LLM judging implementation (Qwen and
Llama evaluators with a separate Phi adjudicator) for engineering diagnostics of
packet construction, rubric parsing, and resumable evidence accounting. Those
labels are explicitly exploratory: they estimate behavior under a specified
judge stack. The promotion function excludes these labels from publication. The
publication certificate therefore requires the expert-human mode, with
the rater and adjudicator identities recorded as pseudonymous identifiers and the
annotation ledgers bound by digest. All judge packets remove target model and
condition identifiers, use the same condition-neutral question and source packet
for every paired output, and keep analyst citations/source indices separate from
the blinded presentation. This separation makes the faithfulness label a claim
about support by supplied source material. The exploratory LLM implementation also records evaluator/model and
prompt digests because LLM-as-judge results can exhibit self-enhancement,
verbosity, and position biases [@zheng2023judging; @wang2024fairevaluators;
@shi2025judges].

The planned analysis treats adjudicated correctness as the primary outcome and completeness,
faithfulness, usefulness, abstention, critical safety failures, calibration,
latency, and failure rate as secondary outcomes. It reports question-clustered
paired uncertainty, exact paired binary contrasts, question-type strata, and
weighted inter-rater agreement. FActScore's atomic-claim distinction motivates
keeping faithfulness and correctness explicit; token overlap remains a lexical
proxy [@min2023factscore], while long-context evidence exposure remains a
separate construct [@liu2024lost]. Until the study is annotated, adjudicated,
thresholded, and explicitly accepted, no quality aggregate is promoted and the
manuscript reports no model-quality pass. Production readiness remains a
separate operational gate for latency, cost, privacy, rollback, monitoring, drift,
and red-team evidence.

The rubric uses ordinal scores with three levels. For each answer,
each rater assigns correctness, completeness, evidence faithfulness, and usefulness
as $0$ (incorrect, absent, or unusable), $1$ (partly correct, incomplete, weakly
supported, or conditionally useful), or $2$ (fully correct, complete for the stated
task, supported, or useful as applicable). Abstention appropriateness and critical
safety failure are binary outcomes. Independently, every deterministic atomic claim
is labelled `supported`, `unsupported`, `uncertain`, or `not_applicable`; the last
label is excluded from the support-rate denominator. This keeps an unsupported
factual assertion visible alongside a high answer score. The citation-overlap
proxy continues to require separate entailment labels.

The confirmatory primary estimand is explicit. Let $Q_C$ be the {{RESULT_QUALITY_CONFIRMATORY_N}} held-out
questions, $H_q$ the adjudicated default-harness answer for question $q$, and
$Y_q = \mathbb{1}[H_q\text{ receives correctness }2]$. The primary estimate is

\begin{equation}
\label{eq:quality-primary}
\widehat{\theta}_{\mathrm{correct}} = |Q_C|^{-1}\sum_{q\in Q_C}Y_q.
\end{equation}

with a Wilson interval for the descriptive rate; baseline contrasts pair the same
question under the no-harness and oracle-evidence conditions and use question-level
clustered bootstrap intervals plus exact paired binary tests. A failed generation,
missing confidence response, missing judge label, missing adjudication, digest
mismatch, pilot leakage, or incomplete condition pair invalidates the affected
report and remains un-imputed. A complete run that misses a frozen threshold
remains in the explicit `complete_not_promoted` state. Artifact generation
preserves that state.

The planned matrix contains {{RESULT_QUALITY_CONDITIONS}} model/condition rows
across {{RESULT_QUALITY_TOTAL_N}} benchmark questions: an exploratory pilot of
{{RESULT_QUALITY_PILOT_N}} questions, followed by a held-out confirmatory set of
{{RESULT_QUALITY_CONFIRMATORY_N}}. Every output is independently labelled by
{{RESULT_QUALITY_RATERS}} blinded expert raters before expert adjudication.
Confidence is
treated as a forecast to be assessed against adjudicated correctness: Brier score,
expected calibration error, reliability curves, and selective accuracy follow the
calibration and risk--coverage framing in [@guo2017calibration; @geifman2017selective].
Agreement statistics are reported as reliability diagnostics. Agreement measures
label consistency; construct validity requires additional evidence
[@artstein2008agreement].
The primary outcome is the frozen protocol's `{{RESULT_QUALITY_PRIMARY}}` on the
confirmatory set. Pilot labels may revise the rubric and remain outside that
estimate.

![Planned model-quality protocol. Gemma and Hermes outputs cross the THALIA default harness, full-context baseline, and oracle-evidence baseline before a stratified exploratory pilot, rubric freeze, two blinded expert-rater passes, adjudication, and a fail-closed certificate. The pilot contains {{RESULT_QUALITY_PILOT_N}} questions and remains outside the {{RESULT_QUALITY_CONFIRMATORY_N}}-question confirmatory estimand; the oracle condition provides evidence while withholding the gold answer. The local-LLM implementation is an engineering diagnostic. The protocol schematic carries no observed quality result, and production readiness has an independent gate.](../output/figures/quality_protocol.png){#fig:quality_protocol width=90%}

### Context-Narrowing Bottleneck {#sec:eval-bottleneck}

The sharp decline in [@sec:eval-real] motivates a diagnostic comparison — swap the lexical lane for a
learned dense retriever. The committed aggregate is narrower: over {{RESULT_BN_N}}
questions, full-haystack ranking hit@10 is {{RESULT_BN_RANKING_RECALL}}, while the
optional per-mode learned-embedder probe is only cited when
`ranking_recall_by_mode.available` is true in the regenerated bottleneck artifact. On
{{RESULT_LME_BENCHMARK}}, retrieval *ranking* contributes less to the observed loss in the retained aggregate.
The loss is upstream in this retained slice: over {{RESULT_BN_N}} questions, full-haystack
ranking recall is {{RESULT_BN_RANKING_RECALL}} while the **Inspector's** window recall —
whether its grep-based narrowing even surfaces a gold line for the Retriever to rank —
is only {{RESULT_BN_INSPECTOR_RECALL}}. In this slice, the RLM-style narrowing
accounts for the larger observed loss before ranking can operate. This is a
retained-slice bottleneck diagnosis; causal ranking claims require an intervention.

So the fix is to relax the narrowing, and [@fig:bottleneck] measures it. Raising the
Inspector's `max_windows` from {{RESULT_BN_MAXWIN_LO}} to {{RESULT_BN_MAXWIN_HI}} lifts
the citation-support proxy from {{RESULT_BN_GROUNDING_LO}} to {{RESULT_BN_GROUNDING_HI}} — but
extractive *answer token-F1* barely moves, consistent with the default extractive responder's
answer-generation limitation even when evidence is shown. The two interventions
compose in this retained subset: with a real Reasoner
(`{{RESULT_BN_MODEL}}`), the same widening converts recovered recall into answer token-F1,
**raising it ~{{RESULT_BN_NEURAL_RATIO}}×, from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_NEURAL_ACC_HI}}**.
(This analysis uses a {{RESULT_BN_N_NEURAL}}-question neural subset, so its absolute
values sit slightly below the {{RESULT_LME_N_NEURAL}}-question headline of
[@sec:eval-real]; the *relative* gain from relaxing the narrowing is the claim.)
The actionable result is bounded: THALIA's default `max_windows={{CONFIG_MAX_WINDOWS}}`
is tuned for compact contexts and produced the largest observed loss in this retained
long-context diagnostic slice;
widening the Inspector *and* using a neural Reasoner is the configuration associated
with higher scores in this retained benchmark slice. The *surrogate* semantic lane
left recall unchanged here. A learned dense embedder remains the appropriate tool
for paraphrase coverage ([@sec:eval-learned]). The finding is a localized
context-narrowing bottleneck supported by this retained slice.

The diagnosis yields an operational fix: the narrowing budget should *scale with
the haystack*. This ships as an **adaptive Inspector**
(`adaptive_windows`, opt-in, `src/stages/inspector.py`): it sets `max_windows` to
roughly one window per {{CONFIG_ADAPTIVE_RATIO}} session lines, floored at the
compact-context default. On
the {{RESULT_NUM_EXAMPLES}}-example synthetic set this leaves every output
**bit-for-bit unchanged** because compact contexts stay below the floor. On
{{RESULT_LME_BENCHMARK}} the fixed adaptive policy is associated
with the observed recall in this retained slice,
lifting observed neural answer token-F1 from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_ADAPTIVE_ACC}}:
the manually selected `max_windows={{RESULT_BN_MAXWIN_HI}}` result ([@fig:bottleneck], star);
the adaptive policy reaches its own observed value while retaining its ratio-based
rule; the sweep maximum is not an input. The diagnosis becomes a one-flag method.

![{{RESULT_LME_BENCHMARK}} bottleneck diagnostic on {{RESULT_BN_N}} ranking/configuration observations and {{RESULT_BN_ACCOUNTING_NEURAL_N}} neural question-configuration rows ({{RESULT_BN_N_NEURAL}} questions per neural sweep setting). Separate small multiples show session reachability, citation-support proxy, and neural answer token-F1 during the Inspector `max_windows` sweep; the star marks the opt-in adaptive policy. Full-haystack ranking recall is {{RESULT_BN_RANKING_RECALL}} and Inspector window recall is {{RESULT_BN_INSPECTOR_RECALL}}. The unit is a benchmark question or declared configuration observation; intervals are descriptive where shown, model values depend on `{{RESULT_BN_MODEL}}`, and the retained-slice diagnosis localizes the observed loss to context narrowing.](../output/figures/bottleneck.png){#fig:bottleneck width=70%}
