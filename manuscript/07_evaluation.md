# Evaluation {#sec:evaluation}

The evaluation is deterministic and offline: a fixed LongMemEval-style dataset, a
deterministic extractive language model, and a composite metric computed in pure
Python. The goal is to validate the *machinery* and to be explicit about what a
deterministic local harness can and cannot demonstrate.

This spine preserves the stable evaluation anchor and the two scope boundaries called out by the project guide. Detailed evidence now lives in adjacent `07a_` through `07e_` files.

The context-poisoning module reports exact cases, not population rates; the required phrasing that the answer keeps the true source in its cited evidence remains part of the evaluation contract. The optional neural rows appear only when a real local model is available.

Modular evaluation files:

- `07a_evaluation_setup_headline_and_scaling.md`
- `07b_evaluation_real_benchmark_and_bottleneck.md`
- `07c_evaluation_baseline_neural_and_context_poisoning.md`
- `07d_evaluation_retrieval_learned_embedder_and_noise.md`
- `07e_evaluation_compiler_added_methods_and_summary.md`
