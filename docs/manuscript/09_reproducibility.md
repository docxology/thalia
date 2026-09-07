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
from the same functions the tests exercise. A drift between prose and code surfaces
as a missing or changed token, exposing narrative drift.

The token gate is deliberately independent of the PDF renderer. The generator
checks manuscript coverage first; optional injection into `output/manuscript/`
then uses the sibling `../template` checkout when available. This prevents a
renderer-path problem from masking the more important contract: every published
number must have a source in the live variable map.

## Ordered Artifact Regeneration {#sec:repro-regenerate}

```bash
# 1. Tests + coverage gate (>= {{CONFIG_COV_GATE}}% on src/; warnings are strict)
PYTHONWARNINGS=error::ResourceWarning uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing --cov-report=json:output/reports/coverage.json \
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
uv run --project . --extra dev python scripts/run_compiler_generalization.py \
  --per-category 10 \
  --seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 \
  --gepa-iterations 4

# 5. Endpoint-specific integrity screen -> data/integrity_advantage.json
uv run --project . --extra dev python scripts/analyze_integrity_advantage.py

# 6. Pipeline trace -> output/data/pipeline_result.json
uv run --project . --extra dev python scripts/run_pipeline.py

# 7. Real DSPy run + optional neural / learned-embedder measurements.
uv run --project . --extra neural python scripts/run_dspy.py
uv run --project . --extra neural python scripts/run_neural_eval.py
uv run --project . --extra neural python scripts/run_learned_retrieval.py
uv run --project . --extra neural python scripts/run_injection_probe.py
uv run --project . --extra neural python scripts/run_longmemeval.py
uv run --project . --extra neural python scripts/run_longmemeval_bottleneck.py

# 8. Figures -> output/figures/*.png  (reads committed aggregates)
uv run --project . --extra dev python scripts/generate_figures.py

# 9. Manuscript variables -> output/data/manuscript_variables.json
uv run --project . --extra dev python scripts/z_generate_manuscript_variables.py

# 10. Demo, dashboard, then artifact hashes + required-output completeness
uv run --project . --extra dev python scripts/run_demo.py
uv run --project . --extra dev python scripts/build_dashboard.py
uv run --project . --extra dev python scripts/validate_artifacts.py
```

The deterministic-core paths in the evaluation, pipeline, figure, and validation
steps are bit-reproducible on any host; the test step also exercises optional
live-service tests when those services are available. The live-recorder step is the
component **outside** the bit-reproducible envelope: it calls recorded
local models (model `{{RESULT_NEURAL_MODEL}}`, temperature {{RESULT_NEURAL_TEMPERATURE}}
[@gemma2025gemma3], and embedder `{{RESULT_EMBED_MODEL}}` with task prefixes
[@nussbaum2024nomic]), so its numbers
reproduce *on a host serving the same model tags*. Cross-host byte identity depends
on machine and Ollama-version agreement. The recorder JSONs carry model metadata — requested
model, resolved tag, digest when Ollama reports one, generation options, embedding
query/document prefixes, benchmark SHA-256/size where applicable, and runtime
Python/platform provenance. If an optional service is unavailable, the tracked
aggregate is preserved; isolated output paths can be used to record the skip
without rewriting committed evidence.

The deterministic research audit evaluates {{RESULT_AUDIT_UNIQUE_N}} unique synthetic examples and
{{RESULT_AUDIT_METHOD_N}} method rows across {{RESULT_AUDIT_STRATA_COUNT}} strata,
{{RESULT_AUDIT_CATEGORY_COUNT}} categories, {{RESULT_AUDIT_SIZES}} per-category sizes,
and {{RESULT_AUDIT_SEED_COUNT}} fixed seeds. Its JSONL ledger has one example/method record with global
sequence numbers and complete failure/fingerprint fields, while the event stream
repeats dataset/config identity per sample and contains no wall-clock fields.

The tracked `data/openrouter_eval.json` is a committed normalized OpenRouter
aggregate used only when present; the canonical local pipeline leaves it
unchanged. The current live smoke recorder is `scripts/run_openrouter.py`, which
writes `output/data/openrouter_result.json` and requires the environment variable
`THALIA_OPENROUTER_API_KEY` to be set to a valid OpenRouter API key. Like all
recorder outputs, an unavailable key is recorded as an isolated skip and the tracked
aggregate remains unchanged; OpenRouter rows contribute only when available.

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

The source release and rendered manuscript are archived as one reproducibility
package at [Zenodo](https://doi.org/{{ZENODO_DOI}}).

**Release DOI:** [{{ZENODO_DOI}}](https://doi.org/{{ZENODO_DOI}}).

The canonical development history is maintained in the
[public GitHub repository](https://github.com/docxology/thalia). The DOI is a
release identifier, not evidence of model-quality, integrity-advantage, or
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
