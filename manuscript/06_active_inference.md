# Active Inference Interpretation: Information, Belief, and Control {#sec:active_inference}

The harness has natural correspondences with the Free Energy Principle and Active
Inference [@friston2010free], relevant to the broader research programme at the
intersection of Active Inference, computational biology, and cognitive security.
This mapping is **interpretive scaffolding**. The paper's evaluation results
([@sec:evaluation]) stand on the executable contracts and recorded aggregates.
The correspondence connects the architecture to a research lineage. It supplies
suggestive framing; a falsifiable Active-Inference derivation would require a
separate generative model and objective.

- **Perception — the Inspector.** Selective attention over external context is a
  form of active sampling: the RLM-style grep/peek loop chooses which slices of
  the environment to bring into the inference, analogous to epistemic foraging
  that reduces uncertainty about hidden causes ([@sec:stage-inspector]).

- **Action — the Reasoner and tool dispatch.** The ReAct-style deterministic read→integrate→retry route
  selects information-gathering and answer-producing actions, analogous to
  policy selection under expected free energy: pragmatic value (answer the query)
  traded against epistemic value (gather more evidence) ([@sec:stage-reasoner]).

- **Memory — the Memory Gate.** The episodic-first architecture mirrors the
  distinction between fast episodic (hippocampal) traces and slow consolidated
  semantic memory. The consolidation gate is a precision-weighting safeguard: it
  prevents low-precision derived beliefs from overwriting retained evidence, an
  engineering response inspired by the consolidation-fault mode documented in
  the cited study
  ([@sec:stage-memory], [@zhang2026memory]).

- **Learning — the Compiler.** MIPRO search and GEPA reflective evolution optimise
  a declared metric over a finite evaluation set. This recalls the
  learning/inference distinction. The compiler optimizes configuration choices;
  parameter learning, an Active-Inference objective, and generalization require
  separate evidence ([@sec:stage-compiler]).

Of these, the memory correspondence is the load-bearing engineering link: the
precision-weighting reading of the consolidation gate ([@zhang2026memory]) is the
interpretive rationale for the episodic-first invariant and what
[@sec:val-memory] ablates. The other three remain framing elements in this
manuscript.
