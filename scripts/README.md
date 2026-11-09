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
| `run_backend_benchmark.py` | Schema-2 backend/method observations and within-backend paired analysis; complete report or incomplete sidecar | `src.benchmark_cli` → `src.evaluation.backend_benchmark` | `uv run --project . python scripts/run_backend_benchmark.py` (no DSPy) |
| `assemble_release_artifacts.py` | Deterministic explicit frozen supplement, complete inventoried output closure and external member receipt; no native execution or publication | `src.release_artifacts` | `dev`, explicit staged root/allowlist/output |
| `build_provenance_p0_packets.py` | Builds blinded expert packets, separate blind key, and sealed blinding manifest from external raw rows | `src.evaluation.provenance_p0` | `dev` |
| `freeze_provenance_p0.py` | Freezes a reviewed P0 protocol with canonical digest and owner-declared margins | `src.evaluation.provenance_p0` | `dev` |
| `freeze_quality_protocol.py` | Records the post-pilot rubric, estimand, thresholds, and provenance before confirmation | `src.evaluation.quality` | `dev` |
| `generate_figures.py` | Deterministic figures under `output/figures/` from generated and committed aggregate JSONs | `src.figures`, `src.evaluation`, `src.provenance` | `dev` |
| `get_longmemeval.sh` | Downloads + SHA-256-validates LongMemEval_S into `data/longmemeval/` (never committed) | `src.evaluation.longmemeval` (heredoc validator) | `bash scripts/get_longmemeval.sh` |
| `promote_production_readiness.py` | Promotes only an accepted, digest-valid operational readiness certificate | `src.evaluation.production_readiness` | `dev` |
| `promote_provenance_p0.py` | Promotes only an accepted, evidence-rebuilt, promotion-eligible P0 certificate | `src.evaluation.provenance_p0` | `dev` |
| `promote_quality_report.py` | Promotes only a digest-valid, threshold-passing quality certificate into committed evidence | `src.evaluation.quality` | `dev` |
| `render_pdf_external.py` | External render or real native validation-only; explicit template selection and fail-closed THALIA manifest gate | `src.manuscript_integrity`, `src.provenance` + provisioned template `infrastructure` | `uv run --no-sync --project ../template python scripts/render_pdf_external.py --template-root ../template --skip-manuscript-hydration --validate` |
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
| `run_neural_eval.py` | Historical extractive-vs-neural full-context DSPy token-F1 diagnostic into `data/neural_eval.json`; not AutoHarness | `src.dspy_runtime` (`evaluate_backends`) | `neural` |
| `run_openrouter.py` | Direct full-context DSPy smoke diagnostic into `output/data/openrouter_result.json`; process-env key required, no `.env` loading; skip/no artifact without key, nonzero on runtime/model failure | `src.dspy_runtime` (`configure_openrouter`, `build_program`) | `neural` |
| `run_pipeline.py` | `output/data/pipeline_result.json` composable-Pipeline trace with intermediates | `src.pipeline` | `dev` |
| `run_production_readiness.py` | Staged local-service operational probes for one pinned profile | `src.evaluation.production_runner` | `neural` |
| `run_quality_campaign.py` | Model-quality runner for the pilot or frozen confirmatory phase (raw observations + blinded packets) | `src.evaluation.quality_runner`, `src.evaluation.llm_judge` | `neural` |
| `run_query.py` | One query CLI against the harness (`--json`, `--config`, `THALIA_*` env, flags) | `src.cli` | `dev` |
| `run_research_campaign.py` | Resumable v2 external-volume campaign tiers; incomplete reports never promoted | `src.evaluation.campaign` | `neural` |
| `run_seed_sensitivity.py` | Isolated ten-seed finite synthetic sensitivity aggregate | `src.evaluation` | `dev` |
| `validate_artifacts.py` | Fail-closed validation of the artifact manifest, formalism traceability, and claim ledger | `src.provenance`, `src.manuscript_integrity`, `src.formalism_traceability` | `dev` |
| `z_generate_manuscript_variables.py` | Generated tokens and source checks; `--benchmark-report PATH` selects validated benchmark evidence, including incomplete reports | `src.manuscript_variables`, `src.manuscript_integrity`, `src.provenance`, `src.formalism_traceability` | `dev` |

## Canonical local run order

`run_harness_eval.py` → `run_compiler.py` → `run_seed_sensitivity.py` →
`run_compiler_generalization.py` → `analyze_integrity_advantage.py` →
`run_pipeline.py` → `generate_figures.py` → `z_generate_manuscript_variables.py`
→ `run_demo.py` → `build_dashboard.py` → `validate_artifacts.py` (fail-closed:
it refuses missing, mutated, or unsafe THALIA manifest entries). Publication
continues through rendering, QA, and the final staged-closure gate below; the
early project check is not a receipt for later modified outputs.

For the source-bound publication refresh, use the recorded enlarged grids (see
the root [AGENTS.md](../AGENTS.md) command block) rather than the quick smoke
defaults; both aggregates record their exact size and seed grids in JSON, so no
result counts are copied manually into manuscript prose.

An intentional live-source refresh precedes `analyze_integrity_advantage.py`,
not follows it. Keep old measured cohorts intact and review isolated new outputs
before changing retained evidence. Any later source mutation requires rerunning
the integrity screen and its downstream figures/tokens/dashboard/manifest gates.

## Backend/method observations

Install the wheel downloaded from the versioned v0.4.0 GitHub release into your
chosen environment; this is not a PyPI publication claim:

```bash
python -m pip install /path/to/thalia-0.4.0-py3-none-any.whl
thalia-benchmark --method full_context --method harness \
  --seed 0 --seed 1 --per-category 2 \
  --output output/data/backend_offline.json
```

The installed command and source bootstrap use `src.benchmark_cli:main` without
DSPy. Source examples assume the repository root:

```bash
uv run --project . python scripts/run_backend_benchmark.py \
  --ollama-model gemma3:1b --num-ctx 8192 \
  --method full_context --method harness --method lexical_only \
  --method adaptive --seed 0 --seed 1 --seed 2 \
  --per-category 2 --timeout 120 --max-tokens 1024 \
  --n-boot 2000 --analysis-seed 0 --reference-method full_context \
  --output output/data/backend_local.json
uv run --project . --extra dev python scripts/build_dashboard.py \
  --backend-benchmark output/data/backend_local.json
uv run --project . --extra dev python \
  scripts/z_generate_manuscript_variables.py \
  --benchmark-report output/data/backend_local.json
```

Model/method/seed flags repeat. Default selection is extractive, method
`harness`, seed 0; `--config PATH` supplies base YAML without harness environment
overrides. Optional positive `--num-ctx` requests Ollama context only, not
effective context retention. Cloud additionally requires explicit
`--openrouter-model MODEL --allow-cloud` and an authorized process-environment
key; a credential alone never invokes cloud.
Before inference, add `--plan` to print the exact workload without model metadata
probes, completion calls or output-file writes. The pure `build_benchmark_plan`
API shares cohort/schedule construction with execution and validation. Planned
counts are not observed successes, billed tokens, cost or elapsed-time estimates.

Schema 2 separates backend metadata from method configs, cell/group summaries,
paired comparisons and portable producer provenance. Migrate singular Python
`seed` to `seeds` and run-level `config` to `build_benchmark_methods`; no aliases
or schema-1 reader remain. Preserve historical release evidence and cohorts.

The default destination is `output/data/backend_benchmark.json` relative to the
caller's working directory, not the package directory. Selected failures are
recorded, return nonzero, and print an `.incomplete.json` sidecar path, preserving
the requested complete destination. Use the actual sidecar in both consumers
when diagnosing failures; an older complete file is not a new success receipt.
Any incomplete planned pair suppresses delta/interval; a single seed has no
interval and small-seed warnings remain visible. Prompt characters are not billed
tokens; end-to-end timing is not throughput/cost. No retries, benchmark cache,
model ranking, expert-quality/power claims or scientific promotion.
Per-seed contribution tables expose requested/complete denominators and suppress
an incomplete seed's mean. Final publication also requires both generated input
receipts to bind the same unchanged selected report under `output/data/` to each
final consumer artifact. External-only or divergent valid selections fail the
project release gate; neither generator silently copies measured JSON.

See [`../docs/backend_benchmark.md`](../docs/backend_benchmark.md) for the
contract and [`../docs/local_method_study.md`](../docs/local_method_study.md)
for the declared finite local plan, preserved original execution and bounded review.

Live neural DSPy tests separately require `THALIA_LIVE_TESTS=1`; optional DSPy
classes skip without the SDK, and collection does not perform generation.

After a completed strict test/JUnit/coverage run, run `run_demo.py` (or
`build_dashboard.py`) to refresh `verification_summary.json` from those finished
machine reports. Zero collection or malformed current reports cannot retain PASS.
Exact observed counts belong in regenerated evidence, not hand-copied fixed claims.

The PDF render/validate step uses an external, already-provisioned template
checkout and is optional for standalone non-publication use. The adapter discovers
a sibling by default or takes `--template-root PATH`; absence fails closed.
Freshly hydrate with THALIA's interpreter and pass exact injection validation
before using `--skip-manuscript-hydration`. The provisioned template runtime has
independent Python admission requirements; `--no-sync` does not install or
reconfigure it.

### Final publication validation without rerendering

Since v0.3.1, THALIA owns `output/reports/thalia_artifact_manifest.json`;
the native renderer owns `output/reports/artifact_manifest.json`. The old shared
filename let the native generic output scan overwrite THALIA's inventory, omit
the required committed `data/integrity_advantage.json`, and record QA/preview
entries that later changed or were excluded. Neither inventory replaces the
downloadable release manifest.

Finish all render/browser/QA work before freezing THALIA's inventory. Use a clean
Git checkout/worktree at the exact release commit, named `thalia` to match the
retained combined-PDF filename, and overlay only the supplemental allowlist.
Native provenance requires a Git worktree boundary, not merely an extracted
tarball. Preserve relative paths and committed inputs. With the current
directory set to this clean Git project root, `THALIA_PYTHON` an absolute
provisioned THALIA interpreter outside it, and `TEMPLATE_ROOT` an absolute
provisioned template root:

```bash
set -e
: "${THALIA_PYTHON:?Set the provisioned THALIA interpreter}"
: "${TEMPLATE_ROOT:?Set the provisioned template checkout}"
"$THALIA_PYTHON" -c \
  'from src.provenance import write_artifact_manifest; print(write_artifact_manifest())'
uv run --no-sync --project "$TEMPLATE_ROOT" python \
  scripts/render_pdf_external.py --template-root "$TEMPLATE_ROOT" \
  --validate-only
"$THALIA_PYTHON" scripts/validate_artifacts.py
```

`--validate-only` runs the real native validation pipeline, not a simulated
check, and neither hydrates nor rerenders. THALIA manifest failure is nonzero
even if the native pipeline passes. Run the full project gate after native
validation; package precisely this verified closure, not a pruned worktree.
Do not mutate manifest-tracked QA or other outputs after the final sequence.
Do not refresh the demo/dashboard/verification summary, annotate QA, or render
again afterward; any tracked change requires a fresh inventory and both gates.
No measured study JSON is resealed. The retained `STUDY_PRODUCER/` capsule and
its `0.3.0` wheel still identify the original unreleased producer, not a current
rerun. Exact current results belong in the v0.4.0 release manifest.

See [artifact assembly](../docs/release_artifacts.md) and
[v0.4.0 release notes](../docs/releases/v0.4.0.md). Historical v0.3.1 repaired the
v0.3.0 supplement defect without replacing either version's tag or asset bytes.

`assemble_release_artifacts.py --project-root "$THALIA_STAGE"
--allowlist /path/to/reviewed-files.json --output /path/to/supplement.tar.gz
--prefix thalia-0.4.0-artifacts` consumes a JSON-array allowlist. It refuses
omitted output entries from either inventory and prints a byte/member receipt
to stdout. Retain that receipt outside frozen inputs. It does not rerun native
validation, refresh evidence or publish to GitHub.

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
