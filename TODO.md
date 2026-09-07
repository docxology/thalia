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
