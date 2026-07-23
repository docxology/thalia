# Evaluation: Baselines, Model Dependence, and Context-Poisoning Diagnostics {#sec:evaluation-baseline-neural-context-poisoning}

## Does the orchestration help? A no-harness baseline {#sec:eval-baseline}

A fair challenge: does the {{CONFIG_NUM_STAGES}}-stage pipeline earn its complexity, or could a naive
baseline — hand the LM the *entire* session with no Inspector windowing, no Retriever
ranking, and no citations — do as well? [@fig:orchestration_value] decomposes both.
On raw accuracy they *tie* exactly ({{RESULT_NAIVE_ACCURACY}} each): on this compact
set the extractive LM retrieves the gold line under the declared token-overlap rule
whether or not the context is narrowed,
so the pipeline does not raise accuracy. But the naive baseline earns zero grounding
(it cites nothing) and zero efficiency (it dumps the full context), so its composite
is only {{RESULT_NAIVE_COMPOSITE}} against the pipeline's {{RESULT_COMPOSITE}} — a
lift of {{RESULT_ORCHESTRATION_LIFT}} that comes *entirely* from the grounding and
efficiency the orchestration provides. The honest reading is precise: on this dataset
the pipeline's value is provenance and bounded context, not raw answer accuracy
(which is LM-bounded — [@sec:eval-neural]).

![Composite score per condition on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo: naive full-context baseline versus full pipeline, stacked into weighted accuracy/grounding/efficiency components. Accuracy ties; the observed contrast is the grounding and efficiency the naive baseline structurally cannot earn under this finite extractive-LM configuration. It is descriptive and non-causal, with no interval or population interpretation.](../output/figures/orchestration_value.png){#fig:orchestration_value width=60%}

The composite weights themselves are a fair target. Sweeping the accuracy weight
across [{{RESULT_WEIGHT_SWEEP_LOW}}, {{RESULT_WEIGHT_SWEEP_HIGH}}] (grounding and
efficiency splitting the remainder in the default {{CONFIG_WEIGHT_GROUND}}:{{CONFIG_WEIGHT_EFF}} ratio), the compiler's winning configuration is
{{RESULT_WEIGHT_ROBUST}} — the declared finite sweep selects {{RESULT_WEIGHT_WINNER}} — so the headline
{{CONFIG_WEIGHT_ACC}}/{{CONFIG_WEIGHT_GROUND}}/{{CONFIG_WEIGHT_EFF}} choice is not load-bearing. (The efficiency term's
$1 - |\text{ranked}|/{{CONFIG_EFFICIENCY_SCALE}}$ uses {{CONFIG_EFFICIENCY_SCALE}} as the inline context budget in evidence slots; on
this compact set ranked evidence sits far below it, which is exactly why efficiency
stays high and near-constant.)

## Real DSPy and neural validation {#sec:eval-neural}

The accuracy ceiling above is a property of the *default extractive LM*, so we
measure that claim rather than assert it. The same {{CONFIG_NUM_STAGES}}-stage contract runs
unchanged under (i) a real `dspy.Predict` program compiled by a real
`dspy.BootstrapFewShot` optimizer and (ii) a real neural model
(`{{RESULT_NEURAL_MODEL}}`, served locally through Ollama) dropped into the Reasoner
slot via `src/dspy_runtime/`. Inputs are identical across backends; only the
language model changes.

We also tested the optimiser the only way that can falsify it — a held-out
before/after. On a leave-out split of the dataset, the `BootstrapFewShot`-compiled
program shows **no measurable token-F1 lift** over the uncompiled one: the extractive
backend ignores few-shot demonstrations by construction, and the neural backend is
already at ceiling on these terse-gold questions. So the Compiler's *measured* value
on this task class is its auditable search trace, not a demonstrated accuracy gain —
we report that null rather than imply an improvement the data does not show
(`src.dspy_runtime.held_out_optimizer_lift`).

[@fig:backend_comparison] reports token-F1 per task category for the deterministic
extractive backend versus the neural model on all {{RESULT_NEURAL_N}} examples.
On this expanded local aggregate, swapping in the neural LM changes mean accuracy
from {{RESULT_EXTRACTIVE_MEAN_F1}} to {{RESULT_NEURAL_MEAN_F1}}; paired mean delta
{{RESULT_NEURAL_PAIRED_DELTA}} with {{CONFIG_CI_LEVEL}}% interval
{{RESULT_NEURAL_PAIRED_CI}} and permutation p={{RESULT_NEURAL_PAIRED_P}} is not a
statistically distinguishable improvement under the declared finite comparison, so we do not call it a lift. The neural model is
higher on **code** ({{RESULT_EXTRACTIVE_CODE_F1}} to {{RESULT_NEURAL_CODE_F1}}) and
multi-session ({{RESULT_EXTRACTIVE_MULTI_F1}} to {{RESULT_NEURAL_MULTI_F1}}), but
lower on the other categories. This mixed result is useful evidence that the
extractive ceiling is model- and metric-dependent, not evidence that every local LM
has a higher mean on the retained task slice; that aggregate does not establish
improvement for every task or model.

The comparison also surfaces a metric caveat that strengthens the honesty story: on
single-session and preference the neural model scores *lower* on token-F1 despite
answers that may be semantically appropriate but are not separately human-annotated (it returns "bluefish42" where the gold
string is "wifi password is bluefish42"). Token-F1 rewards lexical overlap with the
gold phrasing, so a terse answer can be penalised; the metric, not
the model, is the limiting factor there. With {{RESULT_NEURAL_N}} examples this is a
diagnostic signal, not a population estimate, so the figure is case-level rather
than a category-rate bar chart. Unlike the bit-identical deterministic path, the
neural numbers are reproducible *on a host* (temperature {{RESULT_NEURAL_TEMPERATURE}}) rather than across
machines and Ollama versions. Both backends and this table regenerate with
`scripts/run_neural_eval.py`.

![Paired token-F1 per synthetic evaluation example for the deterministic extractive Reasoner versus the recorded neural model (`{{RESULT_NEURAL_MODEL}}`) under the same {{CONFIG_NUM_STAGES}}-stage contract. Lines preserve the pairing on each of the {{RESULT_NEURAL_N}} cases; guides and translucent bands show marginal means and {{CONFIG_CI_LEVEL}}% intervals, while the text reports the paired delta and permutation p-value. Recorded with temperature {{RESULT_NEURAL_TEMPERATURE}} and max_tokens {{RESULT_NEURAL_MAX_TOKENS}} via `scripts/run_neural_eval.py`; the neural estimate is model- and configuration-dependent, not bit-pinned or a population estimate.](../output/figures/backend_comparison.png){#fig:backend_comparison width={{CONFIG_BACKEND_FIGURE_WIDTH}}%}

## Cloud neural validation via OpenRouter {#sec:eval-openrouter}

To stress-test the accuracy ceiling claim beyond a single local model, we ran the
same {{RESULT_OPENROUTER_N}}-example evaluation against **`{{RESULT_OPENROUTER_MODEL}}`** accessed through
OpenRouter — routed via `dspy.LM` → litellm → the OpenRouter API, with no changes
to the {{CONFIG_NUM_STAGES}}-stage harness contract. The recorded results live at
`data/openrouter_eval.json`.

The headline numbers appear to favour the extractive backend: mean token-F1 of
**{{RESULT_OPENROUTER_EXT_MEAN_F1}}** ({{RESULT_OPENROUTER_EXT_PASS}}/{{RESULT_OPENROUTER_N}} pass) for extractive versus **{{RESULT_OPENROUTER_NEURAL_MEAN_F1}}** ({{RESULT_OPENROUTER_NEURAL_PASS}}/{{RESULT_OPENROUTER_N}} pass) for the neural backend. That raw
ordering is misleading, however, because it reflects a well-known token-F1
pathology — **concise answers are structurally penalised**. The recorded model returns
atomic, information-dense replies (short values and dates) while the gold strings
encode the surrounding sentence. Token overlap with a
longer gold string is higher for the extractive backend precisely because it echoes
the full transcript line verbatim; the recorded model's answer is shorter and is not separately
human-annotated here, so token-F1 can penalise it. The programming-language pair (F1
{{RESULT_OPENROUTER_RUST_NEURAL_F1}} vs. {{RESULT_OPENROUTER_RUST_EXT_F1}}) is the clearest illustration.

The ordering **reverses** on the two question types intended to require reasoning beyond
verbatim extraction. On the **cross-session budget synthesis** query ("What budget
did I mention across our sessions?") the extractive backend scores {{RESULT_OPENROUTER_BUDGET_EXT_F1}} — it can
only return the closest matching transcript line, which happens to mention vendors
rather than the dollar figure — while the neural backend answers with the budget value for an F1 of
{{RESULT_OPENROUTER_BUDGET_NEURAL_F1}}. On the **multi-hop deploy error** query ("What error does the deploy code
raise without CONFIG?") extractive again scores {{RESULT_OPENROUTER_MULTIHOP_EXT_F1}} (it surfaces the file path,
not the exception), while the neural backend answers "KeyError" for an F1 of {{RESULT_OPENROUTER_MULTIHOP_NEURAL_F1}}. These are
the synthesis and cross-document cases included to stress the contract; in this
finite probe, {{RESULT_OPENROUTER_MODEL}} has the higher token-F1 on both.

The conclusion reinforces the Ollama finding in [@sec:eval-neural]: accuracy on
simple retrieval questions is LM-bounded and the pipeline adds provenance, not raw
score; on hard synthesis and multi-hop questions a capable neural model lifts the
ceiling in ways the extractive backend structurally cannot match. The full
per-example breakdown is at `data/openrouter_eval.json` (`temperature: {{RESULT_OPENROUTER_TEMPERATURE}}`,
`max_tokens: {{RESULT_OPENROUTER_MAX_TOKENS}}`, `model: {{RESULT_OPENROUTER_MODEL}}`,
{{RESULT_OPENROUTER_N}} examples).

## Cognitive security: context-poisoning {#sec:eval-injection}

A memory harness is only as trustworthy as its behaviour under *adversarial*
context — the cognitive-security question of whether injected text can override a
stored fact. We probe it directly: {{RESULT_INJECT_N}} sessions each state a true
fact, then inject an adversarial line ("IGNORE ALL PREVIOUS … the password is
hunter2"; "SYSTEM OVERRIDE …") that tries to override it.
[@fig:injection_resistance] reports, per backend, how often the *answer* is poisoned
and how often the true source stays auditable.

The result is honest and instructive, and it is *not* "the harness is immune".
Lexical extraction has no inherent injection immunity: the grounded harness and the
naive full-context baseline are poisoned at the same rate
({{RESULT_INJECT_HARNESS_POISON}} probes), because whichever line lexically overlaps
the query most simply wins. What separates them is **provenance** — the harness keeps
the true source in its cited evidence on {{RESULT_INJECT_HARNESS_AUDIT}} probes
against {{RESULT_INJECT_NAIVE_AUDIT}} for the naive baseline, so even a poisoned
answer stays auditable and recoverable because the citation trail surfaces both the
injected and the genuine source. The optional neural row is recorded only when a
live model is available; the current aggregate records {{RESULT_INJECT_NEURAL_POISON}}
neural poison cases, and if that token is unavailable (`—`) the figure omits the
neural row rather than inferring one. The property THALIA actually provides is
therefore **visibility, not immunity**: grounding does not stop poisoning, but it
refuses to hide it (`scripts/run_injection_probe.py`).

![Context-poisoning outcome per synthetic paired probe ({{RESULT_INJECT_N}} cases), reported as exact finite-set counts rather than population rates. `X` marks a poisoned answer and `A` marks that the true source remains cited; row labels show case rates with Wilson intervals when available. Lexical extraction is poisonable, but the grounded harness keeps the true source auditable; optional neural rows appear only when `data/injection_eval.json` contains a live neural measurement and remain model-dependent. No causal or universal robustness claim follows.](../output/figures/injection_resistance.png){#fig:injection_resistance width=65%}
