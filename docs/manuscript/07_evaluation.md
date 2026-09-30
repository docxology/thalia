# Evaluation: Evidence Tiers, Estimands, and Scope {#sec:evaluation}

The evaluation uses distinct evidence tiers. A fixed
LongMemEval-style dataset, a deterministic extractive language model, and a
composite metric computed in pure Python provide the reproducible contract tier.
Recorded Ollama/OpenRouter rows and the external LongMemEval slice provide
model-dependent transfer diagnostics. The goal is to validate the *machinery* and
state the estimand and evidence boundary for each tier.

This spine preserves the stable evaluation anchor and the two scope boundaries called out by the project guide. The renderer places the adjacent `07a_` through `07e_` files beneath this heading as evaluation subsections, so the table of contents presents one coherent evaluation branch.

The context-poisoning module reports exact cases and finite-set rates; these are
exact cases, not population rates. Its legacy `harness_auditable` outcome only
records whether a cited excerpt lexically contains the supplied gold value; it is
a cited-excerpt/source-exposure proxy, not a recoverable source record or
claim-level auditability test. The optional neural rows appear only when
a real model is available. Model-quality status requires a dedicated quality
protocol. Usefulness, factuality, calibration, and preference remain distinct
constructs from execution integrity and lexical overlap [@min2023factscore].

Modular evaluation files:

- `07a_evaluation_setup_headline_and_scaling.md`
- `07b_evaluation_real_benchmark_and_bottleneck.md`
- `07c_evaluation_baseline_neural_and_context_poisoning.md`
- `07d_evaluation_retrieval_learned_embedder_and_noise.md`
- `07e_evaluation_compiler_added_methods_and_summary.md`
