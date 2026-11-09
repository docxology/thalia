"""AutoHarness — the composed five-stage THALIA pipeline.

Wires the four runtime stages together via :class:`Pipeline`:

    session history + query
        -> Inspector (Stage 0, RLM-style context narrowing)
        -> Retriever (Stage 1, lexical-first hybrid + RRF)
        -> Reasoner  (Stage 2, typed declarative reasoning)
        -> MemoryGate(Stage 3, episodic-first gated consolidation)
        -> HarnessOutput

The fifth stage — the Compiler (:mod:`src.compiler`) — operates *on* this object
offline, searching the :class:`HarnessConfig` space against the harness metric.
"""

from __future__ import annotations

from typing import Callable

from .config import HarnessConfig
from .memory.episodic_store import EpisodicStore
from .module import LMClient
from .pipeline import Pipeline
from .signatures import HarnessOutput, MemorySnapshot
from .stages.inspector import Inspector
from .stages.memory_gate import MemoryGate
from .stages.reasoner import Reasoner
from .stages.retriever import Retriever


class AutoHarness:
    """One persistent runtime stage graph for a conversational thread.

    Exposed stages are the executing instances, so changing a Reasoner or
    Retriever attribute affects subsequent turns. Replacing ``config`` applies
    changed fields to those instances without replacing the effective LM or
    episodic state. Inspector policy remains config-driven each turn.
    """

    def __init__(
        self,
        config: HarnessConfig | None = None,
        lm: LMClient | None = None,
        episodic_store: EpisodicStore | None = None,
        memory_snapshot: MemorySnapshot | None = None,
        start_turn: int = 0,
    ) -> None:
        if start_turn < 0:
            raise ValueError(f"start_turn must be non-negative, got {start_turn}")
        self._pipeline = Pipeline(
            config=config,
            lm=lm,
            episodic_store=episodic_store,
            memory_snapshot=memory_snapshot,
        ).with_all_stages()
        self._turn = start_turn

    @property
    def config(self) -> HarnessConfig:
        return self._pipeline.config

    @config.setter
    def config(self, value: HarnessConfig) -> None:
        """Apply changed configuration fields while retaining stage identity."""
        value.validate()
        previous = self._pipeline.config
        for name in (
            "top_k", "lexical_weight", "semantic_weight", "rerank", "mmr_lambda",
            "query_expansion", "expansion_terms", "recency_weight",
        ):
            if getattr(value, name) != getattr(previous, name):
                setattr(self.retriever, name, getattr(value, name))
        if value.rrf_k != previous.rrf_k:
            self.retriever.k = value.rrf_k
        for name in ("max_evidence", "verify", "grounding_threshold"):
            if getattr(value, name) != getattr(previous, name):
                setattr(self.reasoner, name, getattr(value, name))
        self._pipeline.config = value

    @property
    def memory_snapshot(self) -> MemorySnapshot:
        return self._pipeline.memory_snapshot

    @memory_snapshot.setter
    def memory_snapshot(self, value: MemorySnapshot) -> None:
        self._pipeline.memory_snapshot = value

    @property
    def inspector(self) -> Inspector:
        assert self._pipeline._inspector is not None
        return self._pipeline._inspector

    @inspector.setter
    def inspector(self, value: Inspector) -> None:
        self._pipeline._inspector = value

    @property
    def retriever(self) -> Retriever:
        assert self._pipeline._retriever is not None
        return self._pipeline._retriever

    @retriever.setter
    def retriever(self, value: Retriever) -> None:
        self._pipeline._retriever = value

    @property
    def reasoner(self) -> Reasoner:
        assert self._pipeline._reasoner is not None
        return self._pipeline._reasoner

    @reasoner.setter
    def reasoner(self, value: Reasoner) -> None:
        self._pipeline._reasoner = value

    @property
    def memory_gate(self) -> MemoryGate:
        assert self._pipeline._memory_gate is not None
        return self._pipeline._memory_gate

    def forward(
        self,
        query: str,
        session_history: str,
        session_ending: bool = False,
    ) -> HarnessOutput:
        """Run one full harness turn."""
        result = self._pipeline.run(
            query=query,
            session_history=session_history,
            session_ending=session_ending,
            turn_id=self._turn,
        )
        self._turn += 1
        return result

    def run(self, example) -> HarnessOutput:
        """Convenience adapter: run an :class:`EvalExample`-shaped object."""
        return self.forward(query=example.query, session_history=example.session_history)

    def close(self) -> None:
        """Close the default-owned episodic store, leaving caller stores open."""
        self._pipeline.close()

    def __enter__(self) -> "AutoHarness":
        """Return the harness for context-managed resource ownership."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Close an owned store when leaving a context."""
        self.close()

    def __del__(self) -> None:  # pragma: no cover - interpreter safety net
        """Best-effort cleanup for callers that do not use the context manager."""
        try:
            self.close()
        except Exception:
            pass


def build_run_fn(
    config: HarnessConfig,
    lm: LMClient | None = None,
) -> Callable[[object], HarnessOutput]:
    """Return an ``example -> HarnessOutput`` runner with a fresh harness per call."""
    def run(example) -> HarnessOutput:
        with AutoHarness(config=config, lm=lm) as harness:
            return harness.run(example)

    return run


__all__ = ["AutoHarness", "build_run_fn"]
