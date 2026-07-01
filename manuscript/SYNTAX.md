# Manuscript syntax conventions

Pandoc/crossref conventions used across the THALIA manuscript sections.

## Sections

Each section heading carries a label: `# Title {#sec:slug}`. Cross-reference with
`[@sec:slug]` (renders "Section N"). Section slugs in use: `abstract`,
`introduction`, `foundations`, `hermes`, `harness_design`, `formalism`,
`added_methods`, `integration`, `active_inference`, `evaluation`,
`reference_architecture`, `reproducibility`, `operability`, `validation`,
`references`.

## Figures

Use the image form shown below, replacing the placeholder fields with a real
generated PNG and a registered figure label:

```markdown
image caption -> ../output/figures/name.png with label fig-label and width 70%
```

Figure slugs: `retriever_comparison`, `rrf_sensitivity`, `compiler_convergence`,
`consolidation`, `evidence_funnel`, `category_breakdown`, `noise_scaling`,
`mmr_tradeoff`, `method_ablation`.

## Tables

Pipe tables with a label line where cross-referenced; reference with `[@tbl:slug]`.
Table slugs: `headline_results`.

## Equations

`\begin{equation}\label{eq:slug} ... \end{equation}`; reference with `[@eq:slug]`.
Equation slugs: `optimization_problem`-style; in use: `bm25`, `rrf`, `mmr`,
`composite`.

## Citations

`[@key]` for parenthetical, `@key` for in-text; resolved from `references.bib` via
`--citeproc`. Multiple: `[@a; @b]`.

## Tokens

Generated numeric placeholders: `{{TOKEN_NAME}}` (uppercase, digits, underscores).
Use `{{…}}` (ellipsis) for meta-references that should not be substituted.
