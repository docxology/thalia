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

The common benchmark (`src.evaluation.backend_benchmark` and
`scripts/run_backend_benchmark.py`) uses that last interface to run extractive,
local Ollama, and explicitly selected OpenRouter backends through the same
`AutoHarness` configuration and ordered seeded research examples. Fresh
context-managed harnesses isolate examples. Separate outputs retain backend,
model, generation options, dataset/config identities, answers, failures, and
observed end-to-end latency. Complete matched pairs permit descriptive token-F1
differences; incomplete backends retain successful-only diagnostic summaries
without promotion to complete comparisons. The validator and dashboard expose
that distinction. The interface alone is a measurement capability, not empirical
proof; recorded rows in the following subsection are separate finite observations,
not a quality/production certificate. Latency includes harness, transport, and
serving effects; it is neither token throughput nor cost.
Operational commands and the artifact contract are documented in
`docs/backend_benchmark.md` and [@sec:op-backend-benchmark].

### Optional Common-Harness Observations {#sec:eval-common-backends}

The following status and table are generated from the validated optional
`output/data/backend_benchmark.json` artifact, not from the legacy local or cloud
aggregates. If absent, the manuscript reports that no observation was recorded.
An incomplete diagnostic is labelled as such and must not be treated as a
complete paired comparison.

**Recorded artifact status:** {{BACKEND_BENCHMARK_STATUS}}

{{BACKEND_BENCHMARK_TABLE}}

The observation unit is a seeded synthetic research example evaluated through
the same runtime `AutoHarness`, with fresh memory state and matched
dataset/configuration identity. Counts expose requested/completed/failed rows.
Token-F1 measures lexical overlap; latency summaries describe successful-row
end-to-end harness time, including local work, model serving/transport, and
cleanup. They do not measure token throughput or cost. Sequential execution,
cold starts, cache state, hardware/load, and provider scheduling limit latency
comparability; no speed winner is inferred. Any displayed local rows establish
only a finite observational cohort, not adjudicated answer quality, population
performance, production readiness, or a comparison with the historical DSPy
and legacy cloud cohorts. Cloud evidence appears only if explicitly collected;
local availability or interface support is not a cloud success receipt.

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
