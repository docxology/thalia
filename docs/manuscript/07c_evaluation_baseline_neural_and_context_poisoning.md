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

The answer-token-F1 ceiling above is a property of the *default extractive LM*, so we
measure it directly. The same {{CONFIG_NUM_STAGES}}-stage contract runs
unchanged under (i) a real `dspy.Predict` program compiled by a real
`dspy.BootstrapFewShot` optimizer and (ii) a real neural model
(`{{RESULT_NEURAL_MODEL}}`, served locally through Ollama) dropped into the Reasoner
slot via `src/dspy_runtime/`. Inputs are identical across backends; only the
language model changes.

We also tested the optimiser with a held-out before/after comparison. On a
leave-out split of the dataset, the `BootstrapFewShot`-compiled
program shows **no measurable token-F1 lift** over the uncompiled one: the extractive
backend ignores few-shot demonstrations by construction, and the neural backend is
already at ceiling on these terse-gold questions. So the Compiler's *measured* value
on this task class is its auditable search trace. The held-out data show no
answer-quality gain, so the result is recorded as a null
(`src.dspy_runtime.held_out_optimizer_lift`).

[@fig:backend_comparison] reports token-F1 per task category for the deterministic
extractive backend versus the neural model on all {{RESULT_NEURAL_N}} examples.
On this expanded local aggregate, swapping in the neural LM changes mean answer token-F1
from {{RESULT_EXTRACTIVE_MEAN_F1}} to {{RESULT_NEURAL_MEAN_F1}}; paired mean delta
{{RESULT_NEURAL_PAIRED_DELTA}} with {{CONFIG_CI_LEVEL}}% interval
{{RESULT_NEURAL_PAIRED_CI}} and sign-flip randomization p={{RESULT_NEURAL_PAIRED_P}}
yield no statistically distinguishable improvement under the declared finite
comparison.
The neural model is
higher on **code** ({{RESULT_EXTRACTIVE_CODE_F1}} to {{RESULT_NEURAL_CODE_F1}}) and
multi-session ({{RESULT_EXTRACTIVE_MULTI_F1}} to {{RESULT_NEURAL_MULTI_F1}}), and
lower on the other categories. This mixed result shows that the extractive ceiling
depends on the model and metric. The retained aggregate supports a category-level
diagnostic; a general direction across tasks or models requires broader evidence.

The comparison also surfaces a metric caveat that strengthens the honesty story: on
single-session and preference the neural model scores *lower* on token-F1 despite
answers that may be semantically appropriate and lack separate adjudication (it
returns "bluefish42" where the gold
string is "wifi password is bluefish42"). This is the same construct problem that
motivates finer-grained factuality measures such as FActScore [@min2023factscore].
Token-F1 rewards lexical overlap with the gold phrasing, so a terse answer can be
penalised; the metric is the limiting factor there. With {{RESULT_NEURAL_N}} examples this is a
diagnostic signal; the figure is case-level. The neural numbers are reproducible
*on a host* (temperature {{RESULT_NEURAL_TEMPERATURE}}), with cross-host values
depending on machine and Ollama versions. Both backends and this table regenerate with
`scripts/run_neural_eval.py`.

![Paired token-F1 per synthetic evaluation example for the deterministic extractive Reasoner and the recorded neural model (`{{RESULT_NEURAL_MODEL}}`) under the same {{CONFIG_NUM_STAGES}}-stage contract. Lines preserve the pairing on each of the {{RESULT_NEURAL_N}} cases; guides and translucent bands show marginal means and {{CONFIG_CI_LEVEL}}% descriptive intervals, while the text reports the paired delta and sign-flip randomization p-value. Recorded with temperature {{RESULT_NEURAL_TEMPERATURE}} and max_tokens {{RESULT_NEURAL_MAX_TOKENS}} via `scripts/run_neural_eval.py`; the neural estimate is model- and configuration-dependent, with host-specific provenance.](../../output/figures/backend_comparison.png){#fig:backend_comparison width={{CONFIG_BACKEND_FIGURE_WIDTH}}%}

### Cloud-Model Validation via OpenRouter {#sec:eval-openrouter}

To probe whether the observed answer-token-F1 boundary is specific to one local
backend, we ran a separate finite {{RESULT_OPENROUTER_N}}-example provider diagnostic
against **`{{RESULT_OPENROUTER_MODEL}}`** accessed through
OpenRouter — routed via `dspy.LM` → litellm → the OpenRouter API, with no changes
to the {{CONFIG_NUM_STAGES}}-stage harness contract. The recorded results live at
`data/openrouter_eval.json`.

The headline numbers favour the extractive backend on mean token-F1:
**{{RESULT_OPENROUTER_EXT_MEAN_F1}}** ({{RESULT_OPENROUTER_EXT_PASS}}/{{RESULT_OPENROUTER_N}} pass) for extractive versus **{{RESULT_OPENROUTER_NEURAL_MEAN_F1}}** ({{RESULT_OPENROUTER_NEURAL_PASS}}/{{RESULT_OPENROUTER_N}} pass) for the neural backend. That raw
ordering reflects a token-F1 construct effect: **concise answers are structurally
penalised**. The recorded model returns
atomic, information-dense replies (short values and dates) while the gold strings
encode the surrounding sentence. Token overlap with a
longer gold string is higher for the extractive backend because it echoes the full
transcript line verbatim. The recorded model's answer is shorter and has no separate
adjudication here, so token-F1 can penalise it. The programming-language pair (F1
{{RESULT_OPENROUTER_RUST_NEURAL_F1}} vs. {{RESULT_OPENROUTER_RUST_EXT_F1}}) is the clearest illustration.

The ordering **reverses** on the two question types intended to require reasoning beyond
verbatim extraction. On the **cross-session budget synthesis** query ("What budget
did I mention across our sessions?") the extractive backend scores {{RESULT_OPENROUTER_BUDGET_EXT_F1}} — it can
only return the closest matching transcript line, which mentions vendors; the
neural backend answers with the budget value for an F1 of
{{RESULT_OPENROUTER_BUDGET_NEURAL_F1}}. On the **multi-hop deploy error** query ("What error does the deploy code
raise without CONFIG?") extractive again scores {{RESULT_OPENROUTER_MULTIHOP_EXT_F1}} (it surfaces the file path;
the exception is absent), while the neural backend answers "KeyError" for an F1 of {{RESULT_OPENROUTER_MULTIHOP_NEURAL_F1}}. These are
the synthesis and cross-document cases included to stress the contract; in this
finite probe, {{RESULT_OPENROUTER_MODEL}} has the higher token-F1 on both.

This finite, non-adjudicated probe is consistent with the Ollama diagnostic in
[@sec:eval-neural]. Answer token-F1 is bounded by the selected LM and the
gold-string tokenization, while the pipeline adds provenance and leaves semantic
judgment to the model. The two synthesis/multi-hop cases show why a neural backend
may produce a better answer than extraction on some questions. A general backend
ranking and quality effect require broader adjudicated evidence. The full
per-example breakdown is at `data/openrouter_eval.json` (`temperature: {{RESULT_OPENROUTER_TEMPERATURE}}`,
`max_tokens: {{RESULT_OPENROUTER_MAX_TOKENS}}`, `model: {{RESULT_OPENROUTER_MODEL}}`,
{{RESULT_OPENROUTER_N}} examples).

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
