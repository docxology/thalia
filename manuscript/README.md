# `manuscript/` — ATLAS write-up

The full design and evaluation write-up, authored as numbered Markdown sections
that can be explicitly compiled to PDF/HTML by the template rendering pipeline.

## Sections

| File | Content |
|------|---------|
| `00_abstract.md` | Abstract |
| `01_introduction.md` | Motivation, the four foundations + substrate, contributions |
| `02_foundations.md` | Deep analysis of DSPy, RLMs, memory faults, agentic search, `template/` |
| `03_hermes_architecture.md` | Hermes prompt assembly + DSPy/GEPA self-evolution |
| `04_harness_design.md` | The five stages (methodology) with typed signatures |
| `05_template_integration.md` | `AGENTS.md`/`SKILL.md` duality + build lifecycle mapping |
| `06_active_inference.md` | Correspondences with the Free Energy Principle |
| `07_evaluation.md` | Deterministic local evaluation + explicit scope boundaries |
| `08_reference_architecture.md` | Design-principle table + file structure |
| `09_reproducibility.md` | Determinism, generated tokens, regeneration commands |
| `10_operability.md` | Configuration, real LM adapters, persistent session, CLI |
| `11_validation.md` | Invariants, Zero-Mock suite, golden regression, dashboard |
| `99_references.md` | Reference list (Pandoc `--citeproc`) |

Supporting files: `config.yaml` (metadata), `preamble.md` (LaTeX), `references.bib`
(bibliography), `SYNTAX.md` (citation/figure/equation conventions).

## Generated tokens

Numeric results in the prose are `{{…}}` placeholders emitted by
`src/manuscript_variables.py` and verified by
`scripts/z_generate_manuscript_variables.py`. See [`AGENTS.md`](AGENTS.md).
