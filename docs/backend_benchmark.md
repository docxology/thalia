# Common backend benchmark

## Purpose and composition

`src.evaluation.backend_benchmark` measures selected `LMClient` implementations
through the **same `AutoHarness`**, not a direct full-context DSPy prediction.
It reuses the seeded research dataset, harness configuration, `token_f1`, and
existing latency-quantile helper. DSPy is not a prerequisite. Extractive is always
included; Ollama and OpenRouter are selected explicitly.

The runner builds `build_research_dataset(per_category, seed)`, round-robin
orders categories, then applies `limit`. All selected backends receive that same
ordered cohort and configuration. A fresh context-managed harness for every
backend/example isolates episodic memory and closes owned stores. Execution is
sequential, one completion attempt per example, with `config.verify=False`:
there are no retries or verification re-answers in this lane. This is backend
composition at the existing Reasoner protocol boundary, not a replacement stage
chain. `Pipeline` separately exposes four runtime stages and custom steps;
the offline Compiler is the fifth architectural stage.

## CLI: explicit local/cloud selection

The installed `thalia-benchmark` command and repository script call the same
`src.benchmark_cli.main` entry point. The CLI uses default `HarnessConfig`;
custom harness settings are available through the Python API, not a `--config`
flag. Neither interface requires DSPy.

### Installed wheel

Install the wheel downloaded from the GitHub release into your chosen Python
environment, then run from any working directory. No source checkout is needed:

```bash
python -m pip install /path/to/thalia-0.2.0-py3-none-any.whl
thalia-benchmark --per-category 2 --seed 0 --limit 6
# Optional local model; Ollama must already serve the selected model.
thalia-benchmark --ollama-model gemma3:4b --per-category 2 \
  --output output/data/backend_local.json
```

This is installation from a release wheel, not a claim of PyPI publication.
By default, artifacts go to `output/data/backend_benchmark.json` relative to
the **caller's current working directory**, never the installed package directory.
Relative explicit `--output` paths use the same working-directory rule;
absolute paths are used as supplied.

### Source checkout

Run these commands from the repository root. The source script retains the
standard bootstrap and delegates to the same installed-command implementation:

```bash
# Offline baseline only; use a distinct destination for each observation.
uv run --project . python scripts/run_backend_benchmark.py \
  --per-category 2 --seed 0 --output output/data/backend_offline.json

# Local generation: Ollama must already serve each requested model.
uv run --project . python scripts/run_backend_benchmark.py \
  --ollama-model gemma3:4b --ollama-model hermes3:8b \
  --per-category 2 --seed 0 --timeout 120 --max-tokens 512 \
  --output output/data/backend_local.json

# CLOUD OPT-IN: sends selected evidence/prompts to the provider and may incur cost.
# Set THALIA_OPENROUTER_API_KEY in the process environment outside source control.
uv run --project . python scripts/run_backend_benchmark.py \
  --ollama-model gemma3:4b --openrouter-model tencent/hy3-preview \
  --allow-cloud --per-category 2 --seed 0 --timeout 120 --max-tokens 512 \
  --output output/data/backend_local_cloud.json
```

A credential alone never selects cloud. `--openrouter-model` **and**
`--allow-cloud` are required; `--allow-cloud` without a cloud model makes no cloud
request. `--ollama-model` and `--openrouter-model` are repeatable. Duplicate backend
names are rejected. Provider/model labels identify observations, not a guarantee
that a mutable model tag denotes fixed weights.

| Option | Default / meaning |
|---|---|
| `--per-category` | `10`; positive generated examples per category before limiting |
| `--seed` | `0`; deterministic cohort seed |
| `--limit` | Unset; positive cap after category round-robin ordering |
| `--timeout` | `30.0` seconds per model request, not a whole-run deadline |
| `--max-tokens` | `1024`; Ollama `num_predict`, OpenRouter `max_tokens` |
| `--output` | `output/data/backend_benchmark.json` relative to the caller's working directory |

The factory records temperature `0.0`, timeout, and provider-specific output-token
options. The CLI also attempts local Ollama model metadata observation; that is
not a generation request or a quality check, and missing metadata does not skip
generation. OpenRouter requires the environment key
`THALIA_OPENROUTER_API_KEY`. This workflow does not load `.env` and does not read
`THALIA_OPENROUTER_MODEL`; model selection is explicit. Never put credentials
in backend metadata or generation options.

### Recorded local observation

The gitignored default artifact generated during local validation records a
completed local-only cohort with extractive, `gemma3:1b`, and `gemma2:2b`;
its accounting reports no failed rows. This artifact is not shipped with a
clean source checkout. No cloud backend was selected or called. Model digests
and runtime metadata are retained in the report. Scores, counts, and latency
values remain in that artifact and the generated manuscript table rather than
being copied into prose.
The recorded selection/options can be rerun into a new isolated destination:

```bash
uv run --project . python scripts/run_backend_benchmark.py \
  --ollama-model gemma3:1b --ollama-model gemma2:2b \
  --per-category 2 --seed 0 --limit 12 --timeout 120 --max-tokens 1024 \
  --output output/data/backend_local_repeat.json
```

A rerun is a new observation, not a promise of identical generations/timing.
This completed local artifact is not a cloud success, final test-suite pass,
rendering check, or scientific-promotion certificate.

## Python API and caller-supplied backends

`src.benchmark_cli.build_parser() -> argparse.ArgumentParser` exposes the CLI
parser, and `src.benchmark_cli.main(argv: list[str] | None = None) -> int` accepts
explicit arguments or uses the process arguments when `argv` is `None`.
It prints the actual output path and returns `0` for complete evidence or `1`
for incomplete evidence; argparse raises `SystemExit(2)` for invalid arguments
or configuration. Benchmark algorithms remain in
`src.evaluation.backend_benchmark`, independently of CLI parsing and I/O.

```python
from src.config import HarnessConfig
from src.evaluation.backend_benchmark import (
    BenchmarkBackend,
    run_backend_benchmark,
    validate_backend_benchmark,
    write_backend_benchmark,
)
from src.llm import OllamaLM

options = {"temperature": 0.0, "num_predict": 512}
backend = BenchmarkBackend(
    name="local-gemma",
    provider="ollama",
    model="gemma3:4b",
    lm=OllamaLM(model="gemma3:4b", timeout=120, options=options),
    generation_options={**options, "timeout": 120},
)
payload = run_backend_benchmark(
    [backend], per_category=2, seed=0,
    config=HarnessConfig(top_k=4, verify=False),
)
validate_backend_benchmark(payload)
actual_path = write_backend_benchmark(payload, "output/data/backend_custom.json")
print(payload["status"], actual_path)
```

`BenchmarkBackend(name, provider, model, lm, generation_options={},
model_observation={})` accepts any real client implementing
`complete(prompt: str) -> str`; public metadata describes the supplied client
and must match its actual options. Client objects and credentials are not
serialized. The runner prepends an extractive baseline if absent. Unknown
caller-defined providers are permitted; the caller remains responsible for
truthful labels and authorized network behavior.

`build_benchmark_backends(*, ollama_models=(), openrouter_models=(),
timeout=30.0, max_tokens=1024, allow_cloud=False, observe_models=False)` provides
the standard extractive/local/cloud selection. Its factory and
`run_backend_benchmark(..., allow_cloud=True)` both require cloud consent for
OpenRouter. Custom clients that hide network calls cannot be detected by a
protocol or label; explicit authorization remains the caller's responsibility.
Programmatic runs do not automatically read harness-field environment overrides;
pass an explicitly loaded configuration if that is intended.

## Complete/incomplete artifact contract

Schema version `1` uses `metric="token_f1"`. Top-level fields are:

- `status`: `complete` only when every planned backend/example succeeded;
- `dataset_fingerprint`, `config_fingerprint`, `n_examples`, and serialized `config`;
- `cohort`: `per_category`, `seed`, `limit`; `examples`: the ordered identity plan;
- `backends`: unique backend summaries; `rows`: the full requested matrix;
- `runtime_provenance`: Python/platform/machine and available model observations;
- `report_fingerprint`: checksum binding the report, including observed timing.

Each summary contains `name`, `provider`, `model`, public `generation_options`,
`status`, `n_requested`, `n_completed`, `n_failed`, `mean_token_f1`,
`mean_latency_seconds`, `p50_latency_seconds`, and `p95_latency_seconds`.
Means and latency quantiles use **successful rows only**, and are null when there
are none. An incomplete backend's successful-only mean is a diagnostic, not a
complete paired estimate; do not rank it against a complete backend.

Each row records `backend`, stable `example_id`, `category`,
`content_fingerprint`, `expected_answer`, dataset/config fingerprints,
`prompt_fingerprints`, `answer`, `token_f1`, `latency_seconds`, `status`, and
`error_class`. Success is `status="complete"`; failure is `status="failed"`
with null answer/F1 and a class name, never raw provider error text, URLs, keys,
or tracebacks. Failures still occupy their planned matrix cell. Prompt hashes
permit equality checks without publishing the prompt text; retained answers and
expected answers can still be sensitive in caller-selected datasets/workflows.

`write_backend_benchmark(payload, path)` validates before atomic writing.
Complete evidence replaces the requested destination. Incomplete evidence goes
to `<stem>.incomplete.json` (for example `backend_local.incomplete.json`),
preserving a previous complete destination. The function returns the **actual**
path. The CLI prints it and returns `1` for incomplete runs; argument/configuration
errors are nonzero too. Check exit status and printed path: an older complete
file left behind is not evidence that the new invocation succeeded.

No committed `data/*.json` aggregate is overwritten or promoted by this runner.
Use separate output paths to retain different runs. The schema currently emits
per-row scores and backend summaries, not a paired significance test or a
quality/promotion certificate.

## Validation and dashboard

```python
import json
from pathlib import Path
from src.evaluation.backend_benchmark import validate_backend_benchmark

payload = json.loads(Path("output/data/backend_custom.json").read_text())
validate_backend_benchmark(payload)  # None on consistency; ValueError otherwise
```

The validator rebuilds the seeded plan and checks exact schema, stable IDs,
content/dataset/config/report fingerprints, complete matrix accounting, finite
bounded scores, nonnegative finite times, prompt agreement, recomputed token-F1,
and recomputed successful-only means/quantiles/status. It accepts honestly
incomplete artifacts so failures remain inspectable. Checksums detect accidental
mutation, not a maliciously rewritten and re-signed report, authentic provider
identity, or true answer correctness.

```bash
uv run --project . --extra dev python scripts/build_dashboard.py \
  --backend-benchmark output/data/backend_local_cloud.json
# Or explicitly inspect the .incomplete.json path printed by a failed run.
```

The dashboard validates supplied JSON before rendering, shows provider/model,
status/counts, F1 and latency quantiles, and labels absent or incomplete evidence.
Without an explicit path it reads `output/data/backend_benchmark.json` only if
present. Rendering is offline; it never fetches missing model measurements.
`validate_artifacts.py` remains the separate required-output/manifest gate, not
a replacement for `validate_backend_benchmark` or scientific review.

## Comparability and latency boundaries

Compare matched rows only within a shared dataset/configuration and prompt
identity. Different model families, options, software, or hardware are part of
the observation, not controlled away by the common interface. Separate runs
need explicit alignment; identical tags or temperature zero do not ensure
identical generations. Token-F1 rewards lexical overlap with gold phrasing;
it is not adjudicated correctness, faithfulness, reasoning ability, or quality.

`latency_seconds` measures observed end-to-end harness execution, including
construction, retrieval, model transport/inference, memory work, and cleanup.
It excludes cohort generation and factory metadata probes. Failed-attempt times
remain in rows but are excluded from successful latency summaries. Cold starts,
cache state, local hardware/load, network distance, and cloud scheduling are not
controlled or randomized. Quantiles describe these finite observations, not
service-level guarantees, token throughput, price, or a local/cloud speed winner.

## Claim-Evidence Audit

The distinctions below use the **Claim-Evidence Audit** technique. Source facts
are observations; arithmetic summaries are derived features. Stable provider
behavior is an assumption, not an observed guarantee. A general backend winner
would be an unsupported inference. Missing matched cloud observations and expert
labels remain missing inputs, not negative evidence against any model.

| Claim | Evidence and type | Verdict / ceiling |
|---|---|---|
| Same runtime harness/cohort/configuration can measure selected clients | `src/evaluation/backend_benchmark.py`: fresh `AutoHarness`, rebuilt seeded plan, prompt/config identity checks; source inspection | Supported implementation capability; not a claim that a live run passed |
| The recorded local cohort completed | `output/data/backend_benchmark.json`: complete status, full extractive/Gemma local matrix, no failed rows, model/runtime metadata; recorded primary artifact and parent-observed exit success | Supported finite local observation; no cloud execution, quality adjudication, or final suite pass implied |
| Historical local directions are mixed | `data/neural_eval.json` category means: higher neural preference/multi-session, tied temporal, lower code/knowledge-update/single-session; retained primary aggregate | Bounded observation in a full-context DSPy cohort, not a cloud/local ranking |
| Held-out compilation establishes a neural ceiling | `src/dspy_runtime/runtime.py::held_out_optimizer_lift` explicitly configures extractive and returns `qa_metric`; source inspection | Unsupported; only extractive-backed automatic-metric lift is measured |
| Retained cloud aggregate supports a local/cloud winner | `data/openrouter_eval.json` is a separate cohort without matched run/config/code receipt or defined pass threshold; retained primary aggregate with provenance gaps | Unsupported; retain historical numbers without pooling or ranking |
| DSPy smoke regenerates the retained cloud aggregate | `scripts/run_openrouter.py` calls `build_program` and writes `output/data/openrouter_result.json`; source inspection | Contradicted; distinct recorder and output, not full harness evidence |
| Valid artifact means model quality or production readiness | Validator checks internal consistency; no expert labels, cost or operational acceptance certificate | Unsupported; completeness is not scientific promotion |

The weakest link in a generalized performance conclusion is not the interface
but the absence of matched adjudicated outcomes and controlled runtime conditions.
Gold phrasing or serving conditions could explain an apparent ordering instead
of model capability. The next discriminating evidence is independent answer-level
adjudication for quality claims, explicitly collected matched cloud observations
for any cloud comparison, and a controlled operational design for latency claims.
Confidence is high in the source-bound interface distinctions and the observed
local artifact's reported completion. The audit does not itself establish cloud
success, answer quality, production readiness, or release readiness. Separate
software/render observations follow below; dated release receipts remain historical.

## Manuscript consumption

The optional common-harness subsection consumes validated default benchmark
evidence through `BACKEND_BENCHMARK_STATUS` and `BACKEND_BENCHMARK_TABLE`, with an
explicit not-recorded fallback when absent. Source prose therefore does not copy
new scores or timings by hand. An isolated run does not enter the manuscript
merely because its file exists elsewhere; select and retain the intended default
artifact before token hydration. Historical `data/neural_eval.json` and
`data/openrouter_eval.json` remain separate inputs.

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
