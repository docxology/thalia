# THALIA — Publication-Readiness Assessment

_Deep review performed 2026-06-27. Verdict: **the package is publication-ready; the manuscript is ready pending one author-only action (citation verification).**_

## Current loop status — 2026-07-18

The historical snapshots below are retained for provenance. The current source
tree was re-audited through the Science and First-Principles workflows, with
iterative regeneration and refusal-path checks:

- **Suite:** 665 tests passed, 0 skipped; `src/` coverage is **98.82%** against
  the 90% gate. The run included the real DSPy path and live Ollama-gated tests
  available on this host.
- **Artifact integrity:** the generated manifest validates **34 artifacts**,
  including all 32 required paths declared by `domain_profile.yaml`; mutated or
  unsafe manifest entries are covered by regression tests.
- **Traceability:** pipeline intermediates are defensive snapshots, session
  restart allocation uses the maximum persisted turn id, and Memory Gate
  novelty survives reopening an episodic store.
- **Scope boundary:** the deterministic core remains extractive-bounded and the
  semantic lane remains a hashing sub-word surrogate. The live neural and
  learned-retrieval recorders are evidence from the available local models, not
  deterministic headline results.
- **Visual and layout refinement:** the architecture figure now exposes the
  stage verbs and deterministic glyphs, the evidence figures annotate retention
  and concrete citation gaps, and the manuscript adds a generated title-page
  visual abstract (`thalia_cover`) that maps the five-stage harness, evidence
  flow, compiler boundary, and scope limits. The manuscript uses a checked
  compact geometry (`left/right=0.38in`, `top=0.42in`, `bottom=0.45in`). The
  rendered PDF is 45 pages; the TeX geometry log reports 27.46pt side margins
  and 30.35/32.52pt top/bottom margins.
- **Rendered release gate:** the template-side PDF, HTML, and slide outputs pass
  PDF validity, transmission, Markdown, structure, figure-registry (24 figures),
  evidence-registry, project-overlay, and artifact-manifest checks. The project
  remains a sidecar checkout symlinked from the template repository; the source
  files are present in the canonical sidecar and the project-local artifact
  manifest passes.
- **Remaining evidence caveat:** the LongMemEval recorder refresh is deferred
  because its live benchmark path did not complete within this pass; the
  existing aggregate is retained as prior evidence and is not presented as a
  new measurement.

## Historical 2026-06-27 snapshot

## What was independently verified (real, working, validated)

A clean Linux environment was built from `pyproject.toml` (the committed `.venv`
is a macOS venv and does not run here) and the suite was executed end to end.

- **Tests (historical environment):** 571 pass, 0 fail, 15 skipped. Every skip
  was an optional-dependency gate in that environment. No test is mocked
  (zero-mock policy holds).
- **Coverage:** **98.13%** on `src/` (gate 90%), matching the README's claim.
  My first run showed 96% only because 20 tests were fast-failing on the bug below.
- **Invariants:** all **13/13** hold, including `recency_zero_noop` — which was
  *failing at HEAD* until fixed (see below).
- **Artifacts:** all generator scripts run and write real outputs — preflight,
  eval bundle, compiler, pipeline, **19 figures** (300 DPI), dashboard, demo,
  query CLI, and the gated DSPy/learned/injection recorders.
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

## Citation status (author-only) — corrected 2026-07-15

**This section previously (2026-06-27) described `zhang2025rlm`'s implausible
arXiv ID as still present and instructed replacing it. That is now stale: a
reader following the old wording would search `manuscript/references.bib` for
an ID that no longer exists there.**

The commissioned bibliography contained **future-dated 2026 arXiv identifiers**
and one implausible ID — `zhang2025rlm` = `arXiv:2512.24601` (2512 is a future
month; 24601 is Jean Valjean's prisoner number). These were transcribed "as
provided" from the commissioning brief. The remediation actually applied was
**disclosure, not replacement**: `zhang2025rlm`'s entry now reads `journal =
{Preprint, forthcoming; arXiv identifier unverified}` with a note that the
implausible ID "has been withheld pending independent verification; do not
cite a spurious identifier." Five other commissioned/forward-dated 2026 entries
carry the same honest-disclosure treatment, matching §09's statement.

**Before submitting to any venue, verify each `(as provided)`/"identifier
unverified" entry** — find its real arXiv/DOI identifier if one exists, or mark
it as unpublished/forthcoming with no identifier at all. Disclosure prevents a
reviewer from catching a fabricated number, but does not substitute for
verification; a venue may still require every citation resolve to a real,
checkable source before acceptance.

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

- **Figure count is now 23, not 19.** The `src/dspy_runtime.py` module was split
  into the `src/dspy_runtime/` package (the import surface `from src.dspy_runtime
  import …` is unchanged); the evaluation package and `src/figures.py` were likewise
  split (`src/figures/{plots,diagrams,manifest}.py`). All prose references to the
  old `src/dspy_runtime.py` / `src/figures.py` single-file paths were updated to the
  package form. Three figures that were generated but never embedded
  (`pipeline_flow`, `gepa_trajectory`, `category_components`) were added to §07e with
  honest captions, closing the last orphaned-figure gap.
- **Token coverage:** 85 of 100 generated tokens are referenced. The 15 unused are
  all gated on absent recorder artifacts — 14 are the OpenRouter block (only emitted
  when `data/openrouter_eval.json` exists, i.e. `THALIA_OPENROUTER_API_KEY` set) and
  one is `CONFIG_CONTEXT_BUDGET`. None are dead hand-authored literals.
- **Suite health (2026-07-06):** 649 passed, 4 skipped, `src/` coverage 99.54%. A
  transient import-graph break (an untracked `src/dspy/` shadow package colliding
  with the third-party `dspy-ai` dependency) was removed; the suite now collects and
  passes end to end.
