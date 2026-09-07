# AGENTS.md — thalia/skills/thalia-retriever

Project skill packaging for the thalia-retriever stage. `SKILL.md` is the entry point:
Lexical-first hybrid retriever (Stage 1): BM25/grep + semantic lanes, optional query expansion, weighted RRF fusion, MMR re-ranking, and delivery budgeting.
Load the skill when working on that stage; the stage implementation lives
under `src/`.