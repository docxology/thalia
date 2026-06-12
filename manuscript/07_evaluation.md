# Evaluation {#sec:evaluation}

The evaluation is deterministic and offline: a fixed LongMemEval-style dataset, a
deterministic extractive language model, and a composite metric computed in pure
Python. The goal is to validate the *machinery* and to be explicit about what a
deterministic local harness can and cannot demonstrate.

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

## Real benchmark: LongMemEval_S {#sec:eval-real}

The synthetic results, however carefully measured, test machinery the dataset was
built to suit. The honest reckoning is a real benchmark. We run the harness over
**LongMemEval_S** [@wu2025longmemeval] — {{RESULT_LME_N_EXT}} questions over ~40-session,
~115k-token haystacks — mapped onto the same `EvalExample` contract
(`src.evaluation.longmemeval`), scored with **session-level grounding** (was the cited
evidence drawn from the gold session?). Because the benchmark labels evidence at the
session level, this credits a citation that lands on *any* line of the gold session;
it is therefore an **upper bound** on stricter line-level grounding, and we read it as
"did retrieval reach the right session" rather than the exact line. This is external
data, so these results are reproducible from *code plus the downloaded benchmark*
rather than code alone — an honest relaxation of the self-contained thesis, and worth it.

The reckoning is stark ([@fig:longmemeval]). Extractive accuracy **collapses** to
{{RESULT_LME_EXT_ACC}} {{RESULT_LME_EXT_ACC_CI}} — from the synthetic
{{RESULT_LARGE_COMPOSITE}} — confirming directly that the synthetic set was far too
easy and that the extractive default is near-useless on real long-context memory.
Three findings follow, now with real statistics ({{RESULT_LME_N_EXT}} questions, {{CONFIG_CI_LEVEL}}%
bootstrap CIs):

1. **A real neural model matters here.** Dropping `{{RESULT_LME_MODEL}}` into the
   Reasoner ({{RESULT_LME_N_NEURAL}} questions, the Inspector windowing first) raises
   accuracy to {{RESULT_LME_NEURAL_ACC}} {{RESULT_LME_NEURAL_ACC_CI}} — a real ~{{RESULT_LME_NEURAL_RATIO}}×
   gain whose {{CONFIG_CI_LEVEL}}% interval clears the extractive one (the two CIs do not overlap), where
   the synthetic set showed only a tie ([@sec:eval-baseline]). The LM-vs-pipeline argument
   is finally visible on data hard enough to separate them.
2. **Retrieval is the dominant bottleneck — but not retrieval *ranking*.** Session
   grounding is only {{RESULT_LME_GROUNDING}} {{RESULT_LME_GROUNDING_CI}}: the harness
   surfaces the gold evidence session under half the time, and accuracy cannot exceed
   what is surfaced. We expected a learned dense embedder to be the fix; [@sec:eval-bottleneck]
   shows the committed full-haystack ranking aggregate recovers the evidence
   essentially perfectly. The loss is upstream, in the
   Inspector's aggressive context-narrowing, and widening that window is what recovers
   grounding and accuracy.
3. **The honest scope.** {{RESULT_LME_NEURAL_ACC}} is a low absolute number: ATLAS as a
   deterministic offline harness with a small local model is not competitive with a
   hosted-LLM memory system on LongMemEval, and we do not claim it is. What the run
   establishes is that the *machinery* scales to real 115k-token haystacks, that the
   architecture's plug-in points behave as designed under real load, and that the
   evaluation's difficulty — not its plumbing — is where the next gains live.

![Real LongMemEval_S: answer accuracy and session-level grounding for the extractive and neural Reasoners with {{CONFIG_CI_LEVEL}}% bootstrap CIs ({{RESULT_LME_N_EXT}} questions extractive, {{RESULT_LME_N_NEURAL}} neural). Session grounding is an upper bound because any line from the answer session counts. Accuracy collapses versus the synthetic set; the neural advantage becomes statistically real; session grounding (~{{RESULT_LME_GROUNDING}} extractive, lower still for the neural Reasoner) caps both — retrieval is the bottleneck on real long-context data.](../output/figures/longmemeval.png){#fig:longmemeval width=70%}

## Diagnosing the bottleneck: the Inspector, not retrieval {#sec:eval-bottleneck}

The collapse in [@sec:eval-real] invites the obvious fix — swap the lexical lane for a
learned dense retriever. The committed aggregate is narrower: over {{RESULT_BN_N}}
questions, full-haystack ranking hit@10 is {{RESULT_BN_RANKING_RECALL}}, while the
optional per-mode learned-embedder probe is only cited when
`ranking_recall_by_mode.available` is true in the regenerated bottleneck artifact. On
real LongMemEval, retrieval *ranking* is not the problem in the measured aggregate.
The loss is upstream: over {{RESULT_BN_N}} questions, full-haystack
ranking recall is {{RESULT_BN_RANKING_RECALL}} while the **Inspector's** window recall —
whether its grep-based narrowing even surfaces a gold line for the Retriever to rank —
is only {{RESULT_BN_INSPECTOR_RECALL}}. The RLM-style narrowing that lets the harness
scale to 115k tokens is exactly what discards the evidence.

So the fix is to relax the narrowing, and [@fig:bottleneck] measures it. Raising the
Inspector's `max_windows` from {{RESULT_BN_MAXWIN_LO}} to {{RESULT_BN_MAXWIN_HI}} lifts
extractive grounding from {{RESULT_BN_GROUNDING_LO}} to {{RESULT_BN_GROUNDING_HI}} — but
extractive *accuracy* barely moves, because it is LM-bound (it cannot phrase the answer
even when shown the evidence). The two fixes compose: with a real Reasoner
(`{{RESULT_BN_MODEL}}`), the same widening converts recovered recall into accuracy,
**nearly doubling it from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_NEURAL_ACC_HI}}**.
(This analysis uses a {{RESULT_BN_N_NEURAL}}-question neural subset, so its absolute
values sit slightly below the {{RESULT_LME_N_NEURAL}}-question headline of
[@sec:eval-real]; the *relative* gain from relaxing the narrowing is the claim.)
The actionable result is concrete: ATLAS's default `max_windows={{CONFIG_MAX_WINDOWS}}`
is tuned for compact contexts and is the dominant bottleneck on real long-context memory;
widening the Inspector *and* using a neural Reasoner is what the benchmark rewards. That
the dense lane did not help — though it remains the right tool for paraphrase recall
([@sec:eval-learned]) — is itself the finding: we localised the bottleneck rather than
assuming it.

We do not stop at the diagnosis. The fix it implies — that the narrowing budget should
*scale with the haystack* rather than stay fixed — ships as an **adaptive Inspector**
(`adaptive_windows`, opt-in, `src/stages/inspector.py`): it sets `max_windows` to
roughly one window per {{CONFIG_ADAPTIVE_RATIO}} session lines, floored at the
compact-context default. On
the {{RESULT_NUM_EXAMPLES}}-example synthetic set this is a **bit-for-bit no-op** — a
compact context never exceeds the floor, so determinism and every headline number are
preserved — yet on real LongMemEval it recovers the lost recall *automatically*,
lifting neural accuracy from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_ADAPTIVE_ACC}}:
the manually-tuned `max_windows={{RESULT_BN_MAXWIN_HI}}` result ([@fig:bottleneck], star),
reached with no tuning at all. The diagnosis becomes a one-flag method.

![Real LongMemEval: relaxing the Inspector's `max_windows` lifts extractive grounding and, with a neural Reasoner, nearly doubles accuracy; the opt-in adaptive Inspector (star) reaches the manually-tuned best automatically. Localisation: full-haystack ranking recall is perfect ({{RESULT_BN_RANKING_RECALL}}) while Inspector window recall is {{RESULT_BN_INSPECTOR_RECALL}} — the narrowing, not the ranking, is the loss.](../output/figures/bottleneck.png){#fig:bottleneck width=70%}

## Does the orchestration help? A no-harness baseline {#sec:eval-baseline}

A fair challenge: does the five-stage pipeline earn its complexity, or could a naive
baseline — hand the LM the *entire* session with no Inspector windowing, no Retriever
ranking, and no citations — do as well? [@fig:orchestration_value] decomposes both.
On raw accuracy they *tie* exactly ({{RESULT_NAIVE_ACCURACY}} each): on this compact
set the extractive LM recovers the gold line whether or not the context is narrowed,
so the pipeline does not raise accuracy. But the naive baseline earns zero grounding
(it cites nothing) and zero efficiency (it dumps the full context), so its composite
is only {{RESULT_NAIVE_COMPOSITE}} against the pipeline's {{RESULT_COMPOSITE}} — a
lift of {{RESULT_ORCHESTRATION_LIFT}} that comes *entirely* from the grounding and
efficiency the orchestration provides. The honest reading is precise: on this dataset
the pipeline's value is provenance and bounded context, not raw answer accuracy
(which is LM-bounded — [@sec:eval-neural]).

![Composite decomposition for the naive full-context baseline versus the full pipeline, stacked into weighted accuracy/grounding/efficiency components. Accuracy ties; the orchestration's entire lift is the grounding and efficiency the naive baseline structurally cannot earn.](../output/figures/orchestration_value.png){#fig:orchestration_value width=60%}

The composite weights themselves are a fair target. Sweeping the accuracy weight
across [{{RESULT_WEIGHT_SWEEP_LOW}}, {{RESULT_WEIGHT_SWEEP_HIGH}}] (grounding and
efficiency splitting the remainder in the default {{CONFIG_WEIGHT_GROUND}}:{{CONFIG_WEIGHT_EFF}} ratio), the compiler's winning configuration is
{{RESULT_WEIGHT_ROBUST}} — always {{RESULT_WEIGHT_WINNER}} — so the headline
{{CONFIG_WEIGHT_ACC}}/{{CONFIG_WEIGHT_GROUND}}/{{CONFIG_WEIGHT_EFF}} choice is not load-bearing. (The efficiency term's
$1 - |\text{ranked}|/{{CONFIG_EFFICIENCY_SCALE}}$ uses {{CONFIG_EFFICIENCY_SCALE}} as the inline context budget in evidence slots; on
this compact set ranked evidence sits far below it, which is exactly why efficiency
stays high and near-constant.)

## Real DSPy and neural validation {#sec:eval-neural}

The accuracy ceiling above is a property of the *default extractive LM*, so we
measure that claim rather than assert it. The same five-stage contract runs
unchanged under (i) a real `dspy.Predict` program compiled by a real
`dspy.BootstrapFewShot` optimizer and (ii) a real neural model
(`{{RESULT_NEURAL_MODEL}}`, served locally through Ollama) dropped into the Reasoner
slot via `src/dspy_runtime.py`. Inputs are identical across backends; only the
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
Swapping in the neural LM raises mean accuracy from {{RESULT_EXTRACTIVE_MEAN_F1}} to
{{RESULT_NEURAL_MEAN_F1}}, and the gain concentrates exactly where extraction
*cannot* synthesise an answer: on **code** the extractive backend scores
{{RESULT_EXTRACTIVE_CODE_F1}} (it can only echo a transcript line) against
{{RESULT_NEURAL_CODE_F1}} for the neural model, and on **multi-session**
{{RESULT_EXTRACTIVE_MULTI_F1}} against {{RESULT_NEURAL_MULTI_F1}}. Those two classes
are the harness's weakest under the extractive LM, and they are the ones a real LM
rescues — direct evidence that the accuracy ceiling is LM-bounded, not
pipeline-bounded.

The comparison also surfaces a metric caveat that strengthens the honesty story: on
single-session and preference the neural model scores *lower* on token-F1 despite
answers that are arguably more correct (it returns "bluefish42" where the gold
string is "wifi password is bluefish42"). Token-F1 rewards lexical overlap with the
gold phrasing, so a terse-but-correct neural answer is penalised; the metric, not
the model, is the limiting factor there. With {{RESULT_NEURAL_N}} examples this is a
diagnostic signal, not a population estimate, so the figure is case-level rather
than a category-rate bar chart. Unlike the bit-identical deterministic path, the
neural numbers are reproducible *on a host* (temperature 0) rather than across
machines and Ollama versions. Both backends and this table regenerate with
`scripts/run_neural_eval.py`.

![Per-example token-F1 for the deterministic extractive Reasoner versus a real neural model (`{{RESULT_NEURAL_MODEL}}`) dropped into the same five-stage contract. Lines pair the two backends on each of the {{RESULT_NEURAL_N}} examples; horizontal guides mark the means. Recorded at temperature 0 via `scripts/run_neural_eval.py`; reproducible on a host serving the model, not bit-pinned.](../output/figures/backend_comparison.png){#fig:backend_comparison width={{CONFIG_BACKEND_FIGURE_WIDTH}}%}

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
neural row rather than inferring one. The property ATLAS actually provides is
therefore **visibility, not immunity**: grounding does not stop poisoning, but it
refuses to hide it (`scripts/run_injection_probe.py`).

![Context-poisoning over {{RESULT_INJECT_N}} probes as exact cases, not population rates. `X` marks a poisoned answer and `A` marks that the true source remains cited. Lexical extraction is poisonable, but only the grounded harness keeps the true source auditable; optional neural rows appear only when `data/injection_eval.json` contains a live neural measurement.](../output/figures/injection_resistance.png){#fig:injection_resistance width=65%}

## Retrieval mode comparison {#sec:eval-retrieval}

[@fig:retriever_comparison] compares lexical-only, semantic-only, and hybrid
composites at the **default (slack) retrieval budget** (`top_k=8`,
`max_evidence=5`). On the clean compact dataset all three coincide
(lexical {{RESULT_LEXICAL_COMPOSITE}}, semantic {{RESULT_SEMANTIC_COMPOSITE}},
hybrid {{RESULT_HYBRID_COMPOSITE}}): the gold evidence is unambiguous, so every
lane resolves it and the fused result is identical. The best single mode under the
tie-break is {{RESULT_BEST_MODE}}. This tie is itself the finding, and it
reconciles cleanly with the divergence seen in the sweeps below: **retrieval-method
choice is irrelevant while the budget is slack — every method retrieves the gold
span anyway — and only bites once the budget is binding.** The sweep figures
(ablation, MMR, RRF-weight) therefore use a tight budget (`top_k=2`,
`max_evidence=2`) *inherited unchanged from the noise study*, not a budget tuned to
manufacture divergence; we report the regime, labeled, on every figure.

![Composite metric by retrieval mode at the default slack budget (top-k 8, max-evidence 5). All three lanes resolve the unambiguous gold evidence identically; divergence is a property of a binding budget, of noise, and of the embedding model, not of the compact clean set.](../output/figures/retriever_comparison.png){#fig:retriever_comparison width=70%}

**Scope boundary (stated plainly).** The agentic-search study's headline —
*grep generally beats vector retrieval in the cited inline comparisons, with
harness/tool-style dependence* [@sen2026grep] — is **not**
reproduced by these local numbers, and we do not claim it is. The reason is
deliberate: ATLAS's semantic lane is a *deterministic hashing-embedding surrogate*
(character n-gram hashing into a fixed vector), chosen so the whole harness runs
offline with zero mocks. That surrogate captures sub-word overlap, not learned
distributional semantics, so it behaves more like a second lexical method than
like a dense retriever. Reproducing the lexical-vs-dense magnitude requires a
learned embedder — which drops into the same `SemanticIndex` interface without
touching any other stage. What the local experiment *does* validate is that the
two lanes, the weighted RRF fusion, and the budgeting all compose correctly and
deterministically, and that on this *clean* comparison all three lanes coincide
exactly at {{RESULT_HYBRID_COMPOSITE}} — the gold evidence is unambiguous, so the
fusion neither helps nor harms. Under session noise the lanes *do* diverge
([@sec:eval-noise]); we report that divergence honestly rather than generalising
the clean-set coincidence into a uniform hybrid-wins claim.

This boundary is methodologically useful. It separates the *orchestration*
question — can a typed harness pass evidence through Inspector, Retriever,
Reasoner, Memory Gate, and Compiler without losing provenance? — from the
*representation* question — which learned embedding model should occupy the
semantic lane? ATLAS answers the first question locally and leaves the second as a
drop-in experimental extension.

## Learned embedder: surrogate vs dense {#sec:eval-learned}

That drop-in is no longer hypothetical. Behind the same `top_k(query, k)` interface
as the hashing surrogate, `src/retrieval/learned.py` wires a real neural sentence
embedder (`{{RESULT_EMBED_MODEL}}`, served locally through Ollama). To make the
surrogate's limitation *measurable* rather than asserted, we score recall@1 on
{{RESULT_NUM_PROBES}} **paraphrase** probes — each query shares meaning but little
surface morphology with its gold document (e.g. "access code for the network" →
"the wifi password is …"). [@fig:paraphrase_retrieval] reports the result: the
hashing surrogate recovers the gold document on {{RESULT_SURROGATE_RECALL}} of the
probes — it cannot bridge a paraphrase that shares no character n-grams — while the
learned embedder recovers it on {{RESULT_LEARNED_RECALL}}. This is exactly the
qualitative gap the surrogate caveat anticipates, now demonstrated: the surrogate
behaves like a second lexical method, and only a learned embedder makes the semantic
lane genuinely *semantic*. The measurement is gated on a live embedding model and
recorded to `data/learned_retrieval.json` (regenerable via
`scripts/run_learned_retrieval.py`); the deterministic surrogate remains the offline
default, so the bit-reproducible core is untouched.

![Exact recall@1 counts on {{RESULT_NUM_PROBES}} paraphrase probes: the deterministic hashing surrogate versus a real learned embedder (`{{RESULT_EMBED_MODEL}}` via Ollama). The surrogate cannot match a paraphrase that shares no character n-grams with the gold document; the learned embedder resolves all of them. Recorded via `scripts/run_learned_retrieval.py`; the deterministic surrogate stays the offline default.](../output/figures/paraphrase_retrieval.png){#fig:paraphrase_retrieval width=60%}

## Noise scaling {#sec:eval-noise}

`noise_scaling_experiment` appends lexical false-friend lines (repeating query
tokens without the answer) and measures each mode at a tight retrieval budget,
reproducing the *form* of Experiment 2 in [@sen2026grep]. The composites stay
bounded and stable as noise grows — the Inspector's grep anchoring filters most
false friends before retrieval, which is precisely why lexical anchoring is robust.
Consistent with the surrogate caveat above, the hashing "semantic" lane does not
collapse under noise: at *every* distractor level it scores *above* the lexical
lane — at the noisiest ({{RESULT_NOISE_MAX_DISTRACTORS}} false-friend lines),
composite {{RESULT_NOISE_SEMANTIC}} vs. {{RESULT_NOISE_LEXICAL}} — because at the
tight retrieval budget its sub-word overlap still ranks the gold line first
(the pipeline is deterministic, so this ordering carries no run-to-run jitter).
Crucially the gap is present already at *zero* distractors: the surrogate outranks
lexical the moment the budget binds, so the lexical/semantic divergence is a
property of the *binding budget*, not of noise — the slack-budget tie in
[@sec:eval-retrieval] and this tight-budget gap are two views of the same budget
effect, and the noise axis only confirms the ordering is stable.
This is a property of *this* surrogate on *this* compact set, not evidence that a learned
dense retriever would resist lexical false friends the same way — the agentic-search
result [@sen2026grep] concerns learned dense retrieval, which we do not reproduce
here ([@sec:eval-retrieval]). We report the surrogate's measured behaviour rather
than tuning it to match the cited lexical-beats-dense ordering.

The important methodological point is that the noise probe remains falsifiable:
false-friend lines are appended mechanically, the retrieval budget is fixed, and
the measured ordering is pinned by regression tests. A future learned embedder can
replace the hashing lane and rerun the same probe; the rest of the harness and the
metric remain unchanged.

## Compiler {#sec:eval-compiler}

[@fig:compiler_convergence] shows the MIPRO-style search over
{{RESULT_NUM_CANDIDATES}} candidate configurations. On this dataset **every
candidate ties to full floating-point precision** — not merely to display
rounding: composite {{RESULT_COMPILED_SCORE}}, and the accuracy, grounding, and
efficiency components are bit-identical across all candidates. The tie is
*structural*, not a numerical coincidence: every config retrieves the same gold
spans (so accuracy and grounding are unchanged) and the dataset only ever yields a
couple of evidence windows, far below any candidate's `max_evidence` cap (so the
efficiency reward is the same too). With all three components pinned, no retrieval
depth can separate the configurations. The
reported optimum at top-k {{RESULT_COMPILED_TOP_K}} and max-evidence
{{RESULT_COMPILED_MAX_EVIDENCE}} is therefore a **tie-break** (the search returns
the first config achieving the shared maximum, which happens to be a tighter
budget), not a measured win — we report the exact tie rather than narrating a
nonexistent gain. The GEPA-style optimizer reaches the same plateau by reflective
mutation; its trace is recorded for audit. A perfectly flat convergence curve is
the honest outcome for a dataset whose gold evidence is trivially retrievable: the
search machinery is exercised end-to-end, and on a harder distribution — where
retrieval depth changes which spans survive — the same loop has room to move (see
the ablation and MMR sweep above, where a tight budget does separate the methods).

Two further diagnostics close the section. The RRF lane-weight sweep
([@fig:rrf_sensitivity]) confirms that under a *tight* budget the fusion does have a
shape — a non-monotonic dip at the balanced midpoint — even where every weight ties
under the slack default. And the consolidation curves ([@fig:consolidation])
illustrate, **schematically rather than empirically**, the memory-fault mechanism of
@zhang2026memory that the episodic-first Memory Gate is built to avoid: forced
per-turn consolidation degrades below the no-memory baseline while the gated regime
does not.

![MIPRO-style compiler search: candidate composite scores and the best-so-far curve. Every candidate ties exactly on this easy dataset, so the curve is intentionally flat and the optimum is a tie-break rather than a measured improvement. The inset decomposes the composite into its weighted accuracy/grounding/efficiency components, each constant across candidates — the flatness is a proven structural tie, not a rendering accident.](../output/figures/compiler_convergence.png){#fig:compiler_convergence width=70%}

![RRF lane-weight sensitivity under a tight retrieval budget: composite as the lexical weight sweeps from 0 to 1 (semantic = 1 − weight). On this clean set the sub-word semantic surrogate ranks the gold line marginally better than BM25, so semantic-heavy fusion (lexical weight $\le 0.4$) scores highest; the curve then steps down non-monotonically — with a single dip at the balanced midpoint (lexical weight 0.5, where neither lane's ranking dominates) before settling onto a slightly lower lexical-heavy plateau. Under the loose default budget every weight ties — the tight budget is what surfaces the tradeoff.](../output/figures/rrf_sensitivity.png){#fig:rrf_sensitivity width=70%}

![Schematic memory-utility curves: forced per-turn consolidation rises then degrades below the no-memory baseline, while the episodic-first gated regime rises and never falls below it. Illustrative of the mechanism in @zhang2026memory, not an empirical measurement.](../output/figures/consolidation_curve.png){#fig:consolidation width=70%}

## Added-method diagnostics {#sec:eval-added}

Four further figures characterise the pipeline and the added methods. The
**evidence funnel** ([@fig:evidence_funnel]) quantifies the narrowing from raw
session lines through Inspector windows and ranked evidence down to cited sources —
the context-rot defence made visible. The **per-category breakdown**
([@fig:category_breakdown]) shows where the harness is strong and weak across the
six task classes. The **noise-scaling** curves ([@fig:noise_scaling]) plot each
lane's composite as distractor lines accumulate; under the default RRF weights the
hybrid lane tracks the lexical lane *exactly* (it is drawn dashed so it stays
visible over the solid lexical line), a direct, honest read-out of the scope
boundary that the sub-word semantic surrogate contributes nothing the lexical
signal does not already capture. The **MMR tradeoff** ([@fig:mmr_tradeoff]) sweeps
$\lambda$ in [@eq:mmr] from pure diversity to pure relevance under the same tight
retrieval budget (`top_k=2`, `max_evidence=2`) as the ablation and noise study:
pure diversity ($\lambda=0$) scores measurably lower because maximizing
dissimilarity can evict the discriminative span from the two-slot budget, and the
curve steps up to its plateau as soon as relevance is weighted at all ($\lambda \ge 0.1$).
Under the loose default budget the sweep would be flat by construction; the tight
budget surfaces the real diversity penalty without tuning the dataset.

![Evidence narrowing funnel: mean counts per query from raw session lines through Inspector windows, ranked evidence, and cited sources. Counts come from `src.evaluation.evidence_funnel` on the fixed six-example dataset; the figure measures context narrowing, not answer quality by itself.](../output/figures/evidence_funnel.png){#fig:evidence_funnel width=70%}

![Composite metric per task category on the fixed deterministic dataset. Each bar averages the same token-F1, grounding, and efficiency metric used for the headline results; the categories are diagnostic slices, not population estimates.](../output/figures/category_breakdown.png){#fig:category_breakdown width=70%}

![Composite metric per retrieval lane as lexical false-friend distractors are appended under the tight budget (`top_k=2`, `max_evidence=2`). The semantic line is the deterministic hashing surrogate, so the measured ordering is local to this surrogate and does not reproduce learned dense retrieval.](../output/figures/noise_scaling.png){#fig:noise_scaling width=70%}

![MMR relevance/diversity tradeoff under the same tight retrieval budget: composite as $\lambda$ sweeps from 0 (max diversity) to 1 (pure relevance). The sweep shows a two-slot selection penalty for pure diversity on this compact set; under the loose default budget it would be flat.](../output/figures/mmr_tradeoff.png){#fig:mmr_tradeoff width=70%}

## Added-method ablation {#sec:eval-ablation}

[@fig:method_ablation] reports the composite for the base pipeline and each added
retrieval method (query expansion, recency weighting, MMR), plus all combined, on
the single-turn dataset. The ablation runs under the same *tight* retrieval budget
(`top_k=2`, `max_evidence=2`) as the MMR sweep and noise study: under the loose
default budget every gold span is retrieved regardless of method, so the ablation
is null *by construction* — every condition is byte-identical, which measures the
budget, not the methods. A tight budget instead forces a genuine selection contest,
where each method can change which evidence survives. We do not tune the dataset to
manufacture a gap; we use a realistic budget under which the methods can operate at
all. Under that budget recency weighting is the clear winner — reordering by
recency promotes the discriminative span into the surviving evidence — while query
expansion is mildly negative (the extra terms dilute a query that was already
precise) and MMR is neutral on a set this small. **Memory recall is excluded from
this single-turn ablation** because it requires a populated episodic store; it is
exercised directly in the recall and harness tests, where a fact held only in the
episodic store (absent from the immediate session history) is recalled and surfaces
in the answer's citations.

![Added-method ablation under a tight retrieval budget: composite for base, each retrieval method, and all combined. Recency weighting is the clear winner; expansion is mildly negative; MMR is neutral on a set this small.](../output/figures/method_ablation.png){#fig:method_ablation width=70%}

## Summary {#sec:eval-summary}

The harness is correct, deterministic, and fully exercised: {{RESULT_NUM_EXAMPLES}}
examples across all task categories, high grounding and efficiency, a retrieval
lane comparison, a noise-scaling probe, and a compiler that searches and reports an
optimum. The two honest boundaries — extractive-LM accuracy and the hashing
semantic surrogate — are exactly the two designed plug-in points (a real LM, a real
embedder), neither of which perturbs the rest of the architecture.

The result is therefore not "ATLAS beats another agent." The result is that a
typed, lexical-anchored, episodic-first, compiler-optimized harness can be implemented
as deterministic code, measured with auditable citations, regenerated through the
template pipeline, and extended at precisely identified model and embedding
boundaries.
