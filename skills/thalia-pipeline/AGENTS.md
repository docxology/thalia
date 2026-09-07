# AGENTS.md — thalia/skills/thalia-pipeline

Project skill packaging for the thalia-pipeline stage. `SKILL.md` is the entry point:
Composable stage chain exposing Inspector -> Retriever -> Reasoner -> Memory Gate as an explicit, inspectable Pipeline for variants and per-step inspection.
Load the skill when working on that stage; the stage implementation lives
under `src/`.