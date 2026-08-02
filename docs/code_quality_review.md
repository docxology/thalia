# Thermo-Nuclear Code Quality Review — THALIA

**Date:** 2026-06-02 (initial) · **2026-07-05** (follow-up pass) ·
**2026-08-02** (full manuscript and release red-team)
**Scope:** Full standalone THALIA tree (`src/`, `tests/`, `scripts/`)
**Rubric:** [thermo-nuclear-code-quality-review](https://github.com/cursor/cursor-team-kit) (cursor-team-kit plugin)

## Executive verdict: **PASS WITH RELEASE CONDITIONS**

**2026-06-02:** Pre-remediation **PASS WITH BLOCKERS**; structural fixes applied in the same pass.

**2026-07-05:** Pre-remediation **PASS WITH BLOCKERS** (unwired architectural figures, oversized figure module, harness/pipeline duplication). The ranked blockers and moderate findings were remediated; run the current standalone gate for live evidence.

**2026-08-02:** The full strict suite, source-bound artifact chain, enlarged
finite-set audit, manuscript injection, visual figure review, external PDF
validation, and correctly rooted browser check passed. The release boundary is
still conditional: the deterministic package and methods evidence are ready for
review, while P0 integrity confirmation, expert-rater quality, production
acceptance, and any broad neural/generalization claim remain separate gates.

### 2026-08-02 red-team improvements

| Area | Improvement and evidence |
|------|---------------------------|
| Manuscript injection | Added an independent source-to-injected tree verifier that checks numbered-file parity, exact substitution, unresolved tokens, and content drift; regression tests cover each failure class. |
| Experiment controls | Added explicit CLI grids and seed arguments for the enlarged publication audit and held-out compiler run while preserving fast smoke defaults. The generated JSON records requested/completed/failure accounting and finite-cluster interpretation. |
| Statistical communication | Corrected the small-cluster wording so a non-triggered diagnostic is not presented as population validation; retained descriptive interval language and Holm-family metadata. |
| Visual evidence | Improved sample-size tick labels and figure margins; changed zero-rounded p-value labels to inequality notation; regenerated and visually inspected the affected figures. |
| Rendered outputs | Regenerated variables, figures, dashboard, PDF, HTML, and slides in dependency order. External validation and a real browser load from the artifact root confirmed the sibling figure paths, image completeness, and viewport fit. |
| Evidence boundary | Kept the MIPRO-style finite-cluster signal and lexical injection result screen-only/unpromoted; no local metric was upgraded into answer quality, true-source recovery, or production evidence. |

## 2026-07-05 remediation summary

| Finding | Action taken |
|---------|----------------|
| F1 — Architectural figures orphaned from generator | Wired `plot_thalia_overview`, `plot_foundations_map`, `plot_memory_lifecycle`, `plot_gepa_evolution_loop` in `scripts/generate_figures.py`; tests assert PNG existence |
| F2 — `figures.py` at 1024 lines | Split into `src/figures/{plots,diagrams,manifest}.py`; stable `from src.figures import …` surface |
| F3 — `Pipeline` / `AutoHarness` duplication | `AutoHarness.forward` delegates to `Pipeline.with_all_stages().run(...)`; shared `memory_gate`; `session_ending` + `turn_id` on `Pipeline.run` |
| F4 — Loose `dict` on committed JSON plots | `src/evaluation/schemas.py` dataclasses; parse at script boundary; typed plot function signatures |
| F13 — Figure registry ahead of generator | `src/figures/manifest.py` SSOT (`FIGURE_MANIFEST`, `FIGURE_LABELS`, `COMMITTED_FIGURES`); `provenance.py` imports labels |
| F6 — `dspy_runtime.py` mixed concerns | Package `src/dspy_runtime/{adapters,runtime,live_eval}.py`; barrel re-exports preserve import surface |
| F9 — `PipelineContext` erases types | Fields typed to `signatures.payloads`; `adaptive_max_windows` import at module top |

## 2026-06-02 remediation summary

| Finding | Action taken |
|---------|----------------|
| Consolidation marker drift | `EXPLICIT_MEMORY_MARKERS` + `has_explicit_memory_cue()` in `memory/consolidation.py`; Reasoner emits `explicit_request`; harness wires it to MemoryGate |
| Evaluation sweep duplication + JSON/figure budget mismatch | `_tight_eval_config()`, `_metric_sweep()`; `run_full_eval()` sweeps omit loose `base=` |
| `signatures.py` multi-responsibility | Split into `src/signatures/{framework,payloads,stages}.py` barrel-exported from `__init__.py` |
| Lazy recall import | Top-level import in `harness.py`; typed `EpisodicStore \| None` |
| Script logic in `z_generate_manuscript_variables.py` | Moved to `src/manuscript_integrity.py`; script ~65 LOC orchestration only |
| `test_*_extra.py` sprawl | Merged into canonical `test_<module>.py` files; five `*_extra` files removed |
| Ghost doc `retriever_quality_curve` | Replaced with `rrf_weight_sweep` in `method_ablation` docstring |

## Ranked findings (pre-fix audit)

### 1. Consolidation marker drift — **blocker (fixed)**

Reasoner `_REMEMBER_MARKERS` and MemoryGate `_EXPLICIT_MARKERS` diverged (`do not forget`, `make a note` only in Reasoner). Harness did not pass explicit intent to MemoryGate.

**Fix:** Single canonical list in `consolidation.py`; `explicit_request` on Reasoner output; harness passes `explicit_request=reasoned.get("explicit_request")`.

### 2. Evaluation budget SSOT — **blocker (fixed)**

`run_full_eval()` passed headline `config` into sweeps while figures used the default tight budget — JSON and PNG could disagree.

**Fix:** Sweeps in `run_full_eval()` use default tight budget (`rrf_weight_sweep(dataset)` without `base=config`).

### 3. Sweep boilerplate — **structural (fixed)**

Four functions repeated `top_k=2, max_evidence=2` and step loops.

**Fix:** `TIGHT_TOP_K`, `TIGHT_MAX_EVIDENCE`, `_tight_eval_config()`, `_metric_sweep()`.

### 4. `signatures.py` at 429 lines — **moderate (fixed)**

Framework, payloads, and stage contracts in one file.

**Fix:** `src/signatures/` package with stable `from src.signatures import …` surface.

### 5. Manuscript gates in script — **layer leak (fixed)**

Token/crossref validation lived in `scripts/z_generate_manuscript_variables.py`.

**Fix:** `src/manuscript_integrity.py`.

### 6. Test layout drift — **process (fixed)**

Five `*_extra.py` files contradicted `tests/AGENTS.md` one-file-per-module rule.

**Fix:** Merged into `test_config`, `test_cli`, `test_inspector`, `test_retriever`, `test_reasoner`, `test_harness`, `test_evaluation`, `test_figures`.

### 7. Lazy recall import — **low (fixed)**

**Fix:** Module-level import in `harness.py`.

### 8. `classify_task` in Reasoner — **fixed (follow-up)**

Keyword table moved to [`src/routing.py`](../src/routing.py); harness and stages import from there. [`tests/test_routing.py`](../tests/test_routing.py) added.

### 9. Loose `list` on signature fields — **fixed (follow-up)**

Stage signatures in [`src/signatures/stages.py`](../src/signatures/stages.py) now use `list[EvidenceWindow]`, `list[RankedEvidence]`, `list[EvidenceCitation]`.

## What already passed

- Figure styling helpers in `src/figure_style.py`; plotting API in `src/figures/` (plots + diagrams + manifest SSOT).
- Thin orchestrator scripts (except pre-fix `z_generate`, now slim).
- Zero-mock tests, executable invariants, linear five-stage pipeline.
- Clear stage boundaries and LM-behind-protocol invariant preserved.

## Verification

```bash
# From the canonical THALIA checkout
cd /path/to/thalia && PYTHONWARNINGS=error::ResourceWarning uv run --project . --extra dev python -m pytest tests/ \
  --cov=src --cov-report=term-missing --cov-report=json:output/reports/coverage.json \
  --junitxml=output/reports/pytest.xml --cov-fail-under=90

# Template-side validation is external and optional; use the standalone command
# above for this checkout's authoritative code gate.
```

`src/provenance.py::write_verification_summary` (called from `src/demo.py::
build_demo_artifacts`, itself invoked by `scripts/run_demo.py`, and separately
from `scripts/build_dashboard.py`) writes
[`output/reports/verification_summary.json`](../output/reports/verification_summary.json).
The summary preserves the canonical commands and, after the strict suite and
artifact sweep, records the observed test count, coverage, lock/compile/package
checks, and validator result. A fresh gate remains authoritative for a new
checkout; the generated record is evidence from the last completed local run,
not a substitute for rerunning it. The project deliberately does not track a
machine-written coverage snapshot as its numeric SSOT (see `.gitignore`'s note
on `coverage_project.json`, removed 2026-07-15 as a stale, gitignored-but-still
tracked artifact).

**Status:** The latest generated record is a passing local run; exact counts and
coverage remain in `output/reports/verification_summary.json`. The
manuscript-integrity test `test_count_bearing_docs_use_generated_verification_summary`
also prevents count-bearing prose from drifting to frozen pass/skip/coverage
literals.

## 2026-07-18 iterative follow-up

The source-to-artifact chain was rechecked after a first-principles review of
state, determinism, and evidence boundaries. The authoritative local gate is the
standalone command documented in `README.md`; this review intentionally embeds no
stale pass/skip/coverage count. Additional regression coverage protects defensive
pipeline snapshots, sparse persisted turn ids, restart-safe Memory Gate novelty,
strict retrieval/config weights, and a fail-closed artifact manifest validator.
Artifact counts are derived from the live output tree before validation.

The LongMemEval recorder was not silently treated as refreshed: its live
benchmark path did not finish during this pass, so the existing aggregate is
retained as prior evidence and is not cited as a new measurement.

## Follow-up completed (evaluation package)

The evaluation package is organized under [`src/evaluation/`](../src/evaluation/) (`dataset.py`, `budget.py`, `experiments.py`, `bundle.py`) with stable barrel exports.
