# AGENTS.md — thalia/skills

Project-scoped agent skills for the THALIA harness, one per stage:
`thalia-inspector` (Stage 0, context inspection), `thalia-retriever`
(Stage 1, hybrid retrieval), `thalia-reasoner` (Stage 2, typed
reasoning), `thalia-memory-gate` (Stage 3, episodic memory), and
`thalia-compiler` (Stage 4, trace evolution), plus `thalia-pipeline`
(the composable stage chain) and `thalia-session` (persistent
conversation surface). Each subdir has a SKILL.md entry point; the
implementations live under `src/`.