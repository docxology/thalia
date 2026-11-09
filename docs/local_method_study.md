# Local method study: declared recipe and execution receipt

## Status and question

**Executed finite diagnostic.** The declared matrix completed on 2026-11-08:
1,152 accounted cells, including 864 neural responses, with no failed rows.
The execution receipt, source binding, realized-input diagnostics, and
statistical-validity review below distinguish measurements from the recipe.

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
  The six task categories yield **72 unique example IDs** across these cohorts.
  Template-based draws may repeat input text; the execution review reports
  unique submitted prompt hashes separately without dropping planned rows.
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
  --output output/data/backend_benchmark.json
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
  --backend-benchmark output/data/backend_benchmark.json
uv run --project . --extra dev python \
  scripts/z_generate_manuscript_variables.py \
  --benchmark-report output/data/backend_benchmark.json
```

When an external template renderer is available, preserve this explicit report
selection rather than asking it to hydrate again from the optional default:

```bash
uv run --project . --extra dev python scripts/render_pdf_external.py \
  --skip-manuscript-hydration --validate
```

The skip flag is appropriate only after the fresh, explicit hydration above.
The publication owner separately qualifies the pinned renderer source and
checks exact source substitution before rendering.

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

## Source-established construct boundaries

- The research generator assigns strata by category: literal-lexical to
  single-session/temporal tasks, semantic-paraphrase to preference, noisy context
  to code, and multi-hop updates to multi-session/knowledge-update tasks.
  Category and stratum are therefore not crossed factors. Their grouped means
  cannot isolate a difficulty effect from a task-family effect. See
  [`dataset.py`](../src/evaluation/dataset.py).
- The reported `token_f1` uses deduplicated token sets, not multiset token F1.
  Repetition frequency does not receive additional weight; these values are not
  interchangeable with a differently defined external benchmark score. See
  [`compiler/metrics.py`](../src/compiler/metrics.py).
- The enabled semantic scoring lane is a deterministic hashing surrogate, not
  a learned dense encoder. Disabling it tests this implementation's scoring and
  processing work, not the general value of neural semantic retrieval.
- Different method configurations need not produce different prompts on every
  example. The execution review must count realized prompt differences.
  If two methods submit identical text, a response difference from single-pass
  generation is not evidence of a changed context-selection policy on that pair.

## Observed execution receipt — 2026-11-08

The installed wheel ran outside the checkout from
`2026-11-08T23:22:13.991870Z` through `2026-11-08T23:34:42.975656Z`.
CLI exit status was zero; measured process elapsed time was **748.98 seconds**.
All sixteen backend/method cells completed their requested **72/72** examples:
**1,152 complete, zero failed**, including **864 neural** and **288 extractive**
responses. No method, seed, example, or backend was removed or retried.
The scientific matrix and analysis settings were unchanged; the output filename
was aligned with the common default before execution.

Source-controlled recipe: `284adaa788346a1914ab57c21c39408e552c2b0e`.
Actual producer build: `41da836be37995fe9a4612c9ce2b325cc58671b4`.
The original producer wheel has SHA-256
`b0e6b9da3efddecd12b84bf7df419fc918f91deee1595da28b04c29d2772c67e`.
Its exact wheel and Git source archive are retained under `STUDY_PRODUCER/`
in the supplemental archive. Reader-only exposure summaries added afterward
do not rewrite the measured rows or their fingerprints.

Primary machine records, included in the release supplement:

- `output/data/backend_benchmark.json`: schema two, complete status,
  report fingerprint
  `f1615d74dfe8af07133a42e4941158b4310f4ebadbbc7b0d6e6e483815dda117`.
- Dataset fingerprint:
  `eeeb93d2b21fd2a11b370fff8d0f4751af5e6ae3177ebee5d3f6800bdc2cd9d2`.
- Producer package-inventory fingerprint:
  `c7e6ed7d92168624d91149791bbe7958574240646646483f809f088d440ed567`.
  All **75** recorded Python files matched the qualified checkout before
  post-run reader enhancements. This is byte/source binding, not authentication.
- `output/reports/local_method_execution.json`: actual UTC span, CLI options,
  exit status, wheel digest, client facts, and installed dependency versions.
- `output/reports/local_method_analysis.json`: independently recomputed seed
  means, prompt exposure, source-match scope, and a selected-model-only
  post-run serving-state observation.

The client was an Apple M5 Max, 18 physical/logical CPU cores, 128 GiB RAM,
macOS 27.0.1 arm64, Python 3.13.17. The isolated wheel environment contained
NumPy 2.5.4, Matplotlib 3.11.2, PyYAML 6.0.3, and **no DSPy**; the complete
environment inventory is retained in the execution receipt. This differs from
the separately locked development environment and is recorded rather than
silently treated as identical. Ollama reported version **0.40.15**.

| Requested model | Observed quantization | Observed digest prefix |
| --- | --- | --- |
| `gemma3:1b` | Q4_K_M | `97558784bdc9` |
| `gemma2:2b` | Q4_0 | `8ccf136fdd52` |
| `gemma3:12b` | Q4_K_M | `b92b218582c5` |

Full digests and model metadata remain in the primary report. A post-run
`ollama ps` snapshot showed the selected 12B model resident with an 8,192 context
setting and `100% GPU` in its PROCESSOR column. This is a residency/offload
description, not GPU-utilization measurement or attestation of earlier requests'
device placement, exclusive load, or retained input.

## Observed contrasts and realized inputs

The following is the **harness versus full-context** contrast, not a comparison
of model quality. Values are rounded; all methods, seed means, category/stratum
breakdowns, raw answers, and unrounded values remain in the machine report and
generated manuscript tables.

| Backend | Full-context mean F1 | Harness mean F1 | Seed-mean delta | Descriptive interval |
| --- | ---: | ---: | ---: | --- |
| ExtractiveLM | 0.6485 | 0.6485 | 0.0000 | [0.0000, 0.0000] |
| `gemma3:1b` | 0.4963 | 0.5562 | +0.0599 | [+0.0412, +0.0780] |
| `gemma2:2b` | 0.6107 | 0.4750 | -0.1356 | [-0.1518, -0.1148] |
| `gemma3:12b` | 0.5216 | 0.5094 | -0.0122 | [-0.0373, +0.0335] |

Each contrast has all 72 pairs and three seed clusters. The 1B harness delta
was positive in all three observed seed means; the 2B delta was negative in
all three; the 12B seed means changed sign. These are finite observations,
not significance, superiority, or population-coverage claims.

| Method | Distinct prompt hashes | Different from harness / cases | Mean characters | Maximum characters |
| --- | ---: | ---: | ---: | ---: |
| `full_context` | 54 | 72 / 72 | 440.875 | 1,655 |
| `harness` | 47 | 0 / 72 | 251.458 | 485 |
| `lexical_only` | 47 | 15 / 72 | 251.431 | 485 |
| `adaptive` | 47 | 0 / 72 | 251.458 | 485 |

All 72 cases had a recorded prompt for every method, with prompt agreement
validated across backends. The 72 unique IDs represent only 54 distinct
full-context inputs; repeated inputs were retained, not post-hoc deduplicated.
No identical full-context prompt had conflicting recorded gold answers.

Adaptive and ordinary harness submitted **identical per-example text on every
case**. This cohort therefore supplies no active adaptive-context quality
contrast, despite executing the enabled configuration. Lexical-only changed
15 prompt cases; nearly unchanged character counts do not imply unchanged
ranking/order. All three harness-derived arms differed from full context on
every case.

The maximum submitted full-context prompt was 1,655 Unicode characters.
This is **not a stress test of advertised long-context capacity**. Prompt
characters are not tokenizer counts or measured attention. Context reduction
also did not consistently reduce observed end-to-end latency; the complete
latency table remains a host/client/provider snapshot, not throughput or cost.

## Statistical-validity review and corrected inference

This is an implementation- and artifact-grounded review, including Workflowz
LLM-assisted code/interpretation review, not independent human peer review or
expert answer adjudication.

| Finding | Evidence | Consequence / corrected interpretation |
| --- | --- | --- |
| Complete finite accounting | 1,152 complete rows; zero failures; independent recomputation agrees with all paired seed means | The declared observations are present; completeness does not establish generalization. |
| Nominal methods need not differ | Adaptive and harness match all 72 per-example prompt hashes | No adaptive quality benefit or distinct input intervention is identified here. |
| Repeated content | 72 IDs, 54 distinct full-context inputs, 47 harness inputs | Do not treat the row count as independent content replication or evidence of power. |
| Very few seed clusters | Three seed means per contrast; small-cluster warnings on every interval | Bootstrap support is sparse. The observed intervals reduce to seed-mean ranges here, not population precision guarantees. |
| Short submitted inputs | Maximum full-context prompt 1,655 characters | No advertised-context-capacity or retention claim follows. |
| Proxy and construct limits | Deduplicated-token F1; hashing surrogate; strata mapped to categories | No expert correctness, trained-encoder advantage, or isolated difficulty effect is established. |
| Model/runtime confounding | Different Gemma generations and quantization; deterministic rotation without host-load randomization | Interpret within-backend finite contrasts only; do not isolate size effects or certify latency. |
| Provenance is not attestation | Recorded source inventory, model digests, and runtime metadata | Checksums support consistency and drift detection, not authentic execution or provider-binary identity. |

**Corrected inference:** submitting selected context was not uniformly helpful
on these short synthetic inputs: the observed harness contrast improved token
overlap for the selected 1B backend, reduced it for the selected 2B backend,
and varied in sign across seeds for the selected 12B backend. Keep a real
full-context baseline when inputs fit, measure the chosen backend/configuration
on matched cases, and inspect realized prompts rather than treating method
names as evidence. No general model ranking or adaptive-policy advantage follows.

Confidence is high in within-file accounting, arithmetic, and the documented
source-byte match; confidence in population transfer, causal attribution,
expert quality, or operational guarantees is low or unsupported by this design.
No new cloud or external-benchmark execution was part of this run. Independent
human rating, P0 confirmation, and production acceptance were not performed by
this diagnostic; historical observations retain their separate receipts.
