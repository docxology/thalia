# Reference Architecture: Design Principles and Repository Structure {#sec:reference_architecture}

## Executable Design Principles {#sec:ref-principles}

| Principle | Source | Implementation in THALIA |
|-----------|--------|-------------------------|
| Declarative typed signatures | DSPy [@khattab2023dspy] | Every stage is a `Signature` with typed fields (`src/signatures/`) |
| Evidence-conditioned generation | Retrieval-augmented generation [@lewis2020rag] | Retrieved evidence is a first-class input to the Reasoner with an explicit typed handoff |
| Context-use diagnosis | Long-context position sensitivity [@liu2024lost] | Inspector reachability and Reasoner answer quality are reported as separate observables |
| Factuality measurement boundary | Atomic factuality evaluation [@min2023factscore] | Token-F1 and citation overlap are labelled operational proxies; adjudicated truth requires the quality protocol |
| Expert-rater quality protocol | Atomic factuality, truthfulness, and evaluator-bias methodology [@min2023factscore; @lin2022truthfulqa; @zheng2023judging; @wang2024fairevaluators; @shi2025judges] | Separate correctness, completeness, faithfulness, usefulness, safety, and inter-rater agreement fields with blinded packets and fail-closed promotion; local LLM judging is an exploratory non-promotable diagnostic |
| Confidence and abstention | Calibration and selective prediction [@guo2017calibration; @geifman2017selective] | Brier/ECE/reliability/selective metrics use adjudicated outcomes; model text supplies no calibration label |
| Context as inspectable external state | RLMs [@zhang2025rlm] | `REPLEnvironment`; grep before any neural call (`src/stages/inspector.py`) |
| Episodic evidence preservation | Memory faults [@zhang2026memory] | Append-only SQLite store, no overwrite (`src/memory/episodic_store.py`) |
| Gated consolidation | Memory faults [@zhang2026memory] | Both flag and criterion required (`src/memory/consolidation.py`) |
| Lexical-first retrieval | Agentic search [@sen2026grep] | BM25/grep primary lane (`src/retrieval/lexical.py`) |
| Weighted rank fusion | Agentic search [@sen2026grep]; RRF [@cormack2009rrf] | `rrf_fuse`, lexical {{CONFIG_LEXICAL_WEIGHT}} / semantic {{CONFIG_SEMANTIC_WEIGHT}} (`src/retrieval/fusion.py`) |
| Sparse context budgeting | Agentic search [@sen2026grep] | `delivery_mode`; file-based overflow (`src/stages/retriever.py`) |
| Frozen memory snapshot | Hermes [@nous2026hermes] | Read-only `MemorySnapshot` into the Reasoner (`src/signatures/payloads.py`) |
| Self-evolving skills | Hermes + GEPA [@nous2026selfevolution] | `MIPROCompiler`, `GEPAOptimizer`, `check_skill_constraints` (`src/compiler/`) |
| Reproducible provenance | `template/` [@friedman2026template] | Zero-Mock tests, {{CONFIG_COV_GATE}}% gate, generated tokens |
| `AGENTS.md`/`SKILL.md` duality | `template/` [@friedman2026template] | Per-stage `SKILL.md` for hallucination-free discovery |
| Operable + configurable | this work | File/env/flag config, real LM adapters, persistent session, CLI, composable Pipeline ([@sec:operability]) |
| Independent production gate | this work | Latency, cost, privacy, pinning, rollback, monitoring, drift, and red-team acceptance remain separate from model quality |
| Adaptive retrieval + memory recall | this work | PRF query expansion, recency weighting, read-only episodic recall ([@sec:added-methods]) |
| Resource safety + serialisation | this work | Context managers, `to_yaml`/`from_yaml`, `to_dict`, `py.typed` ([@sec:operability]) |

## Repository Layout and Module Ownership {#sec:ref-files}

```text
thalia/
+-- AGENTS.md / README.md            # machine + reader entry points
+-- pyproject.toml                   # pytest/coverage config, deps
+-- config/harness.yaml              # canonical loadable harness configuration
+-- domain_profile.yaml              # advisory research-domain overlay
+-- experiment_plan.yaml             # deterministic experiment declaration
+-- data/claim_ledger.yaml           # sourced numeric-claim registry
+-- src/
|   +-- signatures/                  # framework, payloads, stage contracts
|   +-- routing.py                   # classify_task
|   +-- evaluation/                  # datasets, experiments, quality, production, bundles
|   +-- module.py                    # Module / Prediction / LMClient / ExtractiveLM
|   +-- config.py                    # HarnessConfig + load/save/env overrides
|   +-- llm.py                       # real LM adapters (CallableLM, OllamaLM)
|   +-- harness.py                   # AutoHarness (composes the {{CONFIG_NUM_RUNTIME_STAGES}} runtime stages)
|   +-- recall.py                    # read-only memory recall (episodic + MEMORY.md)
|   +-- session.py                   # persistent multi-turn Session
|   +-- cli.py                       # query CLI (run_query, arg parsing, Inspector diagnostics)
|   +-- demo.py                      # deterministic demo artifact builder
|   +-- provenance.py                # verification, figure, and artifact registries
|   +-- figures/                     # deterministic figure generators (plots, diagrams, manifest)
|   +-- dashboard.py                 # self-contained static HTML dashboard renderer
|   +-- invariants.py                # executable runtime invariants
|   +-- manuscript_variables.py      # generated-token map
|   +-- retrieval/                   # lexical / semantic / fusion / mmr / expansion
|   +-- stages/                      # inspector / retriever / reasoner / memory_gate
|   +-- memory/                      # episodic_store / consolidation
|   +-- compiler/                    # metrics / mipro / gepa
+-- skills/                          # thalia-{inspector,retriever,reasoner,memory-gate,compiler,session}/SKILL.md
+-- scripts/                         # thin orchestrators (eval, compile, figures, dashboard, preflight, tokens, run_query)
+-- tests/                           # Zero-Mock suite, one file per module
+-- docs/manuscript/                      # this document (sections 00-11, 99) + config/preamble/refs
```

## Stage, Signature, Skill, and Test Map {#sec:ref-map}

| Stage | Module | Signature | Skill |
|-------|--------|-----------|-------|
| 0 Inspector | `src/stages/inspector.py` | `InspectorSignature` | `skills/thalia-inspector` |
| 1 Retriever | `src/stages/retriever.py` | `RetrieverSignature` | `skills/thalia-retriever` |
| 2 Reasoner | `src/stages/reasoner.py` | `ReasonerSignature` | `skills/thalia-reasoner` |
| 3 Memory Gate | `src/stages/memory_gate.py` | `MemoryGateSignature` | `skills/thalia-memory-gate` |
| 4 Compiler | `src/compiler/` | — (operates on configs) | `skills/thalia-compiler` |
