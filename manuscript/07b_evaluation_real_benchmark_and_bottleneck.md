# External Benchmark Transfer and Bottleneck Diagnosis {#sec:evaluation-real-benchmark-bottleneck}

## External benchmark: {{RESULT_LME_BENCHMARK}} {#sec:eval-real}

The synthetic results, however carefully measured, test machinery the dataset was
built to suit. The transfer check is an external benchmark. We run the harness over
**{{RESULT_LME_BENCHMARK}}** [@wu2025longmemeval] — {{RESULT_LME_N_EXT}} questions over long,
multi-session haystacks — mapped onto the same `EvalExample` contract
(`src.evaluation.longmemeval`), scored with **session-level grounding** (was the cited
evidence drawn from the gold session?). Because the benchmark labels evidence at the
session level, this credits a citation that lands on *any* line of the gold session;
it is therefore an **upper bound** on stricter line-level grounding, and we read it as
"did retrieval reach the right session" rather than the exact line. This is external
data, so these results are reproducible from *code plus the downloaded benchmark*
rather than code alone — a deliberate, disclosed relaxation of the self-contained thesis.

The external-benchmark comparison ([@fig:longmemeval]) is deliberately a transfer
diagnostic. Extractive accuracy is lower in this retained slice at
{{RESULT_LME_EXT_ACC}} {{RESULT_LME_EXT_ACC_CI}} — versus the synthetic
{{RESULT_LARGE_ACCURACY}} {{RESULT_LARGE_ACCURACY_CI}} on the same token-F1
component — indicating that the synthetic construct is easier than this retained
slice and that the extractive default is below the target usefulness of this
long-context task (a bound on answer phrasing, not on retrieval — the
localisation below shows the evidence is largely reachable).
Three findings follow, now with recorded benchmark statistics ({{RESULT_LME_N_EXT}} questions,
{{CONFIG_CI_LEVEL}}% descriptive bootstrap intervals):

1. **A real neural model changes this retained slice.** Dropping `{{RESULT_LME_MODEL}}` into the
   Reasoner ({{RESULT_LME_N_NEURAL}} questions, the Inspector windowing first) raises
   accuracy to {{RESULT_LME_NEURAL_ACC}} {{RESULT_LME_NEURAL_ACC_CI}} — a descriptive ~{{RESULT_LME_NEURAL_RATIO}}×
   point-estimate contrast. The extractive and neural rows have different retained
   sample sizes and are not a paired model comparison, so their separate bootstrap
   intervals are reported for uncertainty description rather than interpreted by
   interval overlap. The synthetic set showed only a tie ([@sec:eval-baseline]);
   this retained external-benchmark slice is harder and model-dependent.
2. **Evidence reachability is the bottleneck in this retained slice, not ranking
   once evidence is exposed.** Session grounding is only {{RESULT_LME_GROUNDING}}
   {{RESULT_LME_GROUNDING_CI}}: the harness surfaces the gold evidence session at
   the observed rate {{RESULT_LME_GROUNDING}}, and answer accuracy in this evaluation is constrained by what is surfaced. We expected a learned
   dense embedder to be the fix; [@sec:eval-bottleneck] shows the committed
   full-haystack ranking reaches a gold evidence line in {{RESULT_BN_RANKING_RECALL}} of
   the retained cases. In this diagnostic, the larger observed loss is upstream, in
   the Inspector's aggressive context-narrowing, and widening that window is
   associated with recovered grounding and accuracy.
3. **The honest scope.** {{RESULT_LME_NEURAL_ACC}} is a low absolute number: this
   deterministic offline harness with a small local model is not a comparison against
   a hosted-LLM memory system on {{RESULT_LME_BENCHMARK}}, and we do not claim it is.
   What the run
   establishes is that the *machinery* runs on external long-token haystacks, that the
   architecture's plug-in points behave as designed under real load, and that the
   evaluation's difficulty — not its plumbing — is where the next gains live.

![{{RESULT_LME_BENCHMARK}} answer accuracy and session-level grounding for the extractive and neural Reasoners with {{CONFIG_CI_LEVEL}}% descriptive bootstrap intervals ({{RESULT_LME_N_EXT}} extractive questions, {{RESULT_LME_N_NEURAL}} neural). Retained rows have different sample sizes, so intervals are not a formal between-model comparison. Session grounding is an upper-bound reachability measure because any line from the answer session counts, not line-level attribution. Benchmark SHA-256, retained status {{RESULT_LME_BENCHMARK_STATUS}}, and model digest are recorded in `data/longmemeval_results.json`; neural values are model-dependent and not byte-identical regressions.](../output/figures/longmemeval.png){#fig:longmemeval width=70%}

## Observed bottleneck in context narrowing {#sec:eval-bottleneck}

The sharp decline in [@sec:eval-real] motivates a diagnostic comparison — swap the lexical lane for a
learned dense retriever. The committed aggregate is narrower: over {{RESULT_BN_N}}
questions, full-haystack ranking hit@10 is {{RESULT_BN_RANKING_RECALL}}, while the
optional per-mode learned-embedder probe is only cited when
`ranking_recall_by_mode.available` is true in the regenerated bottleneck artifact. On
{{RESULT_LME_BENCHMARK}}, retrieval *ranking* is not the largest observed loss in the retained aggregate.
The loss is upstream in this retained slice: over {{RESULT_BN_N}} questions, full-haystack
ranking recall is {{RESULT_BN_RANKING_RECALL}} while the **Inspector's** window recall —
whether its grep-based narrowing even surfaces a gold line for the Retriever to rank —
is only {{RESULT_BN_INSPECTOR_RECALL}}. In this slice, the RLM-style narrowing
accounts for the larger observed loss before ranking can operate.

So the fix is to relax the narrowing, and [@fig:bottleneck] measures it. Raising the
Inspector's `max_windows` from {{RESULT_BN_MAXWIN_LO}} to {{RESULT_BN_MAXWIN_HI}} lifts
extractive grounding from {{RESULT_BN_GROUNDING_LO}} to {{RESULT_BN_GROUNDING_HI}} — but
extractive *accuracy* barely moves, consistent with the default extractive responder's
answer-generation limitation even when evidence is shown. The two interventions
compose in this retained subset: with a real Reasoner
(`{{RESULT_BN_MODEL}}`), the same widening converts recovered recall into accuracy,
**raising it ~{{RESULT_BN_NEURAL_RATIO}}×, from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_NEURAL_ACC_HI}}**.
(This analysis uses a {{RESULT_BN_N_NEURAL}}-question neural subset, so its absolute
values sit slightly below the {{RESULT_LME_N_NEURAL}}-question headline of
[@sec:eval-real]; the *relative* gain from relaxing the narrowing is the claim.)
The actionable result is bounded: THALIA's default `max_windows={{CONFIG_MAX_WINDOWS}}`
is tuned for compact contexts and produced the largest observed loss in this retained
long-context diagnostic slice;
widening the Inspector *and* using a neural Reasoner is the configuration associated
with higher scores in this retained benchmark slice. That
the *surrogate* semantic lane did not move recall here — while a learned dense embedder
remains the right tool for paraphrase coverage ([@sec:eval-learned]) — is itself the
finding: we localised the bottleneck rather than assuming it.

We do not stop at the diagnosis. The fix it implies — that the narrowing budget should
*scale with the haystack* rather than stay fixed — ships as an **adaptive Inspector**
(`adaptive_windows`, opt-in, `src/stages/inspector.py`): it sets `max_windows` to
roughly one window per {{CONFIG_ADAPTIVE_RATIO}} session lines, floored at the
compact-context default. On
the {{RESULT_NUM_EXAMPLES}}-example synthetic set this is a **bit-for-bit no-op** — a
compact context never exceeds the floor, so determinism and every headline number are
preserved — yet on {{RESULT_LME_BENCHMARK}} the fixed adaptive policy is associated
with the observed recall in this retained slice,
lifting observed neural accuracy from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_ADAPTIVE_ACC}}:
the manually selected `max_windows={{RESULT_BN_MAXWIN_HI}}` result ([@fig:bottleneck], star);
the adaptive policy reaches its own observed value without selecting that sweep maximum
as an input. The diagnosis becomes a one-flag method.

![{{RESULT_LME_BENCHMARK}} bottleneck diagnostic on {{RESULT_BN_N}} ranking/configuration observations and {{RESULT_BN_ACCOUNTING_NEURAL_N}} neural question-configuration rows ({{RESULT_BN_N_NEURAL}} questions per neural sweep setting): an Inspector `max_windows` sweep compares extractive grounding and neural token-F1 accuracy on the retained external benchmark subset, while the star marks the opt-in adaptive policy. Full-haystack ranking recall is {{RESULT_BN_RANKING_RECALL}} and Inspector window recall is {{RESULT_BN_INSPECTOR_RECALL}}. The unit is a benchmark question or declared configuration observation; intervals are descriptive where shown, model values depend on `{{RESULT_BN_MODEL}}`, and the observed loss is localised to context narrowing in this retained slice rather than establishing a universal causal ranking claim.](../output/figures/bottleneck.png){#fig:bottleneck width=70%}
