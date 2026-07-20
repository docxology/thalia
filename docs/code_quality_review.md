# Thermo-Nuclear Code Quality Review — THALIA

**Date:** 2026-06-02 (initial) · **2026-07-05** (follow-up pass)
**Scope:** Full tree under `working/thalia` (`src/`, `tests/`, `scripts/`)
**Rubric:** [thermo-nuclear-code-quality-review](https://github.com/cursor/cursor-team-kit) (cursor-team-kit plugin)

## Executive verdict: **PASS**

**2026-06-02:** Pre-remediation **PASS WITH BLOCKERS**; structural fixes applied in the same pass.

**2026-07-05:** Pre-remediation **PASS WITH BLOCKERS** (unwired architectural figures, `figures.py` >1k LOC, harness/pipeline duplication). All ranked blockers and moderate findings remediated; suite gate confirmed below.

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
cd /path/to/thalia && uv run pytest tests/ \
  --cov=src --cov-report=term-missing --cov-fail-under=90

# From template checkout
uv run --project working/thalia pytest working/thalia/tests/ \
  --cov=working/thalia/src --cov-report=term-missing --cov-fail-under=90
```

`src/provenance.py::write_verification_summary` (called from `src/demo.py::
build_demo_artifacts`, itself invoked by `scripts/run_demo.py`, and separately
from `scripts/build_dashboard.py`) writes
[`output/reports/verification_summary.json`](../output/reports/verification_summary.json).
**Corrected 2026-07-15:** that file is *not* a live results record — every call
site invokes it with no `summary=` argument, so it always falls back to
`default_verification_summary()`'s placeholder (`status: "commands-documented"`,
blank observed fields). It documents which commands to run, not what a run
produced. This project deliberately does not track a machine-written coverage
snapshot as its numeric SSOT (see `.gitignore`'s note on `coverage_project.json`,
removed 2026-07-15 as a stale, gitignored-but-still-tracked artifact) — the
authoritative pass/fail/coverage numbers for any given checkout are whatever a
fresh run of the documented gate reports, cross-checked against
[`PUBLICATION_READINESS.md`](../PUBLICATION_READINESS.md)'s most recent dated run.

**Status:** PASS for the 2026-07-05 remediation pass (suite gate confirmed by the
manuscript-integrity test `test_count_bearing_docs_use_generated_verification_summary`,
which fails if any count-bearing doc hard-codes a stale pass/skip/coverage literal
— it does not, and cannot, confirm that `verification_summary.json` itself holds
real numbers, since the test never inspects that file's content).

## 2026-07-18 iterative follow-up

The source-to-artifact chain was rechecked after a first-principles review of
state, determinism, and evidence boundaries. The authoritative local gate now
reports **665 passed, 0 skipped, 98.82% `src/` coverage**. Additional regression
coverage protects defensive pipeline snapshots, sparse persisted turn ids,
restart-safe Memory Gate novelty, strict retrieval/config weights, and a
fail-closed artifact manifest validator. The generated output manifest checked
34 artifacts (32 required) before the final template render, including the
generated title-page cover visual abstract.

The LongMemEval recorder was not silently treated as refreshed: its live
benchmark path did not finish during this pass, so the existing aggregate is
retained as prior evidence and is not cited as a new measurement.

## Follow-up completed (evaluation package)

Split the former `evaluation.py` into [`src/evaluation/`](../src/evaluation/) (`dataset.py`, `budget.py`, `experiments.py`, `bundle.py`) with stable barrel exports.
