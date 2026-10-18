# `scripts/` — THALIA thin orchestrators

Scripts coordinate I/O and call `src/`; they contain no business logic. Each
Python script applies the identical path bootstrap documented in
[CONVENTIONS.md](CONVENTIONS.md), writes artifacts under `output/` (or a
caller-selected external root), and prints produced paths to stdout.

## Run-command shorthand

- `dev` = `uv run --project . --extra dev python scripts/<script>`
- `neural` = `uv run --project . --extra neural python scripts/<script>`
  (opt-in; needs a live local model or network and the `neural` extra)

## Inventory

| Script | Purpose | Delegates to | Run command |
|---|---|---|---|
| `00_preflight.py` | One harness turn plus core/DSPy/Ollama/model/benchmark/template status | `src.harness`, `src.dspy_runtime`, `src.llm`, `src.signatures` | `dev` |
| `analyze_integrity_advantage.py` | Endpoint-level integrity comparison report with paired statistics and native-unit promotion status | `src.evaluation.integrity_advantage` | `dev` |
| `analyze_production_readiness.py` | Aggregates service observations + control evidence into an independent readiness report | `src.evaluation.production_readiness` | `dev` |
| `analyze_provenance_p0.py` | Validates P0 ledgers, frozen rubric, packets, and statistics without promoting | `src.evaluation.provenance_p0` | `dev` |
| `analyze_quality.py` | Double-annotation/adjudication check and fail-closed quality report (agreement, calibration, paired comparisons) | `src.evaluation.quality` | `dev` |
| `build_dashboard.py` | `output/dashboard.html` static diagnostics dashboard; refreshes the artifact manifest last | `src.dashboard`, `src.evaluation`, `src.provenance` | `dev` |
| `build_provenance_p0_packets.py` | Builds blinded expert packets, separate blind key, and sealed blinding manifest from external raw rows | `src.evaluation.provenance_p0` | `dev` |
| `freeze_provenance_p0.py` | Freezes a reviewed P0 protocol with canonical digest and owner-declared margins | `src.evaluation.provenance_p0` | `dev` |
| `freeze_quality_protocol.py` | Records the post-pilot rubric, estimand, thresholds, and provenance before confirmation | `src.evaluation.quality` | `dev` |
| `generate_figures.py` | Deterministic figures under `output/figures/` from generated and committed aggregate JSONs | `src.figures`, `src.evaluation`, `src.provenance` | `dev` |
| `get_longmemeval.sh` | Downloads + SHA-256-validates LongMemEval_S into `data/longmemeval/` (never committed) | `src.evaluation.longmemeval` (heredoc validator) | `bash scripts/get_longmemeval.sh` |
| `promote_production_readiness.py` | Promotes only an accepted, digest-valid operational readiness certificate | `src.evaluation.production_readiness` | `dev` |
| `promote_provenance_p0.py` | Promotes only an accepted, evidence-rebuilt, promotion-eligible P0 certificate | `src.evaluation.provenance_p0` | `dev` |
| `promote_quality_report.py` | Promotes only a digest-valid, threshold-passing quality certificate into committed evidence | `src.evaluation.quality` | `dev` |
| `render_pdf_external.py` | Optional PDF render/validate through the sibling `../template` checkout (temporary exact link, removed on exit) | `src.manuscript_integrity` + template `infrastructure` | `uv run --project ../template python scripts/render_pdf_external.py --validate` |
| `run_bottleneck_campaign.py` | Matched max-window/adaptive Gemma campaign plus separate ranking diagnostics to an external root | `src.evaluation.campaign`, `src.evaluation.longmemeval` | `neural` |
| `run_compiler.py` | `output/data/compile_result.json` (MIPRO + GEPA traces) | `src.compiler`, `src.harness` | `dev` |
| `run_compiler_generalization.py` | Isolated train/held-out generalization aggregate; explicit seed lists supported | `src.evaluation` | `dev` |
| `run_demo.py` | Canonical deterministic demo artifacts; refreshes `verification_summary.json` from finished machine reports | `src.demo` | `dev` |
| `run_dspy.py` | Real DSPy runtime: `dspy.Predict` + `BootstrapFewShot` + held-out lift | `src.dspy_runtime` | `neural` |
| `run_harness_eval.py` | `output/data/eval_results.json` plus accounting, events, and per-example ledger | `src.evaluation` | `dev` |
| `run_injection_probe.py` | Context-poisoning probe with poisoned-answer and cited-excerpt/source-exposure rows | `src.evaluation.injection_resistance`, `src.evaluation.ablation` | `neural` |
| `run_learned_retrieval.py` | Surrogate-vs-learned dense-embedding recall@1 comparison | `src.retrieval.learned` | `neural` |
| `run_longmemeval.py` | LongMemEval_S answer token-F1/citation-support/session-reachability + CIs; resumable | `src.evaluation.longmemeval` | `neural` |
| `run_longmemeval_bottleneck.py` | Ranking-vs-Inspector recall, max_windows sweep, adaptive fix; preserves last aggregate on live failure | `src.evaluation.longmemeval` | `neural` |
| `run_neural_eval.py` | Real extractive-vs-neural token-F1 measurement into `data/neural_eval.json` | `src.dspy_runtime` (`evaluate_backends`) | `neural` |
| `run_openrouter.py` | Real OpenRouter-hosted neural run over the demo dataset (lazy `src` import; needs `THALIA_OPENROUTER_API_KEY`) | `src.dspy_runtime` (`configure_openrouter`) | `neural` |
| `run_pipeline.py` | `output/data/pipeline_result.json` composable-Pipeline trace with intermediates | `src.pipeline` | `dev` |
| `run_production_readiness.py` | Staged local-service operational probes for one pinned profile | `src.evaluation.production_runner` | `neural` |
| `run_quality_campaign.py` | Model-quality runner for the pilot or frozen confirmatory phase (raw observations + blinded packets) | `src.evaluation.quality_runner`, `src.evaluation.llm_judge` | `neural` |
| `run_query.py` | One query CLI against the harness (`--json`, `--config`, `THALIA_*` env, flags) | `src.cli` | `dev` |
| `run_research_campaign.py` | Resumable v2 external-volume campaign tiers; incomplete reports never promoted | `src.evaluation.campaign` | `neural` |
| `run_seed_sensitivity.py` | Isolated ten-seed finite synthetic sensitivity aggregate | `src.evaluation` | `dev` |
| `validate_artifacts.py` | Fail-closed validation of the artifact manifest, formalism traceability, and claim ledger | `src.provenance`, `src.manuscript_integrity`, `src.formalism_traceability` | `dev` |
| `z_generate_manuscript_variables.py` | `output/data/manuscript_variables.json` + token/crossref/numeric/claim-ledger source checks; optional template injection | `src.manuscript_variables`, `src.manuscript_integrity`, `src.provenance`, `src.formalism_traceability` | `dev` |

## Canonical local run order

`run_harness_eval.py` → `run_compiler.py` → `run_seed_sensitivity.py` →
`run_compiler_generalization.py` → `analyze_integrity_advantage.py` →
`run_pipeline.py` → `generate_figures.py` → `z_generate_manuscript_variables.py`
→ `run_demo.py` → `build_dashboard.py` → `validate_artifacts.py` (last and
fail-closed: it refuses missing, mutated, or unsafe manifest entries).

For the source-bound publication refresh, use the recorded enlarged grids (see
the root [AGENTS.md](../AGENTS.md) command block) rather than the quick smoke
defaults; both aggregates record their exact size and seed grids in JSON, so no
result counts are copied manually into manuscript prose.

After a completed strict test/JUnit/coverage run, run `run_demo.py` (or
`build_dashboard.py`) once to refresh `verification_summary.json` from those
finished machine reports, then reconcile the `test-count` and `test-coverage`
entries in `data/claim_ledger.yaml` from that refreshed summary — never from an
incomplete or failing run.

The PDF render/validate step belongs to the external template checkout and is
optional for this standalone project; `render_pdf_external.py` fails closed if
`../template` is absent.

See [CONVENTIONS.md](CONVENTIONS.md) and [AGENTS.md](AGENTS.md).

## Clean-checkout artifact prerequisites

The complete suite consumes real generated figures, seed sensitivity and the
documented twenty-seed compiler-generalization aggregate. Download the real
LongMemEval benchmark with `get_longmemeval.sh` and generate those artifacts
before testing. CI retains the original Python matrix and90% coverage gate.
The optional live injection test belongs to the existing availability-gated
neural class; its assertions are unchanged.

The publication validator also requires a resolved manuscript. CI fetches
Template source `4670c48cc490636455f2eac09ba4396baed9ffd7`, prepares its locked
Python3.14 environment, and invokes `z_generate_manuscript_variables.py` from
that SDK directory under the runner temporary directory, outside the consumer
project scanned by the documentation checks. The exact fetched commit is
verified before use. This consumes a pinned implementation without asserting a
Template4.0.2 release. Standalone token generation retains its explicit optional
injection status. Exact test counts and percentages remain in real JUnit,
coverage and refreshed verification reports; per-run values do not belong in
the fixed claim ledger. The full validator remains fail-closed for all
registered claim values and all required artifacts.
