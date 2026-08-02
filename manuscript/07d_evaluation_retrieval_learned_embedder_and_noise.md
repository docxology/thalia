## Retrieval Representations and Distractor-Noise Diagnostics {#sec:evaluation-retrieval-learned-noise}

### Lexical, Surrogate-Semantic, and Hybrid Retrieval {#sec:eval-retrieval}

[@fig:retriever_comparison] compares lexical-only, semantic-only, and hybrid
composites at the **default (slack) retrieval budget** (`top_k={{CONFIG_TOP_K}}`,
`max_evidence={{CONFIG_MAX_EVIDENCE}}`). On the clean compact dataset all three
coincide (lexical {{RESULT_LEXICAL_COMPOSITE}}, semantic
{{RESULT_SEMANTIC_COMPOSITE}}, hybrid {{RESULT_HYBRID_COMPOSITE}}): the gold
evidence is unambiguous, so every lane resolves it and the fused result is
identical. The deterministic tie-break selects {{RESULT_BEST_MODE}} as the best
single mode. Retrieval choice is therefore equivalent in the slack-budget regime;
the tight-budget sweeps below expose the regime in which evidence selection can
separate methods. The ablation, MMR, and RRF-weight figures use
`top_k={{CONFIG_TIGHT_TOP_K}}` and `max_evidence={{CONFIG_TIGHT_MAX_EVIDENCE}}`,
the binding budget inherited from the noise study.

![Composite metric by retrieval mode on the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo at the default slack budget (top-k {{CONFIG_TOP_K}}, max-evidence {{CONFIG_MAX_EVIDENCE}}). The observation unit is one deterministic extractive-LM evaluation per example. All three lanes resolve the unambiguous gold evidence identically; the tight-budget, noise, and learned-embedder probes supply the separation diagnostics. Bars are finite descriptive values, and the semantic lane is a hashing surrogate.](../output/figures/retriever_comparison.png){#fig:retriever_comparison width=70%}

**Scope boundary (stated plainly).** The cited agentic-search study reports that
grep generally beats vector retrieval in its inline comparisons, with dependence
on harness and tool style [@sen2026grep]. That result belongs to a learned dense
retrieval setting. THALIA's local semantic lane is a *deterministic
hashing-embedding surrogate*: character n-grams are hashed into a fixed vector so
the complete harness can run offline with zero mocks. The surrogate measures
sub-word overlap and serves as a controlled lexical retrieval comparator. A
learned embedder fits the same `SemanticIndex` interface and supplies the separate
representation experiment required to compare learned dense retrieval with
lexical search.

The local experiment establishes three executable properties. Lexical retrieval,
the hashing lane, weighted RRF fusion, and budgeting compose deterministically. On
the clean comparison all three lanes coincide at {{RESULT_HYBRID_COMPOSITE}} because
the gold evidence is unambiguous. Session noise creates lane divergence
([@sec:eval-noise]), so the clean-set equality describes the slack-budget probe;
the broader hybrid effect remains an open representation-level question.

This boundary separates two estimands. The orchestration estimand asks whether a
typed harness can pass evidence through Inspector, Retriever, Reasoner, Memory
Gate, and Compiler while preserving provenance. The representation estimand asks
which embedding model improves retrieval for a declared probe family. THALIA
measures the first locally and exposes the second through a drop-in extension.

### Learned Embedder Versus Hashing Surrogate {#sec:eval-learned}

Behind the same `top_k(query, k)` interface as the hashing surrogate,
`src/retrieval/learned.py` wires a real neural sentence embedder
(`{{RESULT_EMBED_MODEL}}`, served locally through Ollama). We score recall@1 on
{{RESULT_NUM_PROBES}} **paraphrase** probes. Each query shares meaning with its
gold document while sharing little surface morphology; an example pair is
"access code for the network" and "the wifi password is …".
[@fig:paraphrase_retrieval] reports the result: the hashing surrogate retrieves
the gold document on {{RESULT_SURROGATE_RECALL}} of the probes (Wilson interval
{{RESULT_SURROGATE_RECALL_CI}}), while the learned embedder retrieves it on
{{RESULT_LEARNED_RECALL}} (Wilson interval {{RESULT_LEARNED_RECALL_CI}}). The
expanded probe is deliberately mixed: some paraphrases retain sub-word signal
for the surrogate, while the learned lane closes the remaining misses. The paired
Wilson and exact-binary accounting is recorded in the aggregate and describes this
synthetic probe family. Population retrieval rates require a broader sampling
frame.

The measurement is gated on a live embedding model and recorded to
`data/learned_retrieval.json` (regenerable via
`scripts/run_learned_retrieval.py`). The deterministic surrogate remains the
offline default, so the bit-reproducible core is unchanged. This is a
representation-level probe. Retrieval recall measures the upstream representation
and ranking step; answer quality also depends on how the generator uses surfaced
evidence [@lewis2020rag].

![Paired recall@1 for {{RESULT_NUM_PROBES}} synthetic paraphrase probes. Each point and bar records whether the gold document was retrieved by the deterministic hashing surrogate or the learned embedder (`{{RESULT_EMBED_MODEL}}` via Ollama); bars show Wilson intervals and the exact paired McNemar comparison reports p={{RESULT_EMBED_PAIRED_P}}. The observation unit is a probe, model provenance is recorded in `data/learned_retrieval.json`, and the panel supports a finite representation diagnostic. The hashing surrogate remains the offline default.](../output/figures/paraphrase_retrieval.png){#fig:paraphrase_retrieval width=60%}

### Retrieval Under Distractor Noise {#sec:eval-noise}

`noise_scaling_experiment` appends lexical false-friend lines (repeating query
tokens without the answer) and measures each mode at a tight retrieval budget,
following the design form of the cited noise study [@sen2026grep]. The composites
remain within the metric range as noise grows. Inspector grep anchoring filters
many false friends before retrieval. For this generated probe, the hashing
semantic lane remains above the lexical lane: at the noisiest setting
({{RESULT_NOISE_MAX_DISTRACTORS}} false-friend lines), the composites are
{{RESULT_NOISE_SEMANTIC}} and {{RESULT_NOISE_LEXICAL}}, respectively. The hashing
lane ranks the gold line first because its sub-word overlap survives the tight
budget; deterministic execution gives the same ordering on every run.

The gap is present at zero distractors. The binding budget creates the separation,
and the noise axis measures its stability. The slack-budget equality in
[@sec:eval-retrieval] and the tight-budget divergence therefore describe two
operating points of the same retrieval system. The ordering belongs to this
hashing surrogate and compact generated set. A learned dense retriever requires a
separate run under the same fixed probe, with model and host provenance recorded.
The cited lexical-versus-dense result remains external evidence [@sen2026grep].

The noise probe has a fixed, falsifiable contract: false-friend lines are appended
mechanically, the retrieval budget is fixed, and regression tests pin the measured
ordering. A learned embedder can replace the hashing lane and rerun the same probe;
the remaining stages and the metric contract remain unchanged.
