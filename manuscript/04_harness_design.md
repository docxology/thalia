# Auto-Harness Design {#sec:harness_design}

ATLAS is organised around {{CONFIG_NUM_STAGES}} functional stages. Four are
runtime stages composed by `AutoHarness` (`src/harness.py`); the fifth, the
Compiler, operates on the harness offline. Each stage is a
`src.module.Module` with a declarative `src.signatures.Signature` contract. The
end-to-end flow:

```text
session history + query
  ─► Stage 0  Inspector    RLM-style context narrowing  (peek → grep → windows)
  ─► Stage 1  Retriever    lexical-first hybrid + weighted RRF + budgeting
  ─► Stage 2  Reasoner     typed reasoning; CoT or ReAct; typed citations
  ─► Stage 3  MemoryGate   always append raw episode; gated consolidation
  ─► HarnessOutput
  ╌► Stage 4  Compiler     (offline) MIPRO search + GEPA reflective evolution
```

The language model is abstracted behind a one-method protocol
(`src.module.LMClient.complete`), and the default `ExtractiveLM` returns the
evidence line with maximal lexical overlap with the question. Every stage below is
therefore deterministic and testable without a network.

The design is deliberately conservative about where judgment can enter. Stages
0–1 are retrieval and filtering functions; Stage 2 is the only possible
language-model boundary; Stage 3 is a storage and consolidation policy; Stage 4
is an offline optimizer. This separation lets the evaluation attribute failures:
an absent citation is a retrieval/Inspector problem, an unsupported answer is a
Reasoner problem, a spurious MEMORY.md change is a Memory Gate problem, and a
non-reproducible compiled configuration is a Compiler problem. The manuscript,
tests, and dashboard all report these same typed objects rather than post-hoc
natural-language summaries.

This spine preserves the stable auto-harness design anchor. The detailed method contract, stage-by-stage design, formalism, added-method diagnostics, and implementation traceability now live in adjacent `04a_` through `04c_` modules.

Modular harness-design files:

- `04a_harness_method_contract_and_stage_flow.md`
- `04b_harness_formalism_and_added_methods.md`
- `04c_harness_implementation_traceability.md`
