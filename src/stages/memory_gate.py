"""Stage 3 — Memory Gate: episodic-first storage with gated consolidation.

The gate enforces the consolidation-fault safeguard (Zhang et al., 2026):

1. **Always** append the raw episode to the append-only :class:`EpisodicStore`.
2. **Only** consolidate into MEMORY.md when the Reasoner requested it AND an
   explicit criterion holds (session end, novel task class, or explicit request).
3. **Never** overwrite a raw episode — the MEMORY.md delta is a derived artifact.
"""

from __future__ import annotations

from ..memory.consolidation import (
    ConsolidationAction,
    ConsolidationCriteria,
    consolidate_snapshot,
    decide_action,
    derive_memory_delta,
    has_explicit_memory_cue,
)
from ..memory.episodic_store import EpisodicStore
from ..module import Module, Prediction
from ..signatures import EpisodicEntry, EvidenceCitation, MemoryGateSignature, TaskCategory


class MemoryGate(Module):
    """Stage 3 — append raw episodes and conditionally consolidate memory."""

    signature = MemoryGateSignature

    def __init__(
        self,
        episodic_store: EpisodicStore | None = None,
        memory_md: str = "",
    ) -> None:
        self.store = episodic_store if episodic_store is not None else EpisodicStore()
        self._owns_store = episodic_store is None
        self.memory_md = memory_md
        # Novelty is session-scoped but must survive a process restart when the
        # caller reopens an existing append-only store. Otherwise the first turn
        # after reopen is misclassified as novel and can trigger redundant
        # consolidation.
        self._seen_categories: set[str] = {entry.task_category for entry in self.store.all()}

    def close(self) -> None:
        """Close the store created by this gate, never a caller-owned store."""
        if self._owns_store:
            self.store.close()

    def __enter__(self) -> "MemoryGate":
        """Return the gate for context-managed use."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Close an owned store when leaving a context."""
        self.close()

    def __del__(self) -> None:  # pragma: no cover - interpreter safety net
        """Best-effort cleanup for direct stage users."""
        try:
            self.close()
        except Exception:
            pass

    def forward(  # type: ignore[override]
        self,
        query: str,
        answer: str,
        evidence_citations: list[EvidenceCitation],
        requires_consolidation: bool,
        task_category: TaskCategory = TaskCategory.SINGLE_SESSION,
        turn_id: int | None = None,
        session_ending: bool = False,
        explicit_request: bool | None = None,
    ) -> Prediction:
        """Persist the turn and apply the consolidation gate.

        Args:
            query: The user query.
            answer: The produced answer.
            evidence_citations: Citations from the Reasoner.
            requires_consolidation: The Reasoner's consolidation flag.
            task_category: Detected task category (drives novelty detection).
            turn_id: Explicit turn id; defaults to ``store.max_turn_id() + 1`` (the
                smallest id guaranteed not to collide with an existing episode).
            session_ending: Whether the session is closing.
            explicit_request: Override for the explicit-request criterion; when
                None it is auto-detected from the query text.

        Returns:
            A :class:`Prediction` with ``episodic_entry``, ``consolidation_action``
            (str) and ``memory_delta`` (str).
        """
        category_value = task_category.value if isinstance(task_category, TaskCategory) else str(task_category)
        # Auto-assign a collision-proof turn id: MAX(turn_id) + 1 rather than
        # count(). count() can collide with an explicitly-assigned id when explicit
        # and auto ids are mixed (e.g. an explicit turn_id=0 in an empty store makes
        # count() return a value that a later auto-assign would reuse), which
        # EpisodicStore.append rejects with a ValueError.
        resolved_turn_id = turn_id if turn_id is not None else self.store.max_turn_id() + 1

        self.signature.validate_inputs(
            query=query,
            answer=answer,
            evidence_citations=evidence_citations,
            requires_consolidation=requires_consolidation,
            session_episode_count=self.store.count(),
        )

        entry = EpisodicEntry(
            turn_id=resolved_turn_id,
            query=query,
            answer=answer,
            evidence_indices=tuple(c.source_index for c in evidence_citations),
            task_category=category_value,
        )
        # (1) ALWAYS persist the raw episode — this branch is never skipped.
        self.store.append(entry)

        # (2) Determine explicit criteria (novelty measured before recording it).
        novel = category_value not in self._seen_categories
        self._seen_categories.add(category_value)
        explicit = (
            explicit_request if explicit_request is not None else has_explicit_memory_cue(query)
        )
        criteria = ConsolidationCriteria(
            session_ending=session_ending,
            novel_task_class=novel,
            explicit_request=explicit,
        )

        action = decide_action(
            requires_consolidation=requires_consolidation,
            criteria=criteria,
            memory_exists=bool(self.memory_md.strip()),
        )

        # (3) CONDITIONALLY consolidate — derived delta, raw episode untouched.
        delta = ""
        if action is not ConsolidationAction.NONE:
            delta = derive_memory_delta(entry)
            self.memory_md = consolidate_snapshot(self.memory_md, [delta])

        return Prediction(
            {
                "episodic_entry": entry,
                "consolidation_action": action.value,
                "memory_delta": delta,
            }
        )


__all__ = ["MemoryGate"]
