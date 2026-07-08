# THALIA — Publication-Readiness Assessment

_Deep review performed 2026-06-27. Verdict: **the package is publication-ready; the manuscript is ready pending one author-only action (citation verification).**_

## What was independently verified (real, working, validated)

A clean Linux environment was built from `pyproject.toml` (the committed `.venv`
is a macOS venv and does not run here) and the suite was executed end to end.

- **Tests:** 571 pass, 0 fail, 15 skipped. Every skip is an optional-dependency
  gate (8 require the `dspy` extra, 7 require a live Ollama model). With those
  extras installed the count reaches the README's ~580. No test is mocked
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

## The one blocker for external publication (author-only)

The commissioned bibliography contains **future-dated 2026 arXiv identifiers** and
one implausible ID — `zhang2025rlm` = `arXiv:2512.24601` (2512 is a future month;
24601 is Jean Valjean's prisoner number). These are transcribed "as provided" from
the commissioning brief, so I did **not** invent replacements (that would be
fabrication). I made the disclosure honest and uniform: every commissioned/future
entry is now tagged `(as provided)`, matching §09's statement.

**Before submitting to any venue, you must replace these with verified
identifiers** (or mark the works as unpublished/forthcoming without a spurious
number). A reviewer will flag `2512.24601` immediately. This is the single item
standing between the manuscript and external submission.

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
