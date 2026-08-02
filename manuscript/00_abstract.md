# Abstract {#sec:abstract}

<style>
body {
  max-width: 1120px !important;
  padding: 10px 14px !important;
}
a,
.toc a {
  color: #b00020 !important;
}
</style>

**THALIA** — Typed Harness with Analytical Lexical-Integrated Architecture — is an
executable research harness for long-context memory systems. We implement a
{{CONFIG_NUM_STAGES}}-stage pipeline that makes retrieval, context narrowing,
answer generation, memory mutation, and configuration search explicit. Every
stage has a typed input/output contract, a runnable implementation, an evidence
trace, and a declared scope. The Inspector selects line-addressed context; the
Retriever ranks and fuses lexical and surrogate-semantic evidence; the Reasoner
produces a cited answer; the Memory Gate appends raw episodes before gated
consolidation; and the Compiler searches a bounded configuration surface.

The core is deterministic and offline: BM25/grep, hashing-based retrieval,
weighted reciprocal-rank fusion, real SQLite state, and bounded MIPRO/GEPA-style
search run without network calls or mocks. A one-method LM protocol and a stable
embedding interface provide explicit replacement lanes for genuine DSPy/neural
backends and learned retrieval. Source-bound variables, a claim ledger, formal
anchors, figure registries, and rendering checks connect implementation evidence
to the manuscript.

We evaluate the harness in separate evidence tiers. On the fixed
{{RESULT_NUM_EXAMPLES}}-example LongMemEval-style diagnostic set, the default
configuration reaches composite {{RESULT_COMPOSITE}} (answer token-F1
{{RESULT_ACCURACY}}, citation-support proxy {{RESULT_GROUNDING}}, efficiency
{{RESULT_EFFICIENCY}}). The {{RESULT_NUM_CANDIDATES}}-candidate MIPRO-style search
ties on this easy set, so its primary result is a complete, auditable trace and
tie rule. A genuine `dspy.Predict`/`dspy.BootstrapFewShot` path is exercised. In
the retained {{RESULT_NEURAL_N}}-example local comparison, replacing the
extractive Reasoner with {{RESULT_NEURAL_MODEL}} changes mean token-F1 from
{{RESULT_EXTRACTIVE_MEAN_F1}} to {{RESULT_NEURAL_MEAN_F1}} (paired difference
{{RESULT_NEURAL_PAIRED_DELTA}}, {{CONFIG_CI_LEVEL}}% descriptive interval
{{RESULT_NEURAL_PAIRED_CI}}). On the external {{RESULT_LME_BENCHMARK}} transfer
slice, extractive and neural answer token-F1 are {{RESULT_LME_EXT_ACC}} and
{{RESULT_LME_NEURAL_ACC}}, respectively, with {{CONFIG_CI_LEVEL}}% descriptive
bootstrap intervals. In the {{RESULT_BN_N}}-question bottleneck slice, ranking
recall is {{RESULT_BN_RANKING_RECALL}} while Inspector recall is
{{RESULT_BN_INSPECTOR_RECALL}}; an adaptive context policy changes neural answer
token-F1 from {{RESULT_BN_NEURAL_ACC_LO}} to {{RESULT_BN_ADAPTIVE_ACC}} while
compact-context outputs remain unchanged.

The paper makes three design contributions: a typed and inspectable contract
graph; an evidence-preserving runtime that localizes retrieval, narrowing, and
memory failures; and a source-bound evaluation layer that can be regenerated and
extended across models, embeddings, and context policies. The results support
method integrity and diagnostic localization within the declared tiers. Token-F1,
citation-support overlap, source-index alignment, and reachability remain
operational diagnostics. Sentence-level factuality, usefulness, calibration,
causal robustness, general model competence, and production reliability require
the separate expert-rating and operational protocols specified in the repository.

**Keywords:** declarative pipelines, recursive language models, agentic search,
reciprocal rank fusion, episodic memory, gated consolidation, compiler
optimization, reproducible research.
