# Evaluation: Real Benchmark and Bottleneck Diagnosis {#sec:evaluation-real-benchmark-bottleneck}

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
