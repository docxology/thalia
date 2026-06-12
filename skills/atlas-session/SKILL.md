# SKILL.md — atlas-session

## Purpose
Persistent multi-turn conversation surface over the harness. Wraps `AutoHarness`
with disk-backed state: episodes persist to a SQLite file, the consolidated
MEMORY.md is read at start and written on consolidation, and the running
transcript is reconstructed from stored episodes so earlier turns are retrievable
after a process restart.

## Inputs
- `config: HarnessConfig | None` — harness configuration
- `lm: LMClient | None` — language model (default deterministic)
- `db_path: str` — SQLite path for episodes (`":memory:"` for ephemeral)
- `memory_path: str | Path | None` — MEMORY.md file (read at start, written on consolidation)

## Outputs (per `ask`)
- `HarnessOutput` — answer, citations, ranked evidence, task category, memory record

## Invocation
```python
from src.session import Session
s = Session(db_path="episodes.db", memory_path="MEMORY.md")
s.ask("My wifi password is bluefish42")
out = s.ask("What is the wifi password?")   # retrieves from the earlier turn
s.close()                                    # persists memory + closes the store
```

For explicit recall demos, pass `default_config().with_(recall_memory=True)` and
reopen the same `db_path`; `scripts/run_demo.py` records this deterministic path in
`output/data/demo_result.json`.

## Constraints
- Episodes are append-only; reopening resumes turn IDs (no collision).
- MEMORY.md is written only on consolidation (and on `close`), never overwriting episodes.
- Determinism preserved when the default LM is used.

## Related
CLI surface: `src/cli.py` / `scripts/run_query.py`. Configuration: `src/config.py`
(`load_config`, `save_config`, `ATLAS_*` env overrides).
