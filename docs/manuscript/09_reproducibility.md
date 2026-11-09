# Reproducibility: Determinism, Generated Results, and Provenance {#sec:reproducibility}

THALIA inherits the `template/` reproducibility discipline [@friedman2026template;
@peng2011reproducible]: deterministic computation, Zero-Mock tests, a coverage
gate, and a manuscript whose every result number is a generated token.

## Deterministic Execution and Reproducible State {#sec:repro-determinism}

The deterministic core is a deterministic function of its inputs. The lexical lane
(BM25), the semantic lane (SHA-1 hashing embedding), the RRF fusion, the
REPL-style narrowing, the SQLite episodic store, gated consolidation, and the
local MIPRO/GEPA-style search loops contain no unseeded randomness, no wall-clock
dependence, and no network calls. The default Reasoner is also deterministic and
extractive. Consequently identical inputs reproduce identical answers, evaluation
reports, and compiled configurations on that path — a property the test suite
asserts directly (`test_evaluation.py::test_deterministic`,
`test_manuscript_variables.py::test_deterministic`). Replacing the Reasoner or
semantic lane with a live model intentionally moves the run outside that envelope.

Determinism is enforced at method boundaries and verified at the end. The
Inspector emits ordered windows with stable source indices; retrieval tie-breaks
are deterministic; the episodic store rejects duplicate turn ids; compiler search
uses fixed candidate ordering; and generated figures derive from saved JSON
bundles. A rerun can therefore compare artifacts
at multiple layers: raw evaluation data, compiled configuration, figure inputs,
manuscript variables, hydrated Markdown, and final PDF/HTML.

## Source-Bound Manuscript Variables {#sec:repro-tokens}

Every generated `{{…}}` placeholder in this manuscript is emitted by
`src/manuscript_variables.py::generate_variables` from the live evaluation results
and configuration. Configuration tokens (`CONFIG_*`), headline results
(`RESULT_COMPOSITE`, `RESULT_ACCURACY`, …), the retrieval comparison
(`RESULT_*_COMPOSITE`), and the compiled optimum (`RESULT_COMPILED_*`) all derive
from the same functions the tests exercise. Coverage detects missing tokens and
source-value drift, but does not detect every stale qualitative interpretation
or validate the scientific meaning of a metric; those require a claim-evidence audit.

The token gate is deliberately independent of the PDF renderer. The generator
checks manuscript coverage first; optional injection into `output/manuscript/`
then uses the sibling `../template` checkout when available. This prevents a
renderer-path problem from masking the more important contract: every published
number must have a source in the live variable map.

## Ordered Artifact Regeneration {#sec:repro-regenerate}

```bash
# 1. Tests + coverage gate (>= {{CONFIG_COV_GATE}}% on src/;
# warnings are strict)
PYTHONWARNINGS=error::ResourceWarning \
  uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing \
  --cov-report=json:output/reports/coverage.json \
  --junitxml=output/reports/pytest.xml --cov-fail-under={{CONFIG_COV_GATE}}

# 2. Evaluation bundle -> output/data/eval_results.json
# Quick smoke grid:
uv run --project . --extra dev python scripts/run_harness_eval.py
# Recorded publication-size audit:
uv run --project . --extra dev python scripts/run_harness_eval.py \
  --per-category-values 25 50 100 250 \
  --seeds 0 1 2 3 4 5 6 7 8 9 \
  --n-boot 2000

# 3. Compiler search -> output/data/compile_result.json
uv run --project . --extra dev python scripts/run_compiler.py

# 4. Pre-registered finite sensitivity and held-out compiler aggregates
uv run --project . --extra dev python scripts/run_seed_sensitivity.py
uv run --project . --extra dev python \
  scripts/run_compiler_generalization.py \
  --per-category 10 \
  --seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 \
  --gepa-iterations 4

# 5. Optional live-source refresh, only when deliberately collecting a
# NEW cohort.
# Preserve retained data/*.json; use recorder-specific isolated outputs.
# These commands contact live models and are NOT offline build
# prerequisites:
# scripts/run_neural_eval.py, scripts/run_learned_retrieval.py,
# scripts/run_injection_probe.py, scripts/run_longmemeval.py,
# scripts/run_longmemeval_bottleneck.py (each with its documented output
# options).
# A direct DSPy smoke diagnostic is separate:
# uv run --project . --extra neural python scripts/run_dspy.py

# 6. After all intended evidence-source changes, refresh the source-bound
# screen.
uv run --project . --extra dev python \
  scripts/analyze_integrity_advantage.py
uv run --project . --extra dev python scripts/run_pipeline.py

# 7. Figures -> output/figures/*.png  (reads committed aggregates)
uv run --project . --extra dev python scripts/generate_figures.py

# 8. Manuscript variables -> output/data/manuscript_variables.json
uv run --project . --extra dev python \
  scripts/z_generate_manuscript_variables.py

# 9. Demo, dashboard, then an initial project artifact gate
uv run --project . --extra dev python scripts/run_demo.py
uv run --project . --extra dev python scripts/build_dashboard.py
uv run --project . --extra dev python scripts/validate_artifacts.py

# 10. External render for publication: an already-provisioned template
# runtime is required. This precedes final QA and staged-closure validation.
# THALIA hydration above is fresh and exact; use render-only mode because
# template hydration admission independently requires Python >=3.14.
uv run --no-sync --project ../template python \
  scripts/render_pdf_external.py --template-root ../template \
  --skip-manuscript-hydration --validate
```

The offline build consumes retained model-dependent aggregates without contacting
a model. If live evidence is intentionally refreshed, collect and review those
sources **before** the integrity screen, then regenerate figures, tokens,
dashboard, manifests, and validation in that order. A later source mutation makes
the earlier fingerprint-bound screen stale. A quick smoke grid must not replace
the publication-size deterministic audit.

These are regeneration instructions, not permission to rewrite retained
measurements. The original local method study remains the unreleased
`41da836be37995fe9a4612c9ce2b325cc58671b4` producer, its `0.3.0` wheel, and
report fingerprint
`f1615d74dfe8af07133a42e4941158b4310f4ebadbbc7b0d6e6e483815dda117`.
Its historical 1,152 rows include 864 neural responses; these are original
study counts, not v0.3.1 qualification results. Preserve measured JSON and the
`STUDY_PRODUCER/` capsule names rather than resealing or relabeling them.

Publication requires a final step after rendering and **all** browser inspection,
QA, and preview selection: combine the exact release source with only the
allowlisted supplemental outputs in a clean staging root. Write THALIA's final
manifest there, invoke `scripts/render_pdf_external.py --template-root PATH
--validate-only` using the provisioned native runtime, and then run
`scripts/validate_artifacts.py` using THALIA's runtime. Validation-only performs
real native validation without hydration or rerendering and fails on an invalid
THALIA manifest even if native checks pass. The executable staged sequence and
runtime prerequisites are in `docs/release_artifacts.md`.

Package precisely that verified closure. Do not prune the worktree after
validation or refresh manifest-tracked QA, previews, dashboard, manuscript, or
verification summaries after the final gates. A tracked change requires a new
final manifest/native/project sequence, not a hand-edited digest. Exact v0.3.1
outcomes belong in its downloadable release manifest; no earlier release's
validation counts establish the patch's result.

Deterministic algorithms reproduce results for fixed inputs and a compatible
runtime; this is not a promise that figures, PDFs, or validation metadata are
byte-identical on every host. Dependency versions, fonts, renderer, Python,
SQLite, and platform details can affect serialized or rendered artifacts.
Live calls to `{{RESULT_NEURAL_MODEL}}` [@gemma2025gemma3] and
`{{RESULT_EMBED_MODEL}}` [@nussbaum2024nomic] are outside that envelope.
Matching tags and temperature {{RESULT_NEURAL_TEMPERATURE}} are insufficient
to guarantee repeat generations: resolved model weights, serving versions,
hardware, options, and provider behavior also matter. Recorder-specific
metadata should be inspected rather than assumed uniform across legacy files.
Preserve the retained aggregate when a prerequisite is absent or a live run
fails; a skip message is not automatically a machine-readable skip receipt.

The deterministic research audit evaluates {{RESULT_AUDIT_UNIQUE_N}} unique synthetic examples and
{{RESULT_AUDIT_METHOD_N}} method rows across {{RESULT_AUDIT_STRATA_COUNT}} strata,
{{RESULT_AUDIT_CATEGORY_COUNT}} categories, {{RESULT_AUDIT_SIZES}} per-category sizes,
and {{RESULT_AUDIT_SEED_COUNT}} fixed seeds. Its JSONL ledger has one example/method record with global
sequence numbers and complete failure/fingerprint fields, while the event stream
repeats dataset/config identity per sample and contains no wall-clock fields.

The historical `data/openrouter_eval.json` is not regenerated by the local
pipeline or by `scripts/run_openrouter.py`. The latter is a direct DSPy smoke
diagnostic that writes `output/data/openrouter_result.json` only on success.
It reads `THALIA_OPENROUTER_API_KEY` from the process environment, does not load
`.env`, and has no model-selection environment-variable contract. An absent key
prints a skip and returns success without writing null rows or a skip artifact;
a model/runtime error returns nonzero. An older output can therefore remain
after a skipped or failed invocation and is not proof of a fresh success.

The installed `thalia` command provides the query entry point through
`src.cli:main`; `scripts/run_query.py` remains the source-checkout bootstrap.
Neither installed query nor benchmark use requires a checkout-relative script
path. Runtime configuration and explicit live-model selection retain their
documented precedence and network boundaries.

For matched backend-by-method observations, use installed `thalia-benchmark`
(or `scripts/run_backend_benchmark.py`) with repeatable `--method` and `--seed`
and a new `--output` path ([@sec:op-backend-benchmark]). The default destination
is `output/data/backend_benchmark.json` relative to the caller's working
directory, not inside the package. Cohort seeds define independent generated
plans; `--analysis-seed` controls only descriptive bootstrap resampling.
Optional `--config` loads base YAML without harness environment overrides.

Execution uses backend-outer order and deterministic method-order rotation;
each row retains a contiguous execution index. Schema two binds dataset,
method/config, content and prompt fingerprints, the declared schedule, public
runtime/model observations, and a portable producer-source inventory with
observed package/dependency versions. The inventory is checksum/source binding,
not authenticity or provider-binary attestation. A reader validates its recorded
structure, not equality to the reader's installed source.

Schema-one reports are rejected, not upgraded. Python callers migrate from
singular `seed`/run-level `config` to `seeds` and explicit method construction.
Historical release evidence and retained DSPy/cloud cohorts remain unchanged.
Complete reports replace the requested destination atomically; failed evidence
uses an incomplete sidecar, preserving the last good destination. Always select
the actual printed path and inspect the exit status.

The dashboard's `--backend-benchmark PATH` and variable generator's
`--benchmark-report PATH` select the same validated report, including an explicit
incomplete sidecar. Observation and within-model contrast tables are generated,
not hand-transcribed. Neither consumer fetches missing measurements. The artifact
manifest remains a separate required-output gate; complete accounting is not
scientific promotion.

## Provenance from Source to Rendered Output {#sec:repro-provenance}

The artifact inventory produced alongside this manuscript: the evaluation bundle
(`eval_results.json`), the compiled configuration and trace (`compile_result.json`),
the manuscript figures (rendered with a colourblind-safe palette [@wong2011color]), the
static dashboard, and the manuscript-variable map (`manuscript_variables.json`).
Each is regeneratable and disposable; the source of truth is the code under `src/`
and the fixed dataset in `src/evaluation/`. Together they provide an auditable
record of which harness invariants held at build time. Deployment behaviour
requires separate operational measurements.

The provenance chain is intentionally narrow: generated outputs serve as evidence;
source code and fixed
data → script output → manuscript token → hydrated manuscript → rendered artifact.
That route is what prevents a polished PDF from becoming detached from the
executable harness it describes.

## Public archive and release identity {#sec:repro-release}

The current software identity is **v{{CURRENT_RELEASE_VERSION}}**, with the
versioned [GitHub release URL]({{CURRENT_RELEASE_URL}}). This version has no
assigned Zenodo DOI; neither this manuscript nor its metadata claims a new
archive publication.

The historical **v0.1.0** source release and rendered manuscript are archived as
one reproducibility package at
[Zenodo](https://doi.org/{{ARCHIVED_RELEASE_DOI}}).
**Archived v0.1.0 DOI:**
[{{ARCHIVED_RELEASE_DOI}}](https://doi.org/{{ARCHIVED_RELEASE_DOI}}).
That DOI is loaded from the current metadata's historical `isNewVersionOf`
relation; it does not identify v{{CURRENT_RELEASE_VERSION}} or its regenerated
manuscript. The immutable receipt is `docs/release_receipt.md`.

The canonical development history is maintained in the
[public GitHub repository](https://github.com/docxology/thalia). Release
availability is not evidence of model-quality, integrity-advantage, or
production-readiness claims. The archived package intentionally excludes raw
answers, private external-volume records, credentials, and model weights; those
lanes remain separately documented and gated.

The final local refusal boundary is `validate_artifacts.py`, run again after
native validation on the staged source-plus-output closure. THALIA owns
`output/reports/thalia_artifact_manifest.json`; the native renderer independently
owns `output/reports/artifact_manifest.json`. Before v0.3.1, the native generic
output scan overwrote the shared filename, omitted the required committed
`data/integrity_advantage.json`, and captured QA/preview entries that were later
changed or omitted from packaging. Separate ownership preserves the project
contract rather than treating a generic native scan as its replacement.

The project gate checks relative paths, sizes, SHA-256 values, and required paths
declared by `domain_profile.yaml`, including committed inputs from the source
archive. Freshness requires freezing tracked evidence after all QA and validating
the exact closure after the last native operation. No manifest-tracked output
may change after that final sequence. The v0.3.1 patch supersedes the v0.3.0
supplement defect without retagging or replacing its historical tag and assets.

Memory-system comparisons remain in the cited design lineage and remain external
to THALIA's result layer: MemGPT [@packer2023memgpt], Mem0 [@chhikara2025mem0],
TiMem [@li2026timem], and APEX-MEM [@banerjee2026apexmem] are related systems that
motivate persistent memory interfaces, while the local result concerns the narrower
append-only episodic store plus gated consolidation policy.

## Evidence Scope and Honesty Boundaries {#sec:repro-scope}

Two boundaries are stated wherever they are relevant ([@sec:evaluation]): the
deterministic extractive LM bounds answer token-F1, and the hashing-embedding
semantic lane is a deterministic sub-word surrogate. Learned dense retrieval is
a separate plug-in point. The bibliography records primary or official URLs where
available; source-reported empirical claims retain their source status. A local
aggregate explicitly records any THALIA replication.

The backend/method benchmark is a finite synthetic diagnostic, not a general
model ranking. Methods hold the typed renderer and query fixed but change
selected context. Full-context submission and requested Ollama context size do
not guarantee provider retention. No benchmark cache, retries, warm-up calls or
verification re-answers are used. Provider caches and runtime load remain
uncontrolled. The local study declaration in `docs/local_method_study.md` is a
plan; only an actual receipt can establish execution.

Paired comparisons are within a backend. Any missing planned pair suppresses
both mean delta and interval; a single represented seed has no interval, and
small-seed warnings remain visible with descriptive clustered intervals. Synthetic
seed counts do not establish population precision, power or significance.
Prompt characters are not billed tokens. End-to-end cell timing includes local
method/client overhead and is neither throughput nor cost. Automatic answer
overlap cannot replace expert correctness or faithfulness labels. No
v{{CURRENT_RELEASE_VERSION}} DOI, accepted expert-quality certificate, P0 integrity
confirmation, or independent production certificate is asserted by this release.
