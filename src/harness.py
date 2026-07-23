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

from .config import HarnessConfig, default_config
from .memory.episodic_store import EpisodicStore
from .module import LMClient
from .pipeline import Pipeline
from .signatures import HarnessOutput, MemorySnapshot
from .stages.inspector import Inspector
from .stages.memory_gate import MemoryGate
from .stages.reasoner import Reasoner
from .stages.retriever import Retriever


class AutoHarness:
    """The composed THALIA pipeline for a single conversational thread."""

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
        self.config = config or default_config()
        self.memory_snapshot = memory_snapshot or MemorySnapshot()
        self._lm = lm
        self.inspector = Inspector(
            max_windows=self.config.max_windows,
            partition_threshold=self.config.partition_threshold,
            partition_size=self.config.partition_size,
        )
        self.retriever = Retriever(
            top_k=self.config.top_k,
            k=self.config.rrf_k,
            lexical_weight=self.config.lexical_weight,
            semantic_weight=self.config.semantic_weight,
            rerank=self.config.rerank,
            mmr_lambda=self.config.mmr_lambda,
            query_expansion=self.config.query_expansion,
            expansion_terms=self.config.expansion_terms,
            recency_weight=self.config.recency_weight,
        )
        self.reasoner = Reasoner(
            lm=lm,
            max_evidence=self.config.max_evidence,
            verify=self.config.verify,
            grounding_threshold=self.config.grounding_threshold,
        )
        self.memory_gate = MemoryGate(
            episodic_store=episodic_store,
            memory_md=self.memory_snapshot.memory_md,
        )
        self._owns_store = episodic_store is None
        self._turn = start_turn

    def forward(
        self,
        query: str,
        session_history: str,
        session_ending: bool = False,
    ) -> HarnessOutput:
        """Run one full harness turn."""
        pipeline = (
            Pipeline(
                config=self.config,
                lm=self._lm,
                episodic_store=self.memory_gate.store,
                memory_snapshot=self.memory_snapshot,
                memory_gate=self.memory_gate,
            )
            .with_all_stages()
        )
        result = pipeline.run(
            query=query,
            session_history=session_history,
            session_ending=session_ending,
            turn_id=self._turn,
        )
        if pipeline._inspector is not None:
            self.inspector.max_windows = pipeline._inspector.max_windows
            self.inspector.adaptive_windows = pipeline._inspector.adaptive_windows
        self._turn += 1
        return result

    def run(self, example) -> HarnessOutput:
        """Convenience adapter: run an :class:`EvalExample`-shaped object."""
        return self.forward(query=example.query, session_history=example.session_history)

    def close(self) -> None:
        """Close the default-owned episodic store, leaving caller stores open."""
        if self._owns_store:
            self.memory_gate.store.close()

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
