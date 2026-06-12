# `data/` — advisory evidence registry

Declarative inputs for evidence-grounding validation. These files are validation
inputs only; they do not execute code or autonomous agents.

- [`claim_ledger.yaml`](claim_ledger.yaml) — registers manuscript numeric claims
  that are intentionally sourced from project code or generated artifacts, with the
  source path, tier (`project_source` / `generated_metric` / `manuscript_claim`),
  and the artifact that backs each value.

## Committed aggregate measurements (`data/*.json`)

These small JSON files are **committed** measurement aggregates from the gated
experiments. They are the recorded outputs that the figures (`scripts/generate_figures.py`)
and manuscript tokens (`src/manuscript_variables.py`) read, so the manuscript renders
and the integrity tests pass on a fresh clone without re-running Ollama or downloading
the benchmark. Each is regenerable via its recorder script:

- `neural_eval.json` — extractive-vs-neural token-F1 (`scripts/run_neural_eval.py`, needs Ollama)
- `learned_retrieval.json` — learned dense embedder vs surrogate (`scripts/run_learned_retrieval.py`, needs Ollama)
- `injection_eval.json` — context-poisoning resistance (`scripts/run_injection_probe.py`)
- `longmemeval_results.json` — real LongMemEval_S accuracy/grounding + CIs (`scripts/run_longmemeval.py`)
- `longmemeval_bottleneck.json` — bottleneck localisation + adaptive fix (`scripts/run_longmemeval_bottleneck.py`)

The 277 MB benchmark itself (`data/longmemeval/longmemeval_s.json`) is **gitignored**
and fetched with `scripts/get_longmemeval.sh`. By contrast, the per-run artifacts
under `output/data/` (`eval_results.json`, `compile_result.json`,
`manuscript_variables.json`) are regeneratable and **never committed**. See
[`AGENTS.md`](AGENTS.md).
