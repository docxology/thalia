# `src/memory/` — Agent contract

Barrel package: `from src.memory import EpisodicStore, ConsolidationAction, …`

## Role

Two-tier, episodic-first memory subsystem following Zhang et al. (2026). Raw
conversational episodes are written once and never overwritten; a separately
gated consolidation step derives (never mutates) a MEMORY.md snapshot.

## Module map

| Module | Contents |
|--------|----------|
| [`episodic_store.py`](episodic_store.py) | `EpisodicStore` — SQLite-backed, append-only episode log with FTS5/LIKE search |
| [`consolidation.py`](consolidation.py) | Gate logic: `should_consolidate`, `decide_action`, `derive_memory_delta`, `consolidate_snapshot`; `ConsolidationAction`, `ConsolidationCriteria` |
| [`__init__.py`](__init__.py) | Barrel re-export of both modules |

## Key invariants

- **Append-only**: `EpisodicStore.append` raises `ValueError` on a duplicate
  `turn_id`. There is no update or delete path.
- **Dual-key gate**: `should_consolidate(flag, criteria) -> bool` returns `True`
  only when **both** the Reasoner's `requires_consolidation` flag is set **and**
  `criteria.any_met()` is true (session ending, novel task class, or explicit
  user request). Completing a turn alone is never sufficient.
- **Derived delta, untouched episode**: `derive_memory_delta` builds a Markdown
  bullet from the raw episode; `consolidate_snapshot` only appends under a
  stable heading — prior MEMORY.md content is preserved verbatim.
- **Search determinism**: `EpisodicStore.search` uses FTS5 `MATCH` when
  available, else a `LIKE` scan; either path is deterministic and order-stable.
  Natural-language queries are stripped to bare alphanumeric tokens before being
  passed to FTS5 to avoid syntax errors on punctuation (`?`, `-`, `"`, …).
- **No LM in this package**: all logic is pure Python / SQL.

## `EpisodicStore` API

```
EpisodicStore(db_path=':memory:')
  .append(entry: EpisodicEntry)          # raises ValueError on duplicate turn_id
  .get(turn_id: int) -> EpisodicEntry | None
  .all() -> list[EpisodicEntry]          # ascending turn_id order
  .count() -> int
  .max_turn_id() -> int                  # -1 when empty; use for next-id derivation
  .search(query: str, limit: int) -> list[EpisodicEntry]
  .close()                               # also a context manager
```

## Consolidation logic

```
decide_action(requires_consolidation, criteria, memory_exists) -> ConsolidationAction
  NONE          — gate closed (no write)
  APPEND_MEMORY — gate open, no prior memory
  UPDATE_MEMORY — gate open, explicit_request AND memory already exists
```

`ConsolidationCriteria(session_ending, novel_task_class, explicit_request)` —
frozen dataclass; `.any_met()` is the second key in the dual-key gate.

`EXPLICIT_MEMORY_MARKERS` — tuple of string cues (`"remember"`, `"note that"`,
…) used by `has_explicit_memory_cue(query)`.

## Extension points

- Replace the default `':memory:'` with a file path for persistence.
- `consolidate_snapshot` is a pure function; swap it if the MEMORY.md format
  needs a richer structure.
- `has_explicit_memory_cue` checks the marker list; extend
  `EXPLICIT_MEMORY_MARKERS` for additional languages or cue styles.

## `__all__` exports

`EpisodicStore`, `ConsolidationAction`, `ConsolidationCriteria`,
`should_consolidate`, `decide_action`, `derive_memory_delta`,
`consolidate_snapshot`
