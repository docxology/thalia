# AGENTS.md — thalia/skills/thalia-inspector

Project skill packaging for the thalia-inspector stage. `SKILL.md` is the entry point:
RLM-style context inspector (Stage 0): recursive partitioning + grep/regex over session history, emitting compact evidence windows. Never loads the full context into a neural call.
Load the skill when working on that stage; the stage implementation lives
under `src/`.