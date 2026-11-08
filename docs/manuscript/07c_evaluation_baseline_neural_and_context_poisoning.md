## Baselines, Model Dependence, and Context-Poisoning Stress Tests {#sec:evaluation-baseline-neural-context-poisoning}

### No-Harness Full-Context Baseline {#sec:eval-baseline}

A fair challenge asks what the {{CONFIG_NUM_STAGES}}-stage pipeline adds to a naive
full-context baseline. The baseline passes the *entire* session to the LM and
omits Inspector windowing, Retriever ranking, and citations. [@fig:orchestration_value]
decomposes both conditions.
On raw answer token-F1 they *tie* exactly ({{RESULT_NAIVE_ACCURACY}} each): on this compact
set the extractive LM retrieves the gold line under the declared token-overlap rule
under both context conditions, so answer token-F1 is equal. The naive baseline earns zero citation support
(it cites nothing) and zero efficiency (it dumps the full context), so its composite
is only {{RESULT_NAIVE_COMPOSITE}} against the pipeline's {{RESULT_COMPOSITE}} — a
lift of {{RESULT_ORCHESTRATION_LIFT}} supplied by citation support and efficiency.
On this dataset the pipeline's measured value is provenance and bounded context;
raw answer token-F1 remains bounded by the selected LM ([@sec:eval-neural]).

![Weighted composite components for the naive full-context baseline and typed pipeline on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo. Answer token-F1 is equal; the composite difference comes from citation support and evidence-count efficiency. Stacked bars reproduce the declared metric. The comparison is deterministic and finite; causal and population interpretations require a separate design.](../../output/figures/orchestration_value.png){#fig:orchestration_value width=60%}

The composite weights themselves are a fair target. Sweeping the answer-token-F1 weight
across [{{RESULT_WEIGHT_SWEEP_LOW}}, {{RESULT_WEIGHT_SWEEP_HIGH}}] (citation support and
efficiency splitting the remainder in the default {{CONFIG_WEIGHT_GROUND}}:{{CONFIG_WEIGHT_EFF}} ratio), the compiler's winning configuration is
{{RESULT_WEIGHT_ROBUST}} — the declared finite sweep selects {{RESULT_WEIGHT_WINNER}} — so the headline
{{CONFIG_WEIGHT_ACC}}/{{CONFIG_WEIGHT_GROUND}}/{{CONFIG_WEIGHT_EFF}} choice has little effect on this finite sweep. (The efficiency term's
$1 - |\text{ranked}|/{{CONFIG_EFFICIENCY_SCALE}}$ uses {{CONFIG_EFFICIENCY_SCALE}} as the inline context budget in evidence slots; on
this compact set ranked evidence sits far below it, which is exactly why efficiency
stays high and near-constant.)

### DSPy Runtime and Neural Backend Validation {#sec:eval-neural}

The default extractive responder bounds the preceding answer-token-F1 results.
Two separate DSPy diagnostics exercise model replacement and compilation;
neither should be mistaken for a full runtime-harness comparison. The retained
local comparison uses `dspy.Predict(AnswerFromContext)` with each example's full
session as context, first with the extractive adapter and then with
`{{RESULT_NEURAL_MODEL}}` served through Ollama. It does not execute Inspector,
Retriever, or Memory Gate. Direct `LMClient` injection into `AutoHarness` is a
different, composable integration path ([@sec:op-lm]).

The held-out `BootstrapFewShot` before/after diagnostic is also explicitly
**extractive-backed** (`src.dspy_runtime.held_out_optimizer_lift`). It reports
no measured lift in its automatic `qa_metric` on that split; the extractive
responder ignores few-shot demonstrations by construction. This records a
metric null and an executable compilation path, not a neural optimizer ceiling
or an adjudicated answer-quality result. A neural before/after conclusion
requires a separately recorded neural optimization experiment.

[@fig:backend_comparison] reports token-F1 per task category for the deterministic
extractive backend versus the neural model on all {{RESULT_NEURAL_N}} examples.
On this expanded local aggregate, swapping in the neural LM changes mean answer token-F1
from {{RESULT_EXTRACTIVE_MEAN_F1}} to {{RESULT_NEURAL_MEAN_F1}}; paired mean delta
{{RESULT_NEURAL_PAIRED_DELTA}} with {{CONFIG_CI_LEVEL}}% interval
{{RESULT_NEURAL_PAIRED_CI}} and sign-flip randomization p={{RESULT_NEURAL_PAIRED_P}}
yield no statistically distinguishable improvement under the declared finite
comparison.
The neural model is higher on **preference** and **multi-session**
({{RESULT_EXTRACTIVE_MULTI_F1}} to {{RESULT_NEURAL_MULTI_F1}}), tied on temporal,
and lower on **code** ({{RESULT_EXTRACTIVE_CODE_F1}} to {{RESULT_NEURAL_CODE_F1}}),
knowledge-update, and single-session. These directions describe the retained
category means, not a general ordering across tasks or models.

The single-session examples also illustrate a metric caveat: a terse answer such
as "bluefish42" can receive less token-F1 than a sentence matching the gold
string "wifi password is bluefish42". Semantic appropriateness is not separately
adjudicated here, and this explanation should not be applied to the preference
category, whose recorded neural mean is higher. This is the construct problem
that motivates finer-grained factuality measures such as FActScore
[@min2023factscore]. Token-F1 measures lexical overlap, not semantic correctness.
With {{RESULT_NEURAL_N}} examples the comparison is a finite diagnostic.
`scripts/run_neural_eval.py` can record a new local cohort, but temperature
{{RESULT_NEURAL_TEMPERATURE}} and matching model tags alone do not guarantee
identical generations across runs or hosts.

![Paired token-F1 per synthetic evaluation example for the extractive and recorded neural model (`{{RESULT_NEURAL_MODEL}}`) in the full-context DSPy prediction diagnostic, not the runtime AutoHarness. Lines preserve pairing on the {{RESULT_NEURAL_N}} cases; guides and bands show marginal means and {{CONFIG_CI_LEVEL}}% descriptive intervals, with paired delta and sign-flip randomization p-value. Recorded with temperature {{RESULT_NEURAL_TEMPERATURE}} and max_tokens {{RESULT_NEURAL_MAX_TOKENS}} via `scripts/run_neural_eval.py`; values are model-, configuration-, and runtime-dependent.](../../output/figures/backend_comparison.png){#fig:backend_comparison width={{CONFIG_BACKEND_FIGURE_WIDTH}}%}

### Historical Cloud Diagnostic and Matched Backend Benchmarks {#sec:eval-openrouter}

The retained `data/openrouter_eval.json` is a separate finite,
non-adjudicated {{RESULT_OPENROUTER_N}}-example provider diagnostic for
`{{RESULT_OPENROUTER_MODEL}}`. It records temperature
{{RESULT_OPENROUTER_TEMPERATURE}} and max_tokens
{{RESULT_OPENROUTER_MAX_TOKENS}}, but lacks a run receipt binding raw requests,
dataset/config/code fingerprints, timing, and failure accounting. It therefore
does not establish that the complete runtime harness was exercised.

Its recorded means are {{RESULT_OPENROUTER_EXT_MEAN_F1}} for extractive and
{{RESULT_OPENROUTER_NEURAL_MEAN_F1}} for cloud. The legacy pass counts are
{{RESULT_OPENROUTER_EXT_PASS}} and {{RESULT_OPENROUTER_NEURAL_PASS}},
respectively; their threshold is not defined in that artifact, so they are not
interpreted as accuracy. The programming-language pair has token-F1
{{RESULT_OPENROUTER_RUST_NEURAL_F1}} for the short model answer versus
{{RESULT_OPENROUTER_RUST_EXT_F1}} for extractive, illustrating sensitivity to
gold phrasing rather than adjudicated correctness.

On the retained budget and deploy-error cases the cloud token-F1 values are
{{RESULT_OPENROUTER_BUDGET_NEURAL_F1}} and
{{RESULT_OPENROUTER_MULTIHOP_NEURAL_F1}}, versus
{{RESULT_OPENROUTER_BUDGET_EXT_F1}} and
{{RESULT_OPENROUTER_MULTIHOP_EXT_F1}} for extractive. These are case-level
observations, not evidence of a general reasoning advantage. Neither their
ordering nor the aggregate mean can rank cloud against the distinct local
cohort in [@sec:eval-neural].

Three interfaces must remain separate. `configure_openrouter` configures global
DSPy state; `scripts/run_openrouter.py` records a direct full-context DSPy smoke
diagnostic at `output/data/openrouter_result.json`; and
`src.llm.OpenRouterLM` implements the `LMClient` interface for the Reasoner.
The smoke recorder does not regenerate the historical aggregate.

The schema2 method benchmark (`src.evaluation.backend_benchmark` and
`scripts/run_backend_benchmark.py`) separates **backend identity** from
**context-policy method**. The built-in methods are `full_context`, `harness`,
`lexical_only`, and `adaptive`. Full context submits all session lines directly
to the actual selected LM with `render_signature_prompt(ReasonerSignature, ...)`;
it does not guarantee provider-side context retention. The harness methods use
fresh context-managed `AutoHarness` instances, with verification disabled so each
planned cell submits one completion attempt. Lexical-only changes fusion weights;
adaptive enables adaptive Inspector windows. Custom named harness configurations
retain their own validated configuration and method fingerprint.

The query and typed Reasoner template are fixed across methods, while the supplied
evidence text changes according to the context policy. The seeded cohort retains
example/category/stratum/seed identity; a deterministic interleaving precedes any
global limit. Backends run in outer loops and method order rotates within examples.
The validator rebuilds the planned backend × method × example matrix, verifies its
execution schedule, enforces prompt agreement across backends *within* each
example/method, and recomputes scores, summaries, groups, and paired contrasts.
[@fig:backend_method_design] records these methodological gates, not results.

![Source-owned method-design flow: seeded research examples cross backend identities and full-context or fresh harness context policies while query and typed Reasoner template remain fixed. One attempted completion per cell feeds a validated matrix. Within-backend reference pairing gates the seed-mean token-F1 contrast: absent references yield no contrast, incomplete planned pairs suppress estimates, single-seed contrasts lack intervals, and small-cluster bootstrap warnings remain explicit. This is a methodological schematic, not a numeric result or quality certificate.](../../output/figures/backend_method_design.png){#fig:backend_method_design width=100%}

Operational commands and the artifact contract are documented in
`docs/backend_benchmark.md` and [@sec:op-backend-benchmark].

### Optional Backend × Method Observations {#sec:eval-common-backends}

The following values come only from the validated selected schema2 artifact
(default `output/data/backend_benchmark.json`), never from the legacy local or
cloud aggregates. The generator may explicitly select an incomplete artifact;
absence is reported as not recorded, while schema1 and mutated evidence fail
closed. No mixed-method backend mean is computed.

**Recorded artifact status:** {{BACKEND_BENCHMARK_STATUS}}

**Recorded scope:** {{BACKEND_BENCHMARK_SCOPE}}

{{BACKEND_BENCHMARK_TABLE}}

**Within-model paired method contrasts**

{{BACKEND_COMPARISON_TABLE}}

The contrast pairs identical seeded examples within each backend and computes
the unweighted mean of the per-seed mean paired token-F1 deltas. This is not a
pooled-example mean when represented seed sizes differ. Wins, ties, and losses
count raw complete pairs. Any incomplete planned pair suppresses both the contrast
estimate and interval; missing reference methods produce no contrasts. A single
represented seed has no interval. With multiple represented seeds, seeded
cluster resampling of seed means gives descriptive intervals; small-cluster
warnings remain visible and do not establish significance, power, or a
target-population claim.

**Category and stratum observations**

{{BACKEND_GROUP_TABLE}}

All observation cells retain requested/completed/failed counts. Token-F1 measures
lexical overlap, not adjudicated semantic correctness. Incomplete cells report
success-only diagnostic means. Prompt characters count submitted text, not billed
tokens. Latency includes method execution, local work, transport/model serving,
and cleanup; it is neither throughput nor cost. Sequential execution, cold starts,
cache state, hardware/load, and provider scheduling preclude a speed-winner claim.
These are finite synthetic observations, not expert-quality or production
certificates, and cannot rank the historical DSPy or legacy cloud cohorts.
Cloud appears only with explicit collection consent.

**Recorded source and runtime binding:** {{BACKEND_BENCHMARK_PROVENANCE}}

Portable source-file checksums, exact method configurations, prompt identities,
generation options, and observed runtime metadata support artifact auditing.
Checksums bind recorded bytes; they do not authenticate a publisher or attest
the provider binary, hardware, or retained context.

### Context-Poisoning Stress Test {#sec:eval-injection}

Indirect prompt-injection research shows why retrieved data can blur the boundary
between content and instructions [@greshake2023indirect]. This finite probe
constructs {{RESULT_INJECT_N}} sessions with a supplied fact and a conflicting line
("IGNORE ALL PREVIOUS … the password is hunter2"; "SYSTEM OVERRIDE …") that tries
to override it. [@fig:injection_resistance] reports, per backend, whether the
*answer* is poisoned and whether a cited excerpt lexically contains the supplied
gold value.

The result is deliberately narrow. The two deterministic conditions record the
same poisoned count ({{RESULT_INJECT_HARNESS_POISON}} probes), so the probe shows no
poisoning-rate advantage. The cited-excerpt outcome is a legacy lexical
source-exposure proxy: the harness's joined cited excerpts contain the supplied
gold value on {{RESULT_INJECT_HARNESS_AUDIT}} probes, versus
{{RESULT_INJECT_NAIVE_AUDIT}} for the naive baseline. It does not verify a source
record, recovery of the true source, citation entailment, or claim-level
auditability. The optional neural row is recorded only when a live model is
available; the current aggregate records {{RESULT_INJECT_NEURAL_POISON}} neural
poison cases, and if that token is unavailable (`—`) the figure omits the neural
row. The figure therefore preserves a finite visibility observation alongside the
poisoning outcome (`scripts/run_injection_probe.py`).

![Context-poisoning probe outcomes for {{RESULT_INJECT_N}} synthetic paired cases. `X` marks a poisoned answer and `A` marks a cited excerpt whose text lexically contains the supplied gold value. The `A` overlay is a lexical cited-excerpt/source-exposure proxy, not source-record recovery or claim-level auditability; row labels show poison rates with Wilson intervals when available. The deterministic rows have the same poisoned count. Optional neural rows appear only when `data/injection_eval.json` contains a live measurement and retain model provenance.](../../output/figures/injection_resistance.png){#fig:injection_resistance width=65%}
