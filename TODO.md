# THALIA — TODO

> **Canonical backlog:** [`tasks.yaml`](tasks.yaml) (task + Gantt source of truth,
> managed by the projects/taskboard server). This file does NOT duplicate the task
> roster — it records agent-ergonomics findings from the 2026-08-31 deep pass that
> are not taskboard tasks. Promote a finding to `tasks.yaml` when it becomes
> scheduled work, and delete it here.

## Minor

- [x] (2026-08-31) Broken link in `docs/integrity_advantage_handoff.md` (~line 270):
      target `../manuscript/12_supplemental_notation.md` used the pre-move path;
      fixed to `manuscript/12_supplemental_notation.md` (relative to `docs/`). — fixed this pass.
- [x] (2026-08-31) Stale directory link in `docs/README.md` (~line 15):
      `../manuscript/` did not exist at repo root (manuscript lives at
      `docs/manuscript/`); fixed to `manuscript/` (relative to `docs/`). — fixed this pass.

## Medium

- [x] (2026-08-31) Entry docs did not point to the canonical backlog: `README.md`
      and `AGENTS.md` never mentioned `tasks.yaml`, so a cold agent could not find
      "what to do next". Added a "Status & next actions" pointer in `README.md`
      linking `tasks.yaml` as the single backlog home. — fixed this pass.

## Major

- [x] (2026-08-31) **Manuscript-location migration landed.** The move
      `manuscript/` -> `docs/manuscript/` (28 tracked deletions + untracked new
      tree) plus matching doc-path fixes were verified on disk (all 28 migrated
      files present; 5 content diffs are intentional path updates), one remaining
      stale docstring reference fixed (`src/__init__.py`), and committed as the
      owner-authorized migration commit. Verify with:
      `git status --porcelain -- manuscript/ docs/manuscript/` (clean).

## Workflowz review — 2026-11-10

- [ ] **WF-THALIA-001 — P2 — Make bare CLI help non-executing while preserving the analysis demo.** **Outcome:** `thalia` / `scripts/run_query.py` with no arguments must show help or a concise usage message and exit without running a harness turn; the deterministic batch/demo behavior remains available through an explicit demo path (for example `run_demo()` or a dedicated demo entry point), and normal `--query`, `--json`, and configuration behavior is unchanged. **Evidence:** `src/cli.py:58` declares `--query` required; `src/cli.py:136-146` implements and documents a no-argument demo; `src/cli.py:155-158` dispatches every empty argument list to that demo before argparse can provide help; `scripts/run_query.py:23-26` exposes this behavior through the script wrapper. **Acceptance probe (repo root):** run `python -c "from src.cli import main; import io, contextlib; b=io.StringIO(); rc=0; ns={}; exec('with contextlib.redirect_stdout(b):\n    rc = main([])', globals(), ns); s=b.getvalue(); assert 'usage:' in s, s; assert 'answer' not in s, s"` after the change, then run `python -c "from src.cli import main; assert main(['--query','What is the wifi password?','--session-history','User: my wifi password is bluefish42','--json']) == 0"` and verify JSON is emitted. Also invoke the explicit demo path and verify it still returns the documented answer `bluefish42`. **Dependencies/constraints:** preserve the documented deterministic demo for analysis/render workflows by moving it behind an explicit entry point or adapting the caller; do not silently remove `scripts/run_demo.py` or change `HarnessOutput` serialization. If the batch renderer genuinely requires bare execution, document a separate explicit batch entry point instead of making the general CLI execute a query implicitly.
