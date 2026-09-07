# AGENTS.md — thalia/skills/thalia-session

Project skill packaging for the thalia-session stage. `SKILL.md` is the entry point:
Persistent multi-turn conversation surface: wraps AutoHarness with disk-backed SQLite episodes and consolidated MEMORY.md read at start / written on consolidation.
Load the skill when working on that stage; the stage implementation lives
under `src/`.