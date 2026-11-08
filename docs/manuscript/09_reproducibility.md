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

# 9. Demo, dashboard, then artifact hashes + required-output completeness
uv run --project . --extra dev python scripts/run_demo.py
uv run --project . --extra dev python scripts/build_dashboard.py
uv run --project . --extra dev python scripts/validate_artifacts.py

# 10. Optional external render: an already-provisioned template runtime is
# required.
# THALIA hydration above is fresh and exact; use render-only mode because
# template hydration admission independently requires Python >=3.14.
uv run --no-sync --project ../template python \
  scripts/render_pdf_external.py \
  --skip-manuscript-hydration --validate
```

The offline build consumes retained model-dependent aggregates without contacting
a model. If live evidence is intentionally refreshed, collect and review those
sources **before** the integrity screen, then regenerate figures, tokens,
dashboard, manifests, and validation in that order. A later source mutation makes
the earlier fingerprint-bound screen stale. A quick smoke grid must not replace
the publication-size deterministic audit.

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

For matched full-harness observations, use the installed `thalia-benchmark`
command (or the source-checkout bootstrap `scripts/run_backend_benchmark.py`)
with explicit backend selections and a new `--output` path
([@sec:op-backend-benchmark]). The default output is
`output/data/backend_benchmark.json` relative to the caller's working directory,
not inside the installed package. Its complete/incomplete artifact accounting is
separate from the smoke recorder. The dashboard validates this optional input;
`validate_artifacts.py` remains the separate manifest/required-output gate.
Neither structural validation nor a complete benchmark is scientific promotion.

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

The final local refusal boundary is `validate_artifacts.py`. It checks the
generated manifest's relative paths, file sizes, and SHA-256 values against the
current output tree and verifies the required paths declared by
`domain_profile.yaml`. Freshness is established by running the validator after the
last generator, so a later mutation or omitted artifact fails before rendering.

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

The common backend benchmark is a finite diagnostic of the same harness and
seeded cohort under selected clients, not a general model ranking. Its synthetic
examples and automatic support/answer metrics cannot replace expert correctness
or faithfulness labels; successful schema/accounting validation does not change
that boundary. Recorded latency includes harness and client overhead, and
provider availability, model revisions, host hardware, and warm-up affect live
observations. No v{{CURRENT_RELEASE_VERSION}} DOI, accepted expert-quality
certificate, P0 integrity confirmation, or independent production certificate
is asserted by this release.
