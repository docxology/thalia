# THALIA Harness: Architecture and Executable Contract {#sec:harness_design}

THALIA is organised around {{CONFIG_NUM_STAGES}} functional stages. {{CONFIG_NUM_RUNTIME_STAGES}} are
runtime stages composed by `AutoHarness` (`src/harness.py`); the fifth, the
Compiler, operates on the harness offline. Each stage is a
`src.module.Module` with a declarative `src.signatures.Signature` contract. The
end-to-end flow:

```text
session history + query
  -> Stage 0  Inspector    RLM-style context narrowing  (peek -> grep -> windows)
  -> Stage 1  Retriever    lexical-first hybrid + weighted RRF + budgeting
  -> Stage 2  Reasoner     single-pass reasoning or ReAct-style deterministic read-integrate; typed citations
  -> Stage 3  MemoryGate   always append raw episode; gated consolidation
  -> HarnessOutput
  ~> Stage 4  Compiler     (offline) MIPRO search + GEPA reflective evolution
```

The language model is abstracted behind a one-method protocol
(`src.module.LMClient.complete`), and the default `ExtractiveLM` returns the
evidence line with maximal lexical overlap with the question. The deterministic
default path is therefore testable without a network; substituting a real model
creates a separate model-dependent evidence tier without changing the stage
contracts.

The design is deliberately conservative about where judgment can enter. Stages
zero and one are retrieval and filtering functions; Stage 2 is the language-model
boundary; Stage 3 is a storage and consolidation policy; Stage 4 is an offline
optimizer. This separation supports failure diagnosis: an absent citation points
to retrieval or Inspector reachability, an unsupported answer points to the
Reasoner or its metric, a spurious `MEMORY.md` change points to the Memory Gate,
and a non-reproducible compiled configuration points to the Compiler. These are
diagnostic attributions within the contract graph. Causal claims require a separate
intervention design. The manuscript, tests, and dashboard report the same typed evidence objects generated
from the contracts.

This spine preserves the stable auto-harness design anchor. The detailed method contract, stage-by-stage design, formalism, added-method diagnostics, and implementation traceability now live in adjacent `04a_` through `04c_` modules.

![Schematic lifecycle with no empirical unit, sample size, uncertainty interval, or model comparison. Every raw episode is appended to SQLite EpisodicStore; the dual-key gate controls whether a derived MEMORY.md delta is written, preserving the source turn.](../../output/figures/memory_lifecycle.png){#fig:memory_lifecycle width=80%}

![Schematic GEPA-style audit loop with no empirical unit, sample size, uncertainty interval, or external model dependence. The Compiler evaluates a configuration, identifies the weakest metric component, applies a bounded mutation, and records the complete trace as described in [@sec:eval-compiler].](../../output/figures/gepa_evolution_loop.png){#fig:gepa_evolution_loop width=80%}

Modular harness-design files:

- `04a_harness_method_contract_and_stage_flow.md`
- `04b_harness_formalism_and_added_methods.md`
- `04c_harness_implementation_traceability.md`
