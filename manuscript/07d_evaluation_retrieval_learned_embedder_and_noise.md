# Evaluation: Retrieval, Learned Embedder, and Noise {#sec:evaluation-retrieval-learned-noise}

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
deliberate: THALIA's semantic lane is a *deterministic hashing-embedding surrogate*
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
semantic lane? THALIA answers the first question locally and leaves the second as a
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
