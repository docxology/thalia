# Reproducibility {#sec:reproducibility}

THALIA inherits the `template/` reproducibility discipline [@aii2026template;
@peng2011reproducible]: deterministic computation, Zero-Mock tests, a coverage
gate, and a manuscript whose every result number is a generated token.

## Determinism {#sec:repro-determinism}

Every component is a deterministic function of its inputs. The lexical lane (BM25),
the semantic lane (SHA-1 hashing embedding), the RRF fusion, the REPL-style
narrowing, the SQLite episodic store, the gated consolidation, and the MIPRO/GEPA
search loops contain no unseeded randomness, no wall-clock dependence, and no
network calls. The only judgment step, the Reasoner, defaults to a deterministic
extractive responder. Consequently identical inputs reproduce identical answers,
identical evaluation reports, and identical compiled configurations — a property
the test suite asserts directly (`test_evaluation.py::test_deterministic`,
`test_manuscript_variables.py::test_deterministic`).

Determinism is enforced at method boundaries, not merely observed at the end. The
Inspector emits ordered windows with stable source indices; retrieval tie-breaks
are deterministic; the episodic store rejects duplicate turn ids; compiler search
uses fixed candidate ordering; and generated figures derive from saved JSON
bundles rather than ad-hoc plotting state. A rerun can therefore compare artifacts
at multiple layers: raw evaluation data, compiled configuration, figure inputs,
manuscript variables, hydrated Markdown, and final PDF/HTML.

## Generated manuscript variables {#sec:repro-tokens}

Every generated `{{…}}` placeholder in this manuscript is emitted by
`src/manuscript_variables.py::generate_variables` from the live evaluation results
and configuration. Configuration tokens (`CONFIG_*`), headline results
(`RESULT_COMPOSITE`, `RESULT_ACCURACY`, …), the retrieval comparison
(`RESULT_*_COMPOSITE`), and the compiled optimum (`RESULT_COMPILED_*`) all derive
from the same functions the tests exercise. A drift between prose and code surfaces
as a missing or changed token rather than as silent narrative rot.

The token gate is deliberately independent of the PDF renderer. The generator
checks manuscript coverage first; optional injection into `output/manuscript/`
then uses the sibling `../template` checkout when available. This prevents a
renderer-path problem from masking the more important contract: every published
number must have a source in the live variable map.

## How to regenerate every artifact {#sec:repro-regenerate}

```bash
# 1. Tests + coverage gate (>= {{CONFIG_COV_GATE}}% on src/; warnings are strict)
PYTHONWARNINGS=error::ResourceWarning uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing --cov-report=json:output/reports/coverage.json \
  --junitxml=output/reports/pytest.xml --cov-fail-under={{CONFIG_COV_GATE}}

# 2. Evaluation bundle -> output/data/eval_results.json
uv run --project . --extra dev python scripts/run_harness_eval.py

# 3. Compiler search -> output/data/compile_result.json
uv run --project . --extra dev python scripts/run_compiler.py

# 4. Pre-registered finite sensitivity and held-out compiler aggregates
uv run --project . --extra dev python scripts/run_seed_sensitivity.py
uv run --project . --extra dev python scripts/run_compiler_generalization.py

# 5. Pipeline trace -> output/data/pipeline_result.json
uv run --project . --extra dev python scripts/run_pipeline.py

# 6. Real DSPy run + optional neural / learned-embedder measurements.
uv run --project . --extra neural python scripts/run_dspy.py
uv run --project . --extra neural python scripts/run_neural_eval.py
uv run --project . --extra neural python scripts/run_learned_retrieval.py
uv run --project . --extra neural python scripts/run_injection_probe.py
uv run --project . --extra neural python scripts/run_longmemeval.py
uv run --project . --extra neural python scripts/run_longmemeval_bottleneck.py

# 7. Figures -> output/figures/*.png  (reads committed aggregates)
uv run --project . --extra dev python scripts/generate_figures.py

# 8. Manuscript variables -> output/data/manuscript_variables.json
uv run --project . --extra dev python scripts/z_generate_manuscript_variables.py

# 9. Demo, dashboard, then artifact hashes + required-output completeness
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
reproduce *on a host serving the same model tags*, not byte-for-byte across
machines and Ollama versions. The recorder JSONs carry model metadata — requested
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

The tracked `data/openrouter_eval.json` is a historical normalized OpenRouter
aggregate used only when present; it is not regenerated by the canonical local
pipeline. The current live smoke recorder is `scripts/run_openrouter.py`, which
writes `output/data/openrouter_result.json` and requires the environment variable
`THALIA_OPENROUTER_API_KEY` to be set to a valid OpenRouter API key. Like all
recorder outputs, an unavailable key is recorded as an isolated skip rather than
rewriting the tracked aggregate; the OpenRouter rows simply do not contribute to
aggregate figures.

## Provenance chain {#sec:repro-provenance}

The artifact inventory produced alongside this manuscript: the evaluation bundle
(`eval_results.json`), the compiled configuration and trace (`compile_result.json`),
the manuscript figures (rendered with a colourblind-safe palette [@wong2011color]), the
static dashboard, and the manuscript-variable map (`manuscript_variables.json`).
Each is regeneratable and disposable; the source of truth is the code under `src/`
and the fixed dataset in `src/evaluation/`. Together they provide an auditable
record of which harness invariants held at build time; they are not a proof about
unmeasured deployments.

The provenance chain is intentionally narrow: generated outputs are evidence, not
source. If a reader wants to audit a claim, the route is source code and fixed
data → script output → manuscript token → hydrated manuscript → rendered artifact.
That route is what prevents a polished PDF from becoming detached from the
executable harness it describes.

The final local refusal boundary is `validate_artifacts.py`. It checks the
generated manifest's relative paths, file sizes, and SHA-256 values against the
current output tree and verifies the required paths declared by
`domain_profile.yaml`. The manifest writer is not itself evidence of freshness:
the validator is run after the last generator, so a later mutation or omitted
artifact fails before rendering.

Memory-system comparisons are scoped to the cited design lineage rather than
absorbed as THALIA results: MemGPT [@packer2023memgpt], Mem0 [@chhikara2025mem0],
TiMem [@li2026timem], and APEX-MEM [@banerjee2026apexmem] are related systems that
motivate persistent memory interfaces, while the local result remains the narrower
append-only episodic store plus gated consolidation policy.

## Scope and honesty notes {#sec:repro-scope}

Two boundaries are stated wherever they are relevant ([@sec:evaluation]): the
deterministic extractive LM bounds token-F1 accuracy, and the hashing-embedding
semantic lane is a sub-word surrogate, not a learned dense retriever. Both are
designed plug-in points. The bibliography records primary or official URLs where
available; source-reported empirical claims remain source claims, not independent
THALIA replications, unless a local aggregate explicitly records the result.
