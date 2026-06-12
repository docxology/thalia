"""Memory recall: surface relevant past episodes + MEMORY.md as evidence.

The episodic store records every turn, but a single ``forward`` only inspects the
session history it is handed. Recall closes that loop: at inference it searches the
append-only :class:`EpisodicStore` and the frozen MEMORY.md snapshot for
query-relevant content and returns it as :class:`EvidenceWindow` objects the
Retriever can rank alongside session windows. It is **read-only** — it never writes
or mutates the store — and off by default (`recall_memory`).

Recalled windows use *negative* source indices so they never collide with the
0-based session indices, keeping citations unambiguous.
"""

from __future__ import annotations

from .memory.episodic_store import EpisodicStore
from .module import tokenize
from .signatures import EvidenceWindow

# Source-index bases that cannot collide with non-negative session indices.
_EPISODE_INDEX_BASE = -1
_MEMORY_INDEX_BASE = -10_000


def recall_evidence(
    store: EpisodicStore,
    memory_md: str,
    query: str,
    limit: int = 3,
) -> list[EvidenceWindow]:
    """Return query-relevant recalled evidence windows (read-only).

    Args:
        store: The episodic store to search (not mutated).
        memory_md: The consolidated MEMORY.md snapshot text.
        query: The current query.
        limit: Maximum episodic hits to recall (memory-line hits add up to ``limit``).

    Returns:
        Evidence windows from matching episodes (newest-relevant first) followed by
        matching MEMORY.md lines. Empty when nothing matches.

    Raises:
        ValueError: If ``limit`` is non-positive.
    """
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")

    windows: list[EvidenceWindow] = []
    for episode in store.search(query, limit):
        windows.append(
            EvidenceWindow(
                text=f"[recall turn {episode.turn_id}] {episode.answer}",
                source_index=_EPISODE_INDEX_BASE - episode.turn_id,
            )
        )

    query_terms = set(tokenize(query))
    if query_terms:
        memory_hits = 0
        for line in memory_md.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if query_terms & set(tokenize(stripped)):
                windows.append(EvidenceWindow(text=stripped, source_index=_MEMORY_INDEX_BASE - memory_hits))
                memory_hits += 1
                if memory_hits >= limit:
                    break
    return windows


__all__ = ["recall_evidence"]
