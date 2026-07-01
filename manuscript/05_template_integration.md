# Integration with `docxology/template` {#sec:integration}

THALIA is built inside the `template/` reproducible-research substrate
[@aii2026template], which supplies its provenance and self-documentation layer.
Two integration points matter: the `AGENTS.md`/`SKILL.md` documentation duality
and the eight-stage build lifecycle.

## SKILL.md duality {#sec:integration-skill}

Each THALIA stage carries a machine-readable `SKILL.md` aligned with the Model
Context Protocol, so an agent can discover and invoke a stage's capability through
structured introspection rather than hallucinated API calls. For example,
`skills/thalia-inspector/SKILL.md` declares the Inspector's purpose, inputs,
outputs, invocation snippet, and constraints (never load full context; cap at
`max_windows` windows; grep patterns grounded in query terms). The same discipline
applies to the Retriever, Reasoner, Memory Gate, and Compiler skills.

## Build lifecycle mapping {#sec:integration-lifecycle}

The `template/` eight-stage build pipeline maps directly onto the harness's
compile-and-validate lifecycle:

| `template/` stage | THALIA equivalent |
|-------------------|------------------|
| Environment sanitization | Dependency lock + (optional) LM/API validation |
| Test execution (Zero-Mock) | Stage suite on real data + SQLite; {{CONFIG_COV_GATE}}% `src/` gate |
| Analysis script invocation | `run_harness_eval.py`, `run_compiler.py` |
| Pandoc/XeLaTeX rendering | Manuscript + figure generation |
| SHA-256 + steganographic hash | Compiled-config / artifact fingerprint |
| Structural validation | Signature schema validation (`Signature.validate_inputs`) |
| LLM-assisted review | GEPA trace-driven skill review (optional) |
| Provenance chain | Git-tracked compiled trace + generated tokens |

## What THALIA borrows and what it adds

THALIA borrows the Zero-Mock policy (no `MagicMock`; real computations and real
SQLite throughout `tests/`), the coverage gate (≥ {{CONFIG_COV_GATE}}% on `src/`), the thin
orchestrator pattern (scripts coordinate; `src/` implements), and deterministic
outputs with fixed structure. It adds the agentic-harness layer on top: typed
stage signatures, the lexical-anchored retrieval lane, the episodic-first memory
subsystem, and the bounded Compiler. The result is a harness whose
*behaviour is provable from its build*: a configuration drift, a deleted result,
or an out-of-sync manuscript number cannot reach a green build without a gate
flipping red first.
