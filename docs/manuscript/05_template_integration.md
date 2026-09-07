# Reproducible Research Integration: `docxology/template` Build Lifecycle {#sec:integration}

THALIA is built inside the `template/` reproducible-research substrate
[@friedman2026template], which supplies its provenance and self-documentation layer.
Two integration points matter: the `AGENTS.md`/`SKILL.md` documentation duality
and the eight-stage build lifecycle.

## Documentation Duality: README.md, AGENTS.md, and SKILL.md {#sec:integration-skill}

Each THALIA stage carries a machine-readable `SKILL.md` aligned with the Model
Context Protocol, so an agent can discover and invoke a stage's capability through
structured introspection with explicit API contracts. For example,
`skills/thalia-inspector/SKILL.md` declares the Inspector's purpose, inputs,
outputs, invocation snippet, and constraints (the Inspector loads selected
windows; it caps delivery at `max_windows` windows; grep patterns are grounded in
query terms). The same discipline
applies to the Retriever, Reasoner, Memory Gate, and Compiler skills.

## Mapping the Eight-Stage Build Lifecycle {#sec:integration-lifecycle}

The `template/` eight-stage build pipeline maps directly onto the harness's
compile-and-validate lifecycle:

| `template/` stage | THALIA equivalent |
|-------------------|------------------|
| Environment sanitization | Dependency lock + (optional) LM/API validation |
| Test execution (Zero-Mock) | Stage suite on generated examples + real SQLite; {{CONFIG_COV_GATE}}% `src/` gate |
| Analysis script invocation | `run_harness_eval.py`, `run_compiler.py` |
| Pandoc/XeLaTeX rendering | Manuscript + figure generation |
| SHA-256 + steganographic hash | Compiled-config / artifact fingerprint |
| Structural validation | Signature schema validation (`Signature.validate_inputs`) |
| LLM-assisted review | GEPA trace-driven skill review (optional) |
| Provenance chain | Git-tracked compiled trace + generated tokens |

## Inherited Infrastructure and THALIA Extensions

THALIA borrows the Zero-Mock policy (no `MagicMock`; real computations and real
SQLite throughout `tests/`), the coverage gate (≥ {{CONFIG_COV_GATE}}% on `src/`), the thin
orchestrator pattern (scripts coordinate; `src/` implements), and deterministic
outputs with fixed structure. It adds the agentic-harness layer on top: typed
stage signatures, the lexical-anchored retrieval lane, the episodic-first memory
subsystem, and the bounded Compiler. The result is a harness whose
*behaviour is auditable from its build*: configuration drift, deleted results, and
out-of-sync manuscript numbers trigger a failing gate before a green build. The
build establishes executable traceability and artifact
freshness. Model competence and scientific generalization require separate
evidence.
