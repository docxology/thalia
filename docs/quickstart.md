# Quickstart

The canonical workflow runs from the standalone THALIA root. Every command
targets the project environment and development dependencies explicitly. A
template checkout can use equivalent `--project working/thalia` paths, but the
sibling template is an external integration boundary rather than a local
runtime prerequisite.

## Install & verify

```bash
uv sync --project . --extra dev
uv run --project . --extra dev python scripts/00_preflight.py
PYTHONWARNINGS=error::ResourceWarning uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing --cov-report=json:output/reports/coverage.json \
  --junitxml=output/reports/pytest.xml --cov-fail-under=90
```

## Run a query

```bash
uv run --project . --extra dev python scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
```

Configure via a file, environment, or flags (lowest to highest precedence):

```bash
THALIA_TOP_K=4 uv run --project . --extra dev python scripts/run_query.py \
  --query "..." --config config/harness.yaml --rerank mmr --verify \
  --adaptive-windows --adaptive-window-ratio 5
```

## Multi-turn session (Python)

```python
# Run from the standalone THALIA root so `src` is importable.
from src.session import Session
with Session(db_path="episodes.db", memory_path="MEMORY.md") as s:
    s.ask("My wifi password is bluefish42")
    print(s.ask("What is the wifi password?").answer)
    print("turns:", s.turn_count)
# Session.close() is called automatically on __exit__
```

`Session` (and `EpisodicStore`) implement the context-manager protocol so the
SQLite connection is always closed, even on exception.

## Regenerate artifacts

```bash
# Quick smoke grid (used by isolated script tests)
uv run --project . --extra dev python scripts/run_harness_eval.py
# Publication-size deterministic audit
uv run --project . --extra dev python scripts/run_harness_eval.py \
  --per-category-values 25 50 100 250 \
  --seeds 0 1 2 3 4 5 6 7 8 9 \
  --n-boot 2000
uv run --project . --extra dev python scripts/run_compiler.py
uv run --project . --extra dev python scripts/run_seed_sensitivity.py
uv run --project . --extra dev python scripts/run_compiler_generalization.py \
  --per-category 10 \
  --seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 \
  --gepa-iterations 4
uv run --project . --extra dev python scripts/analyze_integrity_advantage.py
uv run --project . --extra dev python scripts/run_pipeline.py
uv run --project . --extra dev python scripts/generate_figures.py
uv run --project . --extra dev python scripts/z_generate_manuscript_variables.py
uv run --project . --extra dev python scripts/run_demo.py
# build_dashboard.py refreshes the manifest after every required output exists
uv run --project . --extra dev python scripts/build_dashboard.py
uv run --project . --extra dev python scripts/validate_artifacts.py

# Re-render the PDF and validate output (run LAST, once every artifact above is fresh)
# Optional external integration; requires a populated ../template checkout. The
# adapter creates a temporary exact project link and removes it on exit.
uv run --project ../template python scripts/render_pdf_external.py --validate
```

The PDF compiler and THALIA's local artifact checks are separable from the
template-side output-structure check. The adapter reports that external
boundary explicitly when optional template output directories are absent; it
never turns that condition into a fabricated local pass.

`run_harness_eval.py` also runs the seeded sample-size audit. Its accounting is
written to `output/reports/evaluation_accounting.json` and its deterministic
event log to `output/reports/evaluation_events.jsonl`, and one record per
example/method to `output/reports/evaluation_ledger.jsonl`. The precision and
stratified effect figures are `output/figures/sample_size_precision.png` and
`output/figures/statistical_audit.png`. The full audit's unique-example and
method-evaluation counts are generated in `output/data/eval_results.json`; inspect
that accounting bundle rather than copying counts into prose. Pass a smaller
grid explicitly when smoke-testing an isolated temporary output directory.

LongMemEval loading validates every record, aligned session array, and turn. The
neural recorder accepts `--neural-limit 100|250|500` and a resumable
`--checkpoint-path`; a timeout leaves the last valid committed aggregate intact.
The current recovery baseline is 50 neural examples, not a fabricated larger run.

## v2 live campaign (optional)

The v2 campaign is resumable and stores raw rows/checkpoints on the external
`/Volumes/blue/data/thalia_campaigns` volume. Run the campaign and bottleneck
diagnostic scripts with the neural extra only after checking model availability
and free disk space. A timeout or repeated model failure leaves the checkpoint
and marks the tier partial; partial reports are not promoted or used to replace
the retained `data/` aggregates. A valid code/config/model scope mismatch fails
closed rather than recomputing over an existing checkpoint; use a new campaign
ID or the explicit `--allow-scope-change` flag to create a sidecar scope. Inspect
the campaign report before resuming:

```bash
uv run --project . --extra neural python scripts/run_research_campaign.py
uv run --project . --extra neural python scripts/run_bottleneck_campaign.py
```

The deterministic extensions remain repository-local and regenerable:

```bash
uv run --project . --extra dev python scripts/run_seed_sensitivity.py
uv run --project . --extra dev python scripts/run_compiler_generalization.py
```

## Model-quality evidence lane

The operational campaign above is not a model-quality pass: it retains answer
hashes and automated diagnostics, not answer-level labels. The publication path
requires two independent expert raters and blinded adjudication. The local-LLM
runner is an exploratory diagnostic for packet, rubric, and provenance mechanics;
its labels cannot be promoted. Raw answers and annotation packets stay outside
the repository at `/Volumes/blue/data/thalia_quality`.

Run the exploratory pilot first:

```bash
uv run --project . --extra neural python scripts/run_quality_campaign.py --phase pilot
```

After the engineering pilot has diagnosed packet and rubric mechanics, obtain
the two independent blinded expert-rater ledgers and expert adjudication. Analyze
the pilot, review the rubric, and freeze the protocol with the pilot report digest.
The threshold values are deliberately chosen only after that review:

```bash
uv run --project . --extra dev python scripts/analyze_quality.py --help
uv run --project . --extra dev python scripts/freeze_quality_protocol.py --help
uv run --project . --extra neural python scripts/run_quality_campaign.py \
  --phase confirmatory --protocol /path/to/frozen-quality-protocol.json
```

`promote_quality_report.py` refuses incomplete, below-threshold, or tampered
reports. Production readiness is assessed separately and is never implied by the
quality certificate.
