# `data/` — advisory evidence registry

Declarative inputs for evidence-grounding validation. These files are validation
inputs only; they do not execute code or autonomous agents.

- [`claim_ledger.yaml`](claim_ledger.yaml) — registers manuscript numeric claims
  that are intentionally sourced from project code or generated artifacts, with the
  source path, evidence tier, and artifact that backs each value. Current tiers
  distinguish `project_source`, `data_source`, `generated_metric`,
  `finite_synthetic`, `external_benchmark`, `external_benchmark_local_deterministic`,
  and `live_model`; the tier is part of the claim boundary, not a quality score.
  `scripts/z_generate_manuscript_variables.py` validates the source registry;
  `scripts/validate_artifacts.py` additionally checks safe artifact paths and
  declared JSON fields for generated numeric claims.

## Committed aggregate measurements (`data/*.json`)

These small JSON files are **committed** measurement aggregates from the gated
experiments. They are the recorded outputs that the figures (`scripts/generate_figures.py`)
and manuscript tokens (`src/manuscript_variables.py`) read, so the manuscript renders
and the integrity tests pass on a fresh clone without re-running Ollama or downloading
the benchmark. Each is regenerable via its recorder script:

- `neural_eval.json` — extractive-vs-neural token-F1 (`scripts/run_neural_eval.py`, needs Ollama)
- `learned_retrieval.json` — learned dense embedder vs surrogate (`scripts/run_learned_retrieval.py`, needs Ollama)
- `injection_eval.json` — context-poisoning resistance (`scripts/run_injection_probe.py`)
- `longmemeval_results.json` — external LongMemEval_S accuracy/grounding + CIs (`scripts/run_longmemeval.py`)
- `longmemeval_bottleneck.json` — bottleneck localisation + adaptive fix (`scripts/run_longmemeval_bottleneck.py`)

## THALIA v2 campaign lanes

Raw rows and atomic checkpoints live outside the repository at
`/Volumes/blue/data/thalia_campaigns`. A campaign report is promotable only when
every requested row is evaluated and every tier carries the benchmark SHA-256,
model digest, generation options, selected question IDs, config fingerprint, and
code fingerprint. Partial campaigns never replace the retained v1 aggregates.

- `scripts/run_research_campaign.py` — nested Gemma 100/250/500 and Hermes 100 LongMemEval cohorts.
- `scripts/run_bottleneck_campaign.py` — matched 100-question Gemma Inspector policies plus separate lexical/dense/hybrid ranking diagnostics.
- `scripts/run_seed_sensitivity.py` — ten-seed finite synthetic sensitivity lane; it does not replace the five-seed headline.
- `scripts/run_compiler_generalization.py` — held-out MIPRO-/GEPA-style validation;
  its sample accounting includes both final method rows and every compiler
  candidate-training evaluation.

The 277 MB benchmark itself (`data/longmemeval/longmemeval_s.json`) is **gitignored**
and fetched with `scripts/get_longmemeval.sh`. By contrast, the per-run artifacts
under `output/data/` (`eval_results.json`, `compile_result.json`,
`manuscript_variables.json`) are regeneratable and **never committed**. See
[`AGENTS.md`](AGENTS.md).
