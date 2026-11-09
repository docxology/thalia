# Backend and method benchmark

## Purpose and method boundary

`src.evaluation.backend_benchmark` measures real `LMClient` completions on a
shared finite synthetic cohort. Schema 2 separates **backend identity** from
**context-selection method**; it never aggregates methods into one backend score.
DSPy is not required. Extractive is always included; Ollama and OpenRouter are
explicit selections.

| Built-in method | Submitted context |
|---|---|
| `harness` | Base `HarnessConfig` through a fresh `AutoHarness` |
| `full_context` | Every line of the example history, without Inspector/Retriever filtering |
| `lexical_only` | Base harness with lexical weight 1 and semantic weight 0 |
| `adaptive` | Base harness with `adaptive_windows=True` |

Zero-weight retrieval scoring lanes are not built/run and do not enter fusion
membership/ranks. Explicit PRF query expansion remains independent BM25 work;
explicit MMR may still use semantic representations. Lexical-only is therefore
not a promise of zero semantic computation under arbitrary base configurations.
The declared default-base local study leaves PRF and MMR disabled.

All methods hold the typed `ReasonerSignature` renderer and query fixed. The
full-context arm calls the selected client directly with
`render_signature_prompt(ReasonerSignature, history.splitlines(), query=query)`;
it is not a fake LM wrapper or the historical DSPy diagnostic. Harness arms use
fresh context-managed stores per cell and require `verify=False`. Each cell has
one submitted completion attempt: no retries, warm-up calls, verification
re-answers, or benchmark response cache. Provider-side caches and scheduling are
not controlled. **Full context describes what is submitted, not a guarantee that
the provider retains or attends to every line.**

See [`local_method_study.md`](local_method_study.md) for the declared local study
plan and its interpretation boundary. A plan is not an execution receipt.

## Installed CLI and source checkout

Use the wheel from the versioned
[v0.4.0 GitHub release](https://github.com/docxology/thalia/releases/tag/v0.4.0)
in your chosen environment; this is not a PyPI publication claim:

```bash
python -m pip install /path/to/thalia-0.4.0-py3-none-any.whl
# Offline, paired methods; installed command works outside the checkout.
thalia-benchmark --method full_context --method harness \
  --seed 0 --seed 1 --per-category 2 \
  --output output/data/backend_offline.json

# Existing local Ollama model; no download is performed.
thalia-benchmark --ollama-model gemma3:1b \
  --method full_context --method harness --method lexical_only \
  --method adaptive --seed 0 --seed 1 --seed 2 \
  --per-category 2 --num-ctx 8192 --timeout 120 \
  --max-tokens 1024 --n-boot 2000 --analysis-seed 0 \
  --reference-method full_context \
  --output output/data/backend_local.json
```

From the repository root, replace `thalia-benchmark` with
`uv run --project . python scripts/run_backend_benchmark.py`; both use
`src.benchmark_cli.main`. Default and explicit relative output paths are relative
to the **caller's working directory**, never the installed package.

| Option | Default / meaning |
|---|---|
| `--method` | Repeatable; default `harness`; built-ins above, no duplicates |
| `--seed` | Repeatable integer; default 0; unique seeds define separate cohorts |
| `--per-category` | 10; positive examples per category per seed before limiting |
| `--limit` | Unset; positive global cap after seed/category interleaving |
| `--config` | Optional base YAML loaded without `THALIA_*` harness overrides |
| `--ollama-model` / `--openrouter-model` | Repeatable explicit model selection |
| `--num-ctx` | Unset; positive requested Ollama context size only |
| `--timeout` | 30 seconds per request, not a whole-run deadline |
| `--max-tokens` | 1024; Ollama `num_predict`, OpenRouter `max_tokens` |
| `--n-boot` | 2000 descriptive bootstrap resamples |
| `--analysis-seed` | 0; explicit resampling RNG seed, not a generation seed |
| `--reference-method` | `full_context`; contrasts only if selected |
| `--output` | `output/data/backend_benchmark.json` |
| `--plan` | Print the exact planned workload as JSON; no observations, calls, or report file |

`--config` supplies the base for harness-derived methods, not `full_context`.
The benchmark rejects verification-enabled configurations for selected
harness-derived methods before inference; full-context-only selection ignores
unused harness settings.
This differs deliberately from the query CLI's file → environment → flags
precedence. No `.env` is loaded. The factory records temperature 0, output-token
options, timeout, and requested Ollama `num_ctx` when supplied; the request does
not attest actual effective serving context. Cohort seeds are not model RNG seeds.

Cloud requires both explicit model selection and consent:

```bash
# Sends selected prompts to the provider and may incur cost.
# Set THALIA_OPENROUTER_API_KEY outside source control.
thalia-benchmark --openrouter-model tencent/hy3-preview --allow-cloud \
  --method full_context --method harness --seed 0 \
  --per-category 2 --output output/data/backend_cloud.json
```

A key or `--allow-cloud` alone never selects cloud. `--num-ctx` is not forwarded
to OpenRouter. Do not put credentials, private endpoints, or raw provider error
messages into report metadata. SDK-free adapters do not import DSPy or use its
cache; the optional DSPy stack's unresolved persistent-cache advisory remains
separate (see [operability](manuscript/10_operability.md)).

## Inspect the workload without inference

```bash
thalia-benchmark --plan --ollama-model gemma3:1b \
  --method full_context --method harness --method lexical_only \
  --method adaptive --seed 0 --seed 1 --seed 2 --per-category 2
```

The plan is derived by the same pure cohort and rotated-schedule builder used by
execution and validation. It prints planned JSON to stdout, does not write
`--output`, does not query model availability/metadata, and needs no provider
credentials. It records selected identities and generation options, examples,
exact ordered cells and planned counts. The status is `planned`, never complete
or successful. It is not a schema-2 observation report and cannot be supplied as
one. Counts are attempt bounds, not observed successes, provider retention, billed
tokens, money or elapsed-time estimates. Cloud selection still requires explicit
`--allow-cloud` even for planning; planning itself sends no prompts.

In Python, `build_benchmark_plan` accepts the same selection/cohort/analysis
arguments as `run_backend_benchmark` and performs no completion or metadata calls.
Preserve the original `per_category` before limiting: the synthetic generator's
category-major RNG consumption is part of the dataset identity.

## Python API and migration

```python
from src.config import load_config
from src.evaluation.backend_benchmark import (
    BenchmarkMethod,
    build_benchmark_backends,
    build_benchmark_methods,
    run_backend_benchmark,
    validate_backend_benchmark,
    write_backend_benchmark,
)

base = load_config("config/harness.yaml", apply_env=False)
methods = build_benchmark_methods(
    ("full_context", "harness", "lexical_only", "adaptive"),
    config=base,
)
backends = build_benchmark_backends(
    ollama_models=("gemma3:1b",),
    num_ctx=8192,
    timeout=120,
    max_tokens=1024,
)
report = run_backend_benchmark(
    backends,
    methods=methods,
    per_category=2,
    seeds=(0, 1, 2),
    reference_method="full_context",
    n_boot=2000,
    analysis_seed=0,
)
validate_backend_benchmark(report)
path = write_backend_benchmark(report, "output/data/backend_custom.json")
print(report["status"], path)

# Named custom harness configuration; verify must remain False.
custom = BenchmarkMethod(
    name="shallow", kind="harness", config=base.with_(top_k=4)
)
```

`BenchmarkMethod` is frozen. Kinds are `harness` (validated config required) and
`full_context` (`config=None` required); built-in selection rejects unknown or
duplicate names. `BenchmarkBackend(name, provider, model, lm,
generation_options={}, model_observation={})` accepts a real client implementing
`complete(prompt: str) -> str`. Clients/credentials are not serialized. Labels
must honestly describe the client's actual behavior; a protocol cannot detect
hidden network use. The runner inserts extractive if absent. OpenRouter requires
`allow_cloud=True` at both factory and run boundaries.

**Clean cutover:** old Python `seed=...` becomes `seeds=(...,)`. Old run-level
`config=...` moves to `build_benchmark_methods(..., config=...)`, passed as
`methods=...`. There is no singular-seed/config compatibility alias. Schema 1 is
explicitly rejected, not upgraded or silently read by current consumers. Preserve
old release artifacts and historical cohorts unchanged; rerun into a new path
for schema-2 evidence. Root config/config fingerprint and summary-bearing
`backends` are replaced by method records and separate cell `summaries`.

## Cohort and execution schedule

The runner independently builds `build_research_dataset` for each unique seed,
preserving category, stratum, seed, stable example ID, expected answer, and
content fingerprint. At each within-category example index it interleaves seeds
and categories deterministically, rotating seed selection with category/seed
offset, then applies the global limit. One-seed default order is unchanged.
Every selected backend sees the same resulting examples and methods.

Execution is backend-outer to avoid model thrashing, with deterministic
example-index method rotation rather than always executing one method first.
`execution_order` describes the schedule and each row has a contiguous
`execution_index`; validation checks the planned matrix and schedule. Rotation
does not randomize hardware load, cold starts, or provider scheduling.

## Schema-2 accounting and statistical interpretation

Root fields are `schema_version`, `status`, `metric="token_f1"`, `cohort`
(`per_category`, `seeds`, `limit`), `dataset_fingerprint`, `n_examples`, `examples`,
`methods`, `backends`, `rows`, `summaries`, `groups`, `comparisons`, `analysis`,
`runtime_provenance`, `producer_provenance`, `execution_order`, and
`report_fingerprint`.

- `methods` records name, kind, config (null for full context), and
  `method_fingerprint` binding kind/config; `backends` records provider/model and
  public generation options, without method-pooled scores.
- Each row identifies its example, backend and method, dataset/method
  fingerprints, execution index, prompt fingerprints, prompt characters, answer,
  token-F1, latency, status, and safe error class. Complete rows have one prompt;
  failed rows have zero or one captured prompt and null answer/score.
- `summaries` has one backend/method cell. `groups.category` and `groups.stratum`
  retain that separation. Requested/completed/failed counts are always visible.
  F1, prompt-character means and latency mean/p50/p95 use successful rows only;
  absent successes produce nulls, not zeros.
- `analysis` records reference method, resamples, RNG seed, confidence 0.95, and
  unit `seed_mean_paired_token_f1_delta`.
- `comparisons` pairs example identities **within each backend** against the
  selected reference. It records requested/complete pairs, represented seed
  clusters, and raw paired wins/ties/losses. The estimand is the unweighted mean
  of per-seed mean paired F1 deltas, not a pooled model ranking.

**Any missing planned pair suppresses both `mean_delta` and interval.** Counts
and complete-pair wins/ties/losses remain diagnostic. A complete single-seed
contrast can report its finite mean delta but has **no interval**. With at least
two represented seeds, the existing clustered bootstrap resamples seed means;
its small-cluster warning must remain visible. A few synthetic seeds do not
justify population precision, power, p-values, significance, or promotion claims.
If the reference method is absent, comparisons are empty and labelled not
requested, not an implicit zero effect.

Prompt agreement is required across backends for the **same example/method**,
not across different methods. `prompt_characters` counts submitted characters,
not billed tokens, model input-token usage, or effective attention. Latency is
observed end-to-end cell execution (including local method work, transport,
inference and cleanup), not throughput, cost, or a service-level guarantee.
Failed times remain in rows but not successful-only summaries. Cohort generation
and factory metadata probes are outside cell timing.

### Per-seed paired audit

After validating the report, inspect the actual contribution and denominator of
each represented seed without modifying the schema-2 report:

```python
from src.evaluation.benchmark_analysis import summarize_seed_pairs

seed_pairs = summarize_seed_pairs(
    report["rows"],
    backends=[backend["name"] for backend in report["backends"]],
    methods=[method["name"] for method in report["methods"]],
    examples=report["examples"],
    reference_method=report["analysis"]["reference_method"],
)
```

Rows are ordered by backend, selected non-reference method and sorted represented
seed. Each retains requested/complete pairs, raw complete-pair wins/ties/losses,
status and mean delta. A seed's mean is unavailable if any planned pair in that
seed fails, including a seed with no surviving pair. An absent reference produces
no audit rows. The complete overall estimand averages complete seed means equally,
not in proportion to their example counts; pooled observation-cell means therefore
need not subtract to that estimand. Visible complete seeds never rescue a whole
contrast with a missing pair. This helper and the generated tables add
auditability, not data, resampling precision or a new hypothesis test.

### Recorded prompt exposure

`src.evaluation.benchmark_analysis.summarize_prompt_exposure(rows, *, methods,
example_ids, reference_method)` is a pure reader helper, exported from that
module rather than the package barrel. Call it after
`validate_backend_benchmark(report)`, using ordered method names and example IDs.
It returns one row per requested method, in that order:

| Field | Meaning |
|---|---|
| `method` | Requested method name |
| `n_requested_cases` | Number of planned example IDs |
| `n_observed_cases` | Planned cases with a recorded nonempty prompt fingerprint |
| `n_unique_prompts` | Distinct recorded fingerprints across those cases |
| `n_compared_to_reference` | Cases with fingerprints recorded for both this method and the selected reference |
| `n_different_from_reference` | Different paired fingerprints; null if the reference was not selected |
| `prompt_group` | Integer starting at 1 for the first complete vector, reused only for exact vector equality; null if any prompt is missing or the plan is empty |

Observations collapse across backends by `(method, example_id)`, since validated
rows agree on any recorded hash for that case. A failed attempt with a captured
hash counts as observed; an empty failed row never erases a captured hash.
Recorded/planned counts therefore expose missing captures, not successful-answer
counts: retain the separate requested/completed/failed observation accounting.
If the reference is absent there are zero compared cases and a null difference
count; a selected reference with no recorded pairs has zero pairs, not evidence
of equal prompts or a zero quality effect.

Prompt vectors align fingerprints to the supplied example-ID order. Equal
unordered sets of hashes do not establish equivalence, and shared missingness
never assigns a group. A group describes exact per-example recorded submitted
text equivalence in this cohort, not equal code, compute, latency, or quality.
Unique example IDs need not be unique inputs; repeated inputs are not independent
new content or independent method-quality evidence. These are post-run
descriptive diagnostics, not new experiments, causal effects, or model rankings.
They neither recapture prompts nor authenticate actual inference traffic,
provider retention, or effective attention. The helper adds no report fields and
does not alter schema-2 metrics, paired analysis, or report fingerprints.

## One selected report across publication consumers

Dashboard and manuscript generation may independently inspect an explicit valid
report, including an incomplete sidecar. Each writes a source-owned receipt:
`output/reports/dashboard_benchmark_input.json` or
`output/reports/manuscript_benchmark_input.json`. Receipts bind the selected raw
bytes, dataset/report fingerprints and status to the final dashboard or manuscript
variables artifact. A schema-valid report is not sufficient if different
consumers selected different evidence.

For a distributable closure, explicitly stage the unchanged selected report under
`output/data/` and run both generators using that same path. The full artifact
gate rejects divergent reports, changed artifacts/raw bytes, missing evidence and
external-only selections. Standalone external inspection remains supported;
generation never implicitly copies or rewrites measured JSON. Both explicitly
unrecorded consumers remain distinct from a fabricated zero measurement.

## Validation, provenance and failure custody

`validate_backend_benchmark(report)` rebuilds the full seeded cohort and checks
the exact backend × method × example matrix, method configs/fingerprints,
schedule, identities, finite bounds, prompt agreement, recomputed token-F1,
summaries/groups, paired results, and report checksum. Honest incomplete reports
are valid diagnostics. Source inventory paths are portable, with sizes and
SHA-256 digests plus inventory fingerprint and observed package/runtime/
dependency versions. Runtime/model metadata is public allowlisted observation.
Validation checks the recorded inventory's structure, not equality to the
reader's installed source. Checksums bind bytes; they are not authenticity
signatures, provider-binary attestation, or answer-quality adjudication.

`write_backend_benchmark` validates before atomic writing. Complete reports
replace the requested destination; incomplete reports go to
`<stem>.incomplete.json`, preserving the last complete file. The CLI prints the
actual path and returns 0 for complete, 1 for incomplete, or argparse status 2
for invalid arguments/configuration. Check that path and exit status: an older
complete destination is not a new success. No retained `data/` aggregate is
promoted by this runner. Answers/expected answers can still expose sensitive
content even when only prompt hashes, not prompts, are published.

## Dashboard and manuscript consumers

```bash
uv run --project . --extra dev python scripts/build_dashboard.py \
  --backend-benchmark output/data/backend_local.json
uv run --project . --extra dev python \
  scripts/z_generate_manuscript_variables.py \
  --benchmark-report output/data/backend_local.json
```

Select the printed `.incomplete.json` path explicitly to inspect failed evidence.
Dashboard and manuscript consumers validate schema 2 offline and never fetch
missing measurements. Default consumption uses
`output/data/backend_benchmark.json` only when present. Observation and paired
contrast tables retain method identities, failure denominators and single/small
seed caveats. Manuscript observations use generated `BACKEND_BENCHMARK_STATUS`
and `BACKEND_BENCHMARK_TABLE`; contrasts use `BACKEND_COMPARISON_TABLE`.
`generate_variables(..., backend_benchmark_path=...)` selects an explicit report.
Absent evidence is not recorded, not fabricated; measured outcomes are never
hardcoded in source prose. Artifact-manifest validation is a separate gate.

## Claim-Evidence Audit

This guide uses the Claim-Evidence Audit technique to separate source contracts,
derived summaries, serving assumptions, and missing adjudication:

| Claim | Evidence type | Ceiling |
|---|---|---|
| Methods share renderer/query but change selected context | Source contract in `backend_benchmark.py` | Capability, not a live execution receipt |
| Complete schema-2 report has full finite accounting | Validated rows, matrix and recomputed summaries | Consistency, not authenticity or answer quality |
| Paired method delta describes the selected backend/cohort | Complete within-backend pairs and seed-mean analysis | Descriptive finite contrast; retain seed warnings |
| Larger submitted prompt guarantees retained context | Provider behavior would be needed | Unsupported; requested context is not effective retention |
| Token-F1 establishes expert quality or a model winner | Independent expert labels and a different design are missing | Unsupported; no ranking or promotion |
| A historical DSPy/cloud cohort can be pooled here | Matched method/config/source receipts are absent | Unsupported; preserve separate cohorts |

The weakest link in broader inference is construct validity and external
representativeness, not arithmetic completeness. Gold phrasing, context selection,
and serving conditions are credible alternative explanations for a finite delta.
Independent adjudication and a separately designed operational study would
discriminate those explanations; this diagnostic cannot. The declared local
study's receipt and statistical-validity review belong after actual execution.

## Historical local validation before the installed-CLI cutover

These working-tree observations predate the v0.2.0 installed benchmark CLI and
version changes. They are not source-current v0.2.0 verification, a new release,
or scientific promotion. Generated `output/` artifacts remain local and
gitignored.

- Strict full suite: **938 passed, 13 skipped, 951 collected; 90.33% coverage**.
  Receipts: `output/reports/pytest.xml` and `coverage.json`.
  After the renderer metadata fixes, the provenance tests were rerun:
  **13 passed**. Optional live-model skips are not provider success receipts.
- Ruff on changed Python files, `mypy src` (73 files), `uv lock --check`, and
  wheel/source-distribution builds passed. An isolated installed-wheel smoke
  completed six offline observations without DSPy.
- The common local run completed all 36 planned rows across extractive,
  `gemma3:1b`, and `gemma2:2b`, with no failures. Its validated report feeds both
  the dashboard and manuscript table. No cloud request was made.
- Hydration generated every used manuscript token (186), with exact substitution
  across all 22 numbered sections. Artifact validation passed, including the
  source-bound integrity screen; that screen remains unpromoted.
- Browser inspection verified the dashboard at desktop and narrow-mobile widths:
  no page-level horizontal overflow, all 30 images loaded, and the benchmark's
  wide table remains in its labelled keyboard-focusable scroll region.
  The combined HTML loaded all 29 referenced figures and displayed the real
  matched benchmark table without page overflow.
- The external render/validation command passed every reported check: PDF,
  transmission bookends, enabled outputs, Markdown, output structure, figure
  registry, evidence registry, design overlays, and artifact manifest.
  Outputs include `output/pdf/thalia_combined.pdf`, `output/web/index.html`,
  and all 22 slide decks. The PDF has 74 pages, a marked structure tree, and
  visually checked benchmark and typed-signature pages. These facts do not
  establish independent PDF/UA certification.

The provisioned template runtime is separate from THALIA's Python 3.13 dev
environment. Fresh hydration and exact validation precede render-only mode:

```bash
uv run --project . --extra dev python scripts/z_generate_manuscript_variables.py
uv run --project . --extra dev python scripts/validate_artifacts.py
uv run --no-sync --project ../template python scripts/render_pdf_external.py \
  --skip-manuscript-hydration --validate
```

The user-owned TinyTeX installation needed `luatexbase` (and its `ctablestack`
dependency) plus `selnolig`; these were installed with `tlmgr`. Its installed
`fvextra` automatic wrapping was incompatible with tagged paragraph hooks.
Native document-prefix probes isolated that cause; the authored preamble now
uses explicit code layout instead, preserving tagging and native diagnostics.
See `docs/manuscript/SYNTAX.md`. No template source was modified.
