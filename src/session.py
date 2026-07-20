"""Persistent multi-turn session over the THALIA harness.

A :class:`Session` wraps :class:`AutoHarness` with disk-backed state so a
conversation survives process restarts:

* episodes persist to a SQLite file (the append-only episodic store);
* the consolidated MEMORY.md is read at start and re-written whenever a turn
  consolidates;
* the running transcript is reconstructed from stored episodes, so the Inspector
  can retrieve evidence from earlier turns.

This is the harness's "real" multi-turn surface: each :meth:`ask` inspects the
accumulated transcript, retrieves and reasons, and records the turn.
"""

from __future__ import annotations

from pathlib import Path

from .config import HarnessConfig
from .harness import AutoHarness
from .memory.episodic_store import EpisodicStore
from .module import LMClient
from .signatures import HarnessOutput, MemorySnapshot


class Session:
    """A persistent, multi-turn conversation backed by the THALIA harness.

    Args:
        config: Harness configuration (defaults to the harness default).
        lm: Language model for the Reasoner (defaults to the deterministic LM).
        db_path: SQLite path for the episodic store (``":memory:"`` for ephemeral).
        memory_path: Optional path to a MEMORY.md file (read at start, written on
            consolidation). If None, consolidated memory lives only in process.
    """

    def __init__(
        self,
        config: HarnessConfig | None = None,
        lm: LMClient | None = None,
        db_path: str = ":memory:",
        memory_path: str | Path | None = None,
    ) -> None:
        self.db_path = db_path
        self.memory_path = Path(memory_path) if memory_path else None
        memory_md = self.memory_path.read_text() if self.memory_path and self.memory_path.exists() else ""

        store = EpisodicStore(db_path)
        self.harness = AutoHarness(
            config=config,
            lm=lm,
            episodic_store=store,
            memory_snapshot=MemorySnapshot(memory_md=memory_md),
            start_turn=store.max_turn_id() + 1,
        )

        # Reconstruct the running transcript from any persisted episodes so the
        # Inspector can retrieve evidence from earlier turns after a restart.
        self._transcript: list[str] = []
        for episode in store.all():
            self._transcript.append(f"User: {episode.query}")
            self._transcript.append(f"Assistant: {episode.answer}")

    @property
    def turn_count(self) -> int:
        """Number of turns recorded in this session's episodic store."""
        return self.harness.memory_gate.store.count()

    def ask(
        self,
        query: str,
        extra_context: str = "",
        session_ending: bool = False,
    ) -> HarnessOutput:
        """Run one conversational turn and record it.

        Args:
            query: The user's message.
            extra_context: Optional out-of-band context to prepend to the
                inspectable history (e.g. documents) for this turn.
            session_ending: Whether this is the final turn (permits consolidation).

        Returns:
            The :class:`HarnessOutput` for the turn.
        """
        history_parts = [p for p in (extra_context, "\n".join(self._transcript)) if p]
        history = "\n".join(history_parts)

        out = self.harness.forward(query, history, session_ending=session_ending)

        self._transcript.append(f"User: {query}")
        self._transcript.append(f"Assistant: {out.answer}")
        if out.consolidation_applied:
            self._persist_memory()
        return out

    def _persist_memory(self) -> None:
        """Write the current consolidated MEMORY.md to disk (if a path is set)."""
        if self.memory_path is not None:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            self.memory_path.write_text(self.harness.memory_gate.memory_md)

    def close(self) -> None:
        """Persist memory and close the underlying episodic store."""
        self._persist_memory()
        self.harness.memory_gate.store.close()

    def reset(self) -> None:
        """Reset this session to a pristine state, discarding all episodes.

        Closes the existing store, clears the in-memory transcript, and creates a
        fresh :class:`AutoHarness` with a new :class:`EpisodicStore` at the same
        ``db_path``. The MEMORY.md snapshot is re-read from disk (if a path was
        configured), so any consolidated memory that was persisted survives the
        reset; in-memory-only state is lost.
        """
        self.harness.memory_gate.store.close()
        self._transcript = []
        memory_md = self.memory_path.read_text() if self.memory_path and self.memory_path.exists() else ""
        store = EpisodicStore(self.db_path)
        self.harness = AutoHarness(
            config=self.harness.config,
            lm=self.harness.reasoner.lm,
            episodic_store=store,
            memory_snapshot=MemorySnapshot(memory_md=memory_md),
            start_turn=store.max_turn_id() + 1,
        )
        for episode in store.all():
            self._transcript.append(f"User: {episode.query}")
            self._transcript.append(f"Assistant: {episode.answer}")

    # -- Context manager protocol --------------------------------------------------
    # Enables ``with Session(...) as s:`` so the episodic store is always closed
    # and the consolidated MEMORY.md flushed to disk, even on early return or
    # exception.
    def __enter__(self) -> "Session":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()


__all__ = ["Session"]
