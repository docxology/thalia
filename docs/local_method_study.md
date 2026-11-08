# Local method study: declared finite diagnostic

## Status and question

**PLAN, not observed results.** This declaration specifies a v0.3.0 local
within-model comparison. Execution receipts and a statistical-validity review
must be appended by the integration owner after real execution; this document
asserts no completed calls, measured scores, failures, or timing outcomes.

Question: for each selected backend on the same finite synthetic examples, how
do selected-context methods change answer token-F1 relative to submitting the
full history? This is not a model-ranking, expert-quality, power, causal,
production-readiness, or scientific-promotion study.

This recipe was declared before this run, not independently preregistered.
The earlier v0.2 diagnostic informed model selection; these examples are not an
unseen confirmatory holdout. Different Gemma generations are included, so this
design does not isolate model-size effects.

## Declared matrix and inputs

- Cohort: `build_research_dataset`, per-category 4, seeds 0, 1, 2, no limit.
  The six task categories yield **72 unique examples** across these seed cohorts.
- Methods: `full_context`, `harness`, `lexical_only`, `adaptive`.
- Backends: mandatory ExtractiveLM plus installed Ollama `gemma3:1b`, `gemma2:2b`,
  and `gemma3:12b`. Other installed models are outside this declaration.
- Planned matrix: **72 examples × 4 methods × 4 backends = 1,152 rows**, of which
  **864 are neural completion attempts** if execution reaches every planned cell.
  These are design counts, not a completion receipt.
- Base: default validated `HarnessConfig`, verification disabled. Lexical-only
  sets scoring weights to lexical 1 / semantic 0; adaptive enables the existing
  adaptive-window policy. Default PRF query expansion and MMR are disabled.
- Requested Ollama context 8,192; output cap 1,024; temperature 0; timeout
  120 seconds per request. Requested context is not verified effective retention.
- Analysis reference `full_context`, 2,000 bootstrap resamples, analysis seed 0,
  confidence 0.95. Cohort and analysis seeds do not set provider generation RNG.
- No model downloads, private model profiles, paid/cloud calls, retry,
  benchmark response cache, warm-up, verification re-answer, or implicit promotion.

## Invocation

After installing the candidate wheel in the chosen environment, use a new,
isolated destination. The command works without a source checkout or DSPy:

```bash
thalia-benchmark \
  --ollama-model gemma3:1b --ollama-model gemma2:2b \
  --ollama-model gemma3:12b \
  --method full_context --method harness \
  --method lexical_only --method adaptive \
  --seed 0 --seed 1 --seed 2 --per-category 4 \
  --num-ctx 8192 --max-tokens 1024 --timeout 120 \
  --reference-method full_context --n-boot 2000 --analysis-seed 0 \
  --output output/data/local_method_study.json
```

No `--limit` or cloud option is part of this plan. Record the actual printed
path and exit status. Incomplete execution writes an `.incomplete.json` sidecar
and preserves a previous complete destination; that older file is not evidence
of a new success. Do not convert missing rows into successes or retry them into
an apparently uninterrupted observation.

## What is held fixed and what changes

The typed `ReasonerSignature` renderer and query are shared. Full context sends
`session_history.splitlines()` directly to that renderer and actual selected LM,
without Inspector/Retriever filtering. Harness-derived arms use a fresh
context-managed `AutoHarness` per cell. Thus selected context changes, not merely
the model label. Full-context submission does not guarantee that the serving
stack retains or attends to the entire history.

Zero-weight retrieval scoring lanes are not built or run and do not contribute
fusion membership/ranks. This is narrower than saying a method can never perform
lexical or semantic computation: an explicitly enabled PRF query expansion may
independently use BM25, and explicit MMR may use semantic representations. Those
features are disabled in this declared default-base lexical-only arm.

Each seed's cohort is built independently. Deterministic seed/category
interleaving precedes any limit. Execution is backend-outer, with deterministic
method-order rotation by example; contiguous execution indices and schedule
metadata are retained. This reduces model thrashing and avoids one fixed method
always going first, but is not runtime randomization or control of host load.

## Retained evidence and consumers

Retain the schema-2 report, all failures, expected/returned answers, method
configs and fingerprints, dataset/content/prompt fingerprints, prompt character
counts, execution indices, category/stratum summaries, paired contrasts,
model digests and available runtime metadata. Producer provenance binds portable
source paths/sizes/SHA-256 and observed package/dependency versions. Review the
recorded scope, not only mutable model tags. Checksums are not authenticity
signatures or provider-binary attestation.

Use the same explicitly selected artifact for both consumers, including the
printed sidecar if incomplete:

```bash
uv run --project . --extra dev python scripts/build_dashboard.py \
  --backend-benchmark output/data/local_method_study.json
uv run --project . --extra dev python \
  scripts/z_generate_manuscript_variables.py \
  --benchmark-report output/data/local_method_study.json
```

Measured manuscript values come only from validated generated observation and
comparison tokens. Never transcribe scores, timings, or confidence limits into
source prose. Preserve historical `data/neural_eval.json`,
`data/openrouter_eval.json`, and immutable release cohorts without pooling,
rewriting, or schema conversion. See [the benchmark guide](backend_benchmark.md)
for the schema-1 API/consumer cutover.

## Interpretation rules for the later review

1. Account for every planned backend/method/example cell and report actual
   complete/failed counts before interpreting successful-only means.
2. Pair only within a backend on the same example identity. Report raw pair
   wins/ties/losses, but estimate the unweighted mean of per-seed mean paired
   token-F1 deltas against `full_context`.
3. If any planned pair is incomplete, suppress both mean delta and interval;
   available pairs are diagnostic, not a complete contrast. A single represented
   seed has no interval. With multiple seeds, retain the clustered bootstrap's
   small-seed warning: three synthetic seeds are not independent population
   replications or evidence of adequate statistical power.
4. Treat bootstrap intervals as descriptive sensitivity of this finite design.
   No significance, p-values, population precision, model ranking, or superiority
   claims follow from these contrasts.
5. Prompt characters are not billed tokens or measured effective attention.
   End-to-end method timing includes local work, transport/inference, and cleanup;
   it is not token throughput, cost, or a service-level guarantee. Uncontrolled
   cold starts, provider caches, runtime versions and hardware/load remain
   alternative explanations for timing differences.
6. Token-F1 is lexical answer overlap, not expert correctness, faithfulness,
   usefulness, or reasoning quality. Synthetic phrasing and context selection
   can explain differences. Expert adjudication and a separately controlled
   operational design would be needed for broader claims.

The execution receipt must distinguish observed artifacts from this declaration,
record failures/skips and actual scope/provenance, and identify departures from
the plan. The subsequent statistical-validity review must retain the limitations
above rather than interpreting completeness as promotion.
