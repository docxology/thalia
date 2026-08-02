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
- `integrity_advantage.json` — endpoint-level integrity-advantage screen with
  paired statistics, source/code hashes, native units, and promotion status
  (`scripts/analyze_integrity_advantage.py`; run after compiler generalization)
- `longmemeval_results.json` — external LongMemEval_S answer token-F1, citation-support proxy, session reachability, and CIs (`scripts/run_longmemeval.py`)
- `longmemeval_bottleneck.json` — separate evidence-exposure/citation-support/answer token-F1 bottleneck diagnostics plus adaptive fix (`scripts/run_longmemeval_bottleneck.py`)

The planned P0 provenance-confirmation lane intentionally has no committed
aggregate yet. Its raw condition rows, blinded expert packets, adjudications,
and report remain external until an accepted, hash-revalidated certificate is
explicitly promoted; see [`../docs/provenance_p0.md`](../docs/provenance_p0.md).

## THALIA v2 campaign lanes

Raw rows and atomic checkpoints live outside the repository at
`/Volumes/blue/data/thalia_campaigns`. A campaign report is promotable only when
every requested row is evaluated and every tier carries the benchmark SHA-256,
model digest, generation options, selected question IDs, config fingerprint, and
code fingerprint. A complete campaign can still remain an external evidence tier:
operational completeness is not model-quality validation, and live rows do not
replace the committed aggregates without an explicit promotion decision. Partial
campaigns never replace the committed aggregates.

- `scripts/run_research_campaign.py` — nested Gemma 100/250/500 and Hermes 100 LongMemEval cohorts.
- `scripts/run_bottleneck_campaign.py` — matched 100-question Gemma Inspector policies plus separate lexical/dense/hybrid ranking diagnostics.
- `scripts/run_seed_sensitivity.py` — ten-seed finite synthetic sensitivity lane with a distinct per-category design.
- `scripts/run_compiler_generalization.py` — held-out MIPRO-/GEPA-style validation;
  its sample accounting includes both final method rows and every compiler
  candidate-training evaluation.

## Model-quality evidence lane

`src/evaluation/quality.py`, `src/evaluation/quality_runner.py`, and
`src/evaluation/llm_judge.py` implement the separate quality-v3 schema and
external raw-output lane. The protocol in
`experiment_plan.yaml:model_quality` reserves a deterministic stratified pilot,
freezes the rubric and thresholds only after pilot review, and evaluates the
held-out confirmatory questions across Gemma/Hermes harness, full-context, and
oracle-evidence conditions. The publication mode uses two independently blinded
expert raters and expert adjudication with randomized, condition-neutral packets
and deterministic atomic claims. The local-LLM judging implementation remains an
engineering diagnostic and is rejected by promotion.

- `scripts/run_quality_campaign.py` — capture raw answers, evidence, confidence,
  latency, failures, and model/config/code provenance under
  `/Volumes/blue/data/thalia_quality`.
- `scripts/analyze_quality.py` — validate paired rows, annotations, adjudication,
  Brier/ECE calibration, reliability/selective metrics, agreement, safety, and
  threshold outcomes.
- `scripts/freeze_quality_protocol.py` — freeze a reviewed pilot protocol and
  record the pilot report digest; confirmation refuses an unfrozen protocol.
- `scripts/promote_quality_report.py` — promote only an untampered, explicitly
  accepted `passed`
  certificate into `data/quality_results.json`.

The v2 campaign report is immutable operational evidence and stores answer hashes
and automated metrics rather than retained answer text. It is not retrofitted with
judge labels and is never silently promoted as a model-quality result. A complete
quality run can still remain `complete_not_promoted`; production readiness is an
independent gate.

The 277 MB benchmark itself (`data/longmemeval/longmemeval_s.json`) is **gitignored**
and fetched with `scripts/get_longmemeval.sh`. By contrast, the per-run artifacts
under `output/data/` (`eval_results.json`, `compile_result.json`,
`manuscript_variables.json`) are regeneratable and **never committed**. See
[`AGENTS.md`](AGENTS.md).
