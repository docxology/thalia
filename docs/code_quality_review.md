# Thermo-Nuclear Code Quality Review — THALIA

**Date:** 2026-06-02
**Scope:** Full tree under `working/thalia` (`src/`, `tests/`, `scripts/`)
**Rubric:** [thermo-nuclear-code-quality-review](https://github.com/cursor/cursor-team-kit) (cursor-team-kit plugin)

## Executive verdict: **PASS** (after remediation)

Pre-remediation: **PASS WITH BLOCKERS**. Structural fixes below were applied in the same pass; the authoritative suite command is now recorded in `output/reports/verification_summary.json` and must meet the `src/` coverage gate from `pyproject.toml`. This avoids pinning transient pass/skip counts in a review document.

## Remediation summary

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

- Figure styling helpers are split into `src/figure_style.py`; the public `src.figures` plotting API remains stable for scripts/tests.
- Thin orchestrator scripts (except pre-fix `z_generate`, now slim).
- Zero-mock tests, executable invariants, linear five-stage pipeline.
- Clear stage boundaries and LM-behind-protocol invariant preserved.

## Verification

```bash
uv run --project working/thalia pytest working/thalia/tests/ \
  --cov=working/thalia/src --cov-report=term-missing --cov-fail-under=90
```

## Follow-up completed (evaluation package)

Split the former `evaluation.py` into [`src/evaluation/`](../src/evaluation/) (`dataset.py`, `budget.py`, `experiments.py`, `bundle.py`) with stable barrel exports.
