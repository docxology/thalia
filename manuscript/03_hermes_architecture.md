# Hermes Agent Architecture {#sec:hermes}

THALIA uses the Hermes Agent ecosystem [@nous2026hermes; @nous2026selfevolution]
as the concrete engineering pattern that binds the four foundations together. Two
sub-systems matter: prompt assembly with a frozen memory snapshot, and the
DSPy + GEPA self-evolution loop.

## Prompt assembly and the frozen snapshot {#sec:hermes-prompt}

Hermes assembles its system prompt as a strictly-ordered stack: agent identity,
tool-aware guidance, optional static blocks, a **frozen MEMORY.md snapshot**
(cross-session durable facts, injected read-only at session start), a frozen
USER.md snapshot, a compact skills index, context files, and platform/timestamp
hints.

The critical property is that memory snapshots are **frozen at session start** and
not mutated mid-conversation. Mid-session writes update disk state, but the
assembled prompt prefix stays stable for provider-side prefix caching. This
directly implements the consolidation-safety principle of [@zhang2026memory]: the
raw episodic store (SQLite/FTS5) is kept separate from the consolidated snapshot,
and the snapshot the model reasons against never changes underneath it.

**THALIA adoption.** `src.signatures.MemorySnapshot` is a frozen dataclass
injected into the Reasoner as read-only `memory_context`; the Memory Gate writes
raw episodes to `EpisodicStore` and only updates its `memory_md` through gated
consolidation. The snapshot the Reasoner sees within a turn is immutable
([@sec:stage-reasoner], [@sec:stage-memory]).

## Self-evolution: DSPy + GEPA {#sec:hermes-gepa}

The `hermes-agent-self-evolution` project [@nous2026selfevolution] connects DSPy
and GEPA (Genetic-Pareto prompt evolution) to automatically evolve skills, tool
descriptions, system-prompt sections, and code, in a five-phase roadmap:

| Phase | Target | Engine |
|-------|--------|--------|
| 1 | Skill files (`SKILL.md`) | DSPy + GEPA |
| 2 | Tool descriptions | DSPy + GEPA |
| 3 | System-prompt sections | DSPy + GEPA |
| 4 | Tool implementation code | Darwinian evolver |
| 5 | Continuous improvement loop | Automated pipeline |

GEPA reads **execution traces** to understand *why* something failed — not merely
that it failed — then proposes targeted improvements. Every evolved variant must
pass hard gates before merge: the full test suite (100%), size limits (skills
≤ 15 KB, tool descriptions ≤ 500 chars), caching compatibility (no mid-conversation
changes), semantic preservation, and human review.

**THALIA adoption.** The Compiler stage embodies both engines. The MIPRO-style
search (`src/compiler/mipro.py`) evaluates configurations against the harness
metric; the GEPA-style optimizer (`src/compiler/gepa.py`) reflects on the weakest
metric component of an evaluation report and applies a targeted, bounded mutation,
recording the full trace. The size/non-empty constraints on evolved skill
artifacts are enforced by `check_skill_constraints` (15 KB budget mirrored from
the Hermes roadmap), and an optional `to_dspy_signature` bridge produces a real
`dspy.Signature` when DSPy is installed — gated so the deterministic core never
requires it ([@sec:stage-compiler]). With the `dspy` extra present, `src/dspy_runtime/`
goes further than the signature bridge: it runs a genuine `dspy.Predict` program and
a genuine `dspy.BootstrapFewShot` optimizer, both backed by the project's real
deterministic `ExtractiveLM` so the path stays offline and reproducible. The
`MIPRO`/`GEPA` compilers above are the project's own deterministic engine, distinct
from — and not a stand-in for — that real DSPy machinery; the headline evaluation
remains extractive-bounded either way.
