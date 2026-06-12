# Alignment with Active Inference {#sec:active_inference}

The harness has natural correspondences with the Free Energy Principle and Active
Inference [@friston2010free], relevant to the broader research programme at the
intersection of Active Inference, computational biology, and cognitive security.
This mapping is **interpretive scaffolding, not a claim**: none of the paper's
evaluation results ([@sec:evaluation]) depend on it, and it is offered to connect
the architecture to a research lineage, not to assert formal equivalence (any
pipeline can be relabelled in this vocabulary, so the correspondence is suggestive,
not falsifiable). With that caveat stated plainly:

- **Perception — the Inspector.** Selective attention over external context is a
  form of active sampling: the RLM-style grep/peek loop chooses which slices of
  the environment to bring into the inference, analogous to epistemic foraging
  that reduces uncertainty about hidden causes ([@sec:stage-inspector]).

- **Action — the Reasoner and tool dispatch.** The ReAct read→integrate→retry loop
  selects information-gathering and answer-producing actions, analogous to
  policy selection under expected free energy: pragmatic value (answer the query)
  traded against epistemic value (gather more evidence) ([@sec:stage-reasoner]).

- **Memory — the Memory Gate.** The episodic-first architecture mirrors the
  distinction between fast episodic (hippocampal) traces and slow consolidated
  semantic memory. The consolidation gate is a precision-weighting safeguard: it
  prevents low-precision derived beliefs from overwriting high-precision veridical
  evidence, which is exactly the failure the consolidation-fault study documents
  ([@sec:stage-memory], [@zhang2026memory]).

- **Learning — the Compiler.** MIPRO search and GEPA reflective evolution minimise
  a metric (expected loss) over a training distribution — a machine-learning
  instantiation of the learning/inference duality in which slow parameter learning
  improves fast inference ([@sec:stage-compiler]).

Of these, only the memory correspondence is load-bearing in the engineering: the
precision-weighting reading of the consolidation gate ([@zhang2026memory]) is what
the episodic-first invariant actually enforces and what
[@sec:val-memory] ablates. The other three are framing, and we treat them as such.
