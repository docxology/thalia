# THALIA — Publication-Readiness Assessment

_Deep review refreshed 2026-07-22. Verdict: **the deterministic package and retained v1 evidence chain pass the local gates; the ambitious v2 live campaign remains partial and is not promoted. Final manuscript/PDF release assembly is therefore held until an accepted campaign aggregate exists.**_

## Current loop status — 2026-07-22

The project-wide review completed the authoritative local suite and tightened the
release contracts without touching the sibling template or replacing retained
evidence:

- **Authoritative suite:** **765/765 tests passed**, with **92.39%** `src/`
  coverage against the 90% gate and resource warnings treated as errors. Ruff,
  mypy, compileall, lock validation, and deterministic-core import all pass.
- **Integrity gates:** the fail-closed artifact validator passes **42 checked / 41
  required paths**; manuscript token coverage, cross-reference integrity, a new
  bibliography-key check, paper-audit/formalism traceability, and claim-ledger
  artifact checks pass. The claim ledger includes the retained benchmark
  identity/digest, denominators, model-dependent probes, compiler candidate
  evaluations, and the final test/coverage denominator.
- **Statistics/accounting:** held-out compiler accounting now includes both the
  final method evaluations and all compiler candidate-training evaluations; the
  aggregate is not allowed to describe only the three final scores as the full
  executed sample.
- **Scholarship:** the manuscript now distinguishes source-reported external
  findings from THALIA replications, qualifies the agentic-search claim to what
  the checked source abstract establishes, and places the SQLite/FTS5 citation at
  the claim it supports. Primary scholarly records and identifiers were checked;
  source-reported empirical findings remain external evidence.
- **v2 campaign:** the external resumable run completed all three Gemma tiers
  (100/250/500; 850 complete rows, zero failures). The matched Hermes-100 tier
  was safely paused after three consecutive Ollama timeouts (0 complete, 3
  failed rows), preserving its checkpoint and producing a partial campaign
  report. Checkpoint/report parsing now rejects duplicate examples, scope or
  model-provenance mismatches, missing digests/options, and incomplete counts;
  interrupted runs explicitly account for tiers not yet started. Hermes,
  bottleneck, and cross-model promotion therefore remain pending; no partial v2
  tier is promoted. The historical 500 extractive / 50 neural LongMemEval and
  retained bottleneck aggregates remain prior evidence.
- **Checkpoint recovery:** a bounded resume audit detected a code-scope change
  before it could overwrite the campaign report. The original complete
  `gemma-100` checkpoint was reconstructed from the unchanged 853-row report;
  the interrupted 37-row attempt remains as a forensic sidecar. Scope-mismatched
  checkpoints now fail closed unless `--allow-scope-change` is explicitly used.
- **Generated evidence:** the deterministic 10-seed sensitivity and held-out
  compiler aggregates are validated and feed generated manuscript variables,
  tables, captions, figures, dashboard, and artifact manifests. These outputs
  are reproducible package evidence, not a substitute for the incomplete live
  v2 campaign.
- **Release boundary:** the existing 53-page PDF and its visual inspection remain
  prior-artifact evidence. Because the v2 campaign is incomplete, the combined
  PDF has not been rerendered or represented as the final v2 release; the
  supplementary slides remain separately bounded drafts because of their known
  renderer/layout issues.
- **PDF audit note:** the retained PDF is readable and visually checked across
  title, contents, statistical, benchmark, bottleneck, backend, and reference
  pages. Its LaTeX logs contain one non-fatal underfull-box warning and no fatal,
  undefined-reference, or overfull-box errors. The older template-side
  `output/reports/validation_report.json` is a stale standalone-structure
  snapshot and is not treated as current release evidence; the THALIA-local
  fail-closed validator is authoritative until the accepted campaign permits a
  fresh external render.

## Prior verified loop status — 2026-07-21

The historical snapshots below are retained for provenance. The current source
tree was re-audited through the Science and First-Principles workflows, with
iterative regeneration and refusal-path checks:

- **Suite:** 745 tests passed with `PYTHONWARNINGS=error::ResourceWarning` and
  `src/` coverage at **94.00%** against the 90% gate. `uv lock --check`,
  compilation, deterministic core import, wheel construction, and isolated
  `import src` also pass. The run included the live DSPy, Gemma, embedding, and
  LongMemEval paths available on this host.
- **Artifact integrity:** the final fail-closed generated manifest validates all
  **39 required paths** declared by `domain_profile.yaml` (**40 artifacts
  checked**). The required set includes the per-example ledger, deterministic
  event stream, accounting report, paper/formalism audit, statistical-audit
  figures, and generated data/figures; mutated or unsafe manifest entries are
  covered by regression tests.
- **Statistical evidence:** the seeded research audit contains 5,550 unique
  examples and 16,650 method evaluations across four deterministic strata, five
  seeds, and six categories. Marginal means use fixed-stratum bootstrap intervals;
  primary and stratum-level method deltas use aligned pairs with whole-seed-cluster
  resampling. Wilson intervals, exact paired binary tests, and a complete Holm
  family (40 comparisons in the canonical grid) are recorded with estimands and
  provenance rather than inferred from plots.
- **Recorder evidence:** the current live recorders account for 30 injection
  probes, 32 learned-retrieval probes, and 24 balanced backend examples. The
  LongMemEval recovery baseline remains 500 extractive / 50 neural examples;
  resumable checkpointing is available for future 100/250/500 neural runs, but
  no larger neural result is fabricated. The retained bottleneck aggregate is
  30 neural questions per sweep setting (90 completed question-configuration
  rows across the retained sweep); a larger refresh exceeded local neural
  capacity and left that validated aggregate unchanged.
- **Traceability:** pipeline intermediates are defensive snapshots, session
  restart allocation uses the maximum persisted turn id, and Memory Gate
  novelty survives reopening an episodic store. The formalism registry resolves
  **17 formal objects**, **4 composition edges**, and **8 audited claims** to
  code, tests, equations, manuscript sections, and required artifacts.
- **Manuscript injection:** 133 referenced variables are generated from live
  configuration, aggregates, provenance, and statistical ledgers. The standalone
  generator now fails closed on missing tokens, dangling references, and
  result-bearing numeric literals left hardcoded in numbered manuscript prose.
- **Scope boundary:** the deterministic core remains extractive-bounded and the
  semantic lane remains a hashing sub-word surrogate. The live neural and
  learned-retrieval recorders are evidence from the available local models, not
  deterministic headline results.
- **Visual and layout refinement:** the architecture figure now exposes the
  stage verbs and deterministic glyphs; evidence figures annotate retention and
  concrete citation gaps; the statistical forest now shows exact paired
  stratum-level intervals, adjusted q-values, and failure accounting; and the
  memory-lifecycle schematic uses wrapped labels and explicit margins so its
  append-only and dual-key branches remain legible after manuscript scaling; and
  the manuscript adds a generated title-page visual abstract (`thalia_cover`) that
  maps the five-stage harness, evidence flow, compiler boundary, and scope
  limits. The manuscript source retains the checked compact geometry
  (`left/right=0.38in`, `top=0.42in`, `bottom=0.45in`), and the external render
  confirms a 53-page letter artifact.
- **Rendered release gate:** the external template pipeline was run after the
  final artifact regeneration through `scripts/render_pdf_external.py --validate`.
  The **53-page** letter PDF is **3,761,743 bytes** and passed PDF validity,
  transmission bookends, Markdown, figure/evidence registries, project overlays,
  and artifact-manifest validation. The LaTeX log has no overfull boxes, fatal
  errors, undefined citations, unresolved cross-references, or generated-token
  markers; one non-fatal underfull bibliography box remains for the long
  template citation title. The cover was visually checked as title/subtitle →
  enlarged full-width visual abstract → author/ORCID/DOI/date, with
  `DOI: forthcoming` supplied by publication configuration. Representative
  statistical-audit, benchmark, bottleneck, injection, operability, and
  references pages were rendered to PNG and visually inspected. The template
  validator's output-structure check remains an explicitly external,
  non-fatal warning: its report marks that check false because the optional
  simulations/, llm/, and logs/ directories are absent, while the validation
  summary records no critical issues and exits successfully. The adapter leaves
  no persistent THALIA link and the sibling checkout remains untouched; this
  boundary is reported rather than promoted to a local pass.
  SHA-256: `2d5676f172566758936eaab481e2d79f0a0338de61619feb19d1443b5c704dff`.
- **Supplementary slide boundary:** all 21 Beamer PDFs are structurally valid
  and pass the template validator, but the external renderer still emits
  overfull-box warnings for several figure-heavy decks; visual inspection
  shows title-only or clipped figure frames in those supplementary slides. The
  combined manuscript PDF is unaffected and was inspected separately. Treat
  the slide decks as presentation drafts until the renderer's figure/frame
  splitting is fixed upstream or in a dedicated slide-source pass.
- **External evidence:** LongMemEval_S was downloaded and validated (500 items;
  277,383,467 bytes; SHA-256
  `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`), then
  recorded with 50 neural examples. Gemma and nomic-embed-text provenance,
  digests, prefixes, and generation options are preserved in the refreshed
  aggregates.

## Historical 2026-06-27 snapshot

## What was independently verified (real, working, validated)

A clean Linux environment was built from `pyproject.toml` (the committed `.venv`
is a macOS venv and does not run there) and the suite was executed end to end.

- **Tests (historical environment):** the historical run completed with no
  repository failures after the noted fixes; its exact counts are intentionally
  not treated as current evidence. No test is mocked (zero-mock policy holds).
- **Coverage:** the historical run exceeded the 90% `src/` gate; run the current
  command for the live percentage.
- **Invariants:** all **13/13** hold, including `recency_zero_noop` — which was
  *failing at HEAD* until fixed (see below).
- **Artifacts:** the historical generator sweep exercised preflight, eval,
  compiler, pipeline, figures, dashboard, demo, query CLI, and the gated
  DSPy/learned/injection recorders.
- **Manuscript integrity:** 85 `{{TOKEN}}` variables referenced, all generated
  from live code, zero missing; all `@sec:`/`@fig:`/`@eq:` cross-references
  resolve; all 24 bib keys are used.

## Bugs found and fixed (these made the headline claims actually true)

1. **Cross-platform determinism leak (real defect, was failing at HEAD).**
   The semantic lane ranked four equal-relevance windows as `[1,0,2,3]` instead
   of `[0,1,2,3]` because one cosine differed by ~2e-16 (NumPy float-summation
   noise), flipping the RRF order. The "bit-for-bit deterministic" claim was
   therefore platform-dependent. **Fix:** round lane sort-keys to 12 dp in
   `semantic.py` and `lexical.py` so float-noise ties break deterministically on
   index. The `recency_zero_noop` invariant now holds; no committed figure or
   token value changed (regression tests still pass).
2. **`requires-python = ">=3.10"` was untrue (19 tests failed on 3.10).** Core
   modules `import tomllib` (Python 3.11+ only). **Fix:** `tomllib`→`tomli`
   fallback in `provenance.py`, `manuscript_variables.py`, and `test_pipeline.py`,
   plus a conditional `tomli` dependency. The package now genuinely runs on 3.10.

## Improvements and additions made

- **Visualization:** `pipeline_flow` figure relabeled from truncated query strings
  ("When is the car servic…") to clean task-category labels (Temporal, Preference,
  Code, …), consistent with the rest of the evaluation. Title casing fixed.
- **Manuscript (honesty + consistency):**
  - Tightened the one boundary-blurring sentence (§07b) so the *surrogate*
    semantic lane is no longer conflated with a *learned dense embedder*.
  - Softened "near-useless" → "far below usable accuracy (a bound on answer
    phrasing, not retrieval)" to match the localisation finding.
  - Qualified the abstract's "recovers accuracy automatically" to "recovers most
    of that gap on the neural subset, up to the manually-tuned best."
  - Added an "easy-set ⇒ tie expected" caveat to the §11 dense-RAG-parity result.
  - Added the missing §10 (operability) and §11 (validation) to the Reader's guide.
  - Tokenized two hard-coded `90` coverage values (§09, §11) so they track
    `{{CONFIG_COV_GATE}}`.
  - Trimmed editorializing prose ("…and worth it").
- **Docs:** README test/coverage/token counts corrected to the precise figures.

## Citation status (author-only) — independently checked 2026-07-21

The previously disclosed forward-dated entries have now been resolved against
primary records and the bibliography has been corrected. `zhang2025rlm`,
`zhang2026memory`, `sen2026grep`, `li2026timem`, and `banerjee2026apexmem` now
carry their verified arXiv identifiers and URLs. The template citation now
uses the current Zenodo record and DOI. Recheck versions and venue metadata at
submission, but no placeholder or deliberately withheld identifier remains in
these entries.

## Recommended (non-blocking) polish

- Prune the remaining "honest/honestly/honesty story" meta-asides (~6 instances) —
  the candor is a strength but is over-narrated.
- Consolidate the "slack vs. binding budget" explanation (restated ~5× across §07d–e).
- Move the inline `<style>` block out of `00_abstract.md` into the render template.
- 5 generated tokens are unused (`CONFIG_CONTEXT_BUDGET`, `RESULT_BN_RECALL_*`);
  reference or drop them.

## Bottom line

The code is real, deterministic (now genuinely cross-platform), fully tested, and
honestly scoped. Two real bugs that contradicted headline claims are fixed. The
manuscript is structurally complete and unusually candid. **It is ready to publish
the package now and ready to submit the manuscript as soon as the commissioned
citations are verified.**

## 2026-07-06 follow-up (post restructure)

- **Figure count is now 23, not 19.** The former single-file DSPy runtime was split
  into the `src/dspy_runtime/` package (the import surface `from src.dspy_runtime
  import …` is unchanged); the evaluation package and figure module were likewise
  split (`src/figures/{plots,diagrams,manifest}.py`). All prose references to the
  former single-file paths were updated to the package form. Three figures that were generated but never embedded
  (`pipeline_flow`, `gepa_trajectory`, `category_components`) were added to §07e with
  honest captions, closing the last orphaned-figure gap.
- **Token coverage:** generated variables are checked against the manuscript by
  the live token-coverage gate. Optional recorder variables may remain absent when
  their external services are unavailable; none are treated as hand-authored
  evidence.
- **Suite health (historical):** a transient import-graph break from an untracked
  shadow package was removed. Run the current standalone gate to establish live
  collection, skips, and coverage.
