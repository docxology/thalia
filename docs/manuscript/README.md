# `docs/manuscript/` — THALIA write-up

The full design and evaluation write-up, authored as numbered Markdown sections
that can be explicitly compiled to PDF/HTML by the template rendering pipeline.

## Sections

| File | Content |
|------|---------|
| `00_abstract.md` | Abstract |
| `01_introduction.md` | Motivation, the four foundations + substrate, contributions |
| `02_foundations.md` | Deep analysis of DSPy, RLMs, memory faults, agentic search, `template/` |
| `03_hermes_architecture.md` | Hermes prompt assembly + DSPy/GEPA self-evolution |
| `04_harness_design.md` | Harness-design spine and reading order |
| `04a_`-`04c_*.md` | Method contract/stage flow, formalism/added methods, and implementation traceability |
| `05_template_integration.md` | `AGENTS.md`/`SKILL.md` duality + build lifecycle mapping |
| `06_active_inference.md` | Correspondences with the Free Energy Principle |
| `07_evaluation.md` | Top-level evaluation chapter: evidence tiers, estimands, and scope boundaries |
| `07a_`-`07e_*.md` | Evaluation subsections: experimental design, benchmark transfer, baselines/context-poisoning probe, retrieval/noise, and compiler synthesis |
| `08_reference_architecture.md` | Design-principle table + file structure |
| `09_reproducibility.md` | Determinism, generated tokens, regeneration commands |
| `10_operability.md` | Configuration, real LM adapters, persistent session, CLI |
| `11_validation.md` | Invariants, Zero-Mock suite, golden regression, dashboard |
| `12_supplemental_notation.md` | Canonical symbols and statistical contracts |
| `99_references.md` | Reference list (Pandoc `--citeproc`) |

Supporting files: `config.yaml` (metadata), `preamble.md` (LaTeX), `references.bib`
(bibliography), `SYNTAX.md` (citation/figure/equation conventions). The
THALIA-local [`thalia_overlay.yaml`](../../thalia_overlay.yaml) holds project-specific model-quality,
campaign, and production-readiness declarations that do not belong in the
generic template profile/experiment schemas.

## Generated tokens

Numeric results in the prose are `{{…}}` placeholders emitted by
`src/manuscript_variables.py` and verified by
`scripts/z_generate_manuscript_variables.py`. See [`AGENTS.md`](AGENTS.md).

## Build from a clean checkout

Use the pinned [Template renderer](https://github.com/docxology/template/tree/87704feae0a4490ef7dad9c931d268e8c30273c2)
with Git, uv, Pandoc `3.14`, a matching pandoc-crossref, and the
[Template PDF and Beamer toolchain](https://github.com/docxology/template/blob/87704feae0a4490ef7dad9c931d268e8c30273c2/docs/guides/startup-and-setup.md).
Use TeX Live `2026` with LuaLaTeX, `latex-lab`, `pdfmanagement`, and
`tagpdf` for the tagged PDF. Install Beamer and XeLaTeX for the slide decks.
The build steps below run
without a model server. Retained benchmarks are read from their tracked
aggregates, which include observations collected in earlier runs.

Run from the standalone THALIA root with the desired commit checked out.
The physical working checkout allows Template to bind its receipt to the
canonical Git-tracked source.

```bash
thalia_source="$(pwd -P)"
thalia_commit="$(git rev-parse HEAD)"
render_workspace="$(mktemp -d)"
template_checkout="$render_workspace/template"
git clone https://github.com/docxology/template.git "$template_checkout"
git -C "$template_checkout" checkout --detach 87704feae0a4490ef7dad9c931d268e8c30273c2
mkdir -p "$template_checkout/projects/working"
git clone "$thalia_source" "$template_checkout/projects/working/thalia"
cd "$template_checkout/projects/working/thalia"
git checkout --detach "$thalia_commit"
uv sync --locked --extra dev --python 3.13

export MPLBACKEND=Agg
uv run --no-sync python scripts/run_seed_sensitivity.py
uv run --no-sync python scripts/run_compiler_generalization.py \
  --per-category 10 \
  --seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 \
  --gepa-iterations 4
uv run --no-sync python scripts/run_harness_eval.py
uv run --no-sync python scripts/run_compiler.py
uv run --no-sync python scripts/run_pipeline.py
uv run --no-sync python scripts/generate_figures.py
uv run --no-sync python scripts/run_demo.py

cd "$template_checkout"
uv sync --locked --python 3.14
uv run --locked --python 3.14 python \
  projects/working/thalia/scripts/z_generate_manuscript_variables.py
uv run --no-sync python scripts/pipeline/stage_03_render.py \
  --project working/thalia --skip-manuscript-hydration
uv run --no-sync python scripts/pipeline/stage_04_validate.py \
  --project working/thalia
```

The local token generator validates citations and labels, then verifies
the exact text of the hydrated sections. Pass
`--skip-manuscript-hydration` only after this fresh generation step.
Inspect `output/pdf/thalia_combined.pdf`, `output/web/index.html`,
`output/slides/`, and `output/reports/` inside the working checkout.
The render checks are separate from the release gate, which compares
retained input checksums before publication. The separate [release controls](../release_artifacts.md) describe the
final publication bundle and its consumer receipts.
