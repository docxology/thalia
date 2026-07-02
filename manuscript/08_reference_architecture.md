# Reference Architecture Summary {#sec:reference_architecture}

## Design principles encoded {#sec:ref-principles}

| Principle | Source | Implementation in THALIA |
|-----------|--------|-------------------------|
| Declarative typed signatures | DSPy [@khattab2023dspy] | Every stage is a `Signature` with typed fields (`src/signatures/`) |
| Context as inspectable external state | RLMs [@zhang2025rlm] | `REPLEnvironment`; grep before any neural call (`src/stages/inspector.py`) |
| Episodic evidence preservation | Memory faults [@zhang2026memory] | Append-only SQLite store, no overwrite (`src/memory/episodic_store.py`) |
| Gated consolidation | Memory faults [@zhang2026memory] | Both flag and criterion required (`src/memory/consolidation.py`) |
| Lexical-first retrieval | Agentic search [@sen2026grep] | BM25/grep primary lane (`src/retrieval/lexical.py`) |
| Weighted rank fusion | Agentic search [@sen2026grep]; RRF [@cormack2009rrf] | `rrf_fuse`, lexical {{CONFIG_LEXICAL_WEIGHT}} / semantic {{CONFIG_SEMANTIC_WEIGHT}} (`src/retrieval/fusion.py`) |
| Sparse context budgeting | Agentic search [@sen2026grep] | `delivery_mode`; file-based overflow (`src/stages/retriever.py`) |
| Frozen memory snapshot | Hermes [@nous2026hermes] | Read-only `MemorySnapshot` into the Reasoner (`src/signatures/payloads.py`) |
| Self-evolving skills | Hermes + GEPA [@nous2026selfevolution] | `MIPROCompiler`, `GEPAOptimizer`, `check_skill_constraints` (`src/compiler/`) |
| Reproducible provenance | `template/` [@aii2026template] | Zero-Mock tests, {{CONFIG_COV_GATE}}% gate, generated tokens |
| `AGENTS.md`/`SKILL.md` duality | `template/` [@aii2026template] | Per-stage `SKILL.md` for hallucination-free discovery |
| Operable + configurable | this work | File/env/flag config, real LM adapters, persistent session, CLI, composable Pipeline ([@sec:operability]) |
| Adaptive retrieval + memory recall | this work | PRF query expansion, recency weighting, read-only episodic recall ([@sec:added-methods]) |
| Resource safety + serialisation | this work | Context managers, `to_yaml`/`from_yaml`, `to_dict`, `py.typed` ([@sec:operability]) |

## File structure {#sec:ref-files}

```text
thalia/
+-- AGENTS.md / README.md            # machine + human entry points
+-- pyproject.toml                   # pytest/coverage config, deps
+-- config/harness.yaml              # canonical loadable harness configuration
+-- domain_profile.yaml              # advisory research-domain overlay
+-- experiment_plan.yaml             # deterministic experiment declaration
+-- data/claim_ledger.yaml           # sourced numeric-claim registry
+-- src/
|   +-- signatures/                  # framework, payloads, stage contracts
|   +-- routing.py                   # classify_task
|   +-- evaluation/                  # dataset, experiments, run_full_eval bundle
|   +-- module.py                    # Module / Prediction / LMClient / ExtractiveLM
|   +-- config.py                    # HarnessConfig + load/save/env overrides
|   +-- llm.py                       # real LM adapters (CallableLM, OllamaLM)
|   +-- harness.py                   # AutoHarness (composes the four stages)
|   +-- recall.py                    # read-only memory recall (episodic + MEMORY.md)
|   +-- session.py                   # persistent multi-turn Session
|   +-- cli.py                       # query CLI (run_query, arg parsing, Inspector diagnostics)
|   +-- demo.py                      # deterministic demo artifact builder
|   +-- provenance.py                # verification, figure, and artifact registries
|   +-- figures.py                   # deterministic figure generators
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
+-- manuscript/                      # this document (sections 00-11, 99) + config/preamble/refs
```

## Stage-to-signature-to-skill map {#sec:ref-map}

| Stage | Module | Signature | Skill |
|-------|--------|-----------|-------|
| 0 Inspector | `src/stages/inspector.py` | `InspectorSignature` | `skills/thalia-inspector` |
| 1 Retriever | `src/stages/retriever.py` | `RetrieverSignature` | `skills/thalia-retriever` |
| 2 Reasoner | `src/stages/reasoner.py` | `ReasonerSignature` | `skills/thalia-reasoner` |
| 3 Memory Gate | `src/stages/memory_gate.py` | `MemoryGateSignature` | `skills/thalia-memory-gate` |
| 4 Compiler | `src/compiler/` | — (operates on configs) | `skills/thalia-compiler` |
