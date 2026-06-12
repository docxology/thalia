"""Episodic-first memory subsystem for the ATLAS harness.

Implements the two-tier architecture recommended by Zhang et al. (2026): a raw,
append-only episodic store that is never overwritten, plus an explicitly gated
consolidation step that derives (never mutates) a MEMORY.md snapshot.

* :mod:`src.memory.episodic_store` — SQLite (+ FTS5 when available) raw episodes.
* :mod:`src.memory.consolidation` — Retain/Delete/Consolidate gating logic.
"""

from .consolidation import (
    ConsolidationAction,
    ConsolidationCriteria,
    consolidate_snapshot,
    decide_action,
    derive_memory_delta,
    should_consolidate,
)
from .episodic_store import EpisodicStore

__all__ = [
    "EpisodicStore",
    "ConsolidationAction",
    "ConsolidationCriteria",
    "should_consolidate",
    "decide_action",
    "derive_memory_delta",
    "consolidate_snapshot",
]
