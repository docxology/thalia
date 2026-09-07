# AGENTS.md — thalia/skills/thalia-memory-gate

Project skill packaging for the thalia-memory-gate stage. `SKILL.md` is the entry point:
Episodic-first memory gate (Stage 3): append-only SQLite (+FTS5) episode store; consolidates a MEMORY.md delta only on request and explicit criterion; never overwrites history.
Load the skill when working on that stage; the stage implementation lives
under `src/`.