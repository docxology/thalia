"""AutoHarness — the composed five-stage ATLAS pipeline.

Wires the four runtime stages together:

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
from .recall import recall_evidence
from .signatures import HarnessOutput, MemorySnapshot
from .stages.inspector import Inspector, adaptive_max_windows
from .stages.memory_gate import MemoryGate
from .routing import classify_task
from .stages.reasoner import Reasoner
from .stages.retriever import Retriever


class AutoHarness:
    """The composed ATLAS pipeline for a single conversational thread.

    Memory persists across :meth:`run` calls on the same instance (later turns
    can consolidate from earlier ones). For order-independent evaluation, build a
    fresh harness per example via :func:`build_run_fn`.

    Args:
        config: Tunable parameters (defaults to :func:`default_config`).
        lm: Language model for the Reasoner (defaults to the deterministic
            :class:`~src.module.ExtractiveLM`).
        episodic_store: Optional shared episodic store.
        memory_snapshot: Frozen MEMORY/USER snapshot injected at start.
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
        self.config = config or default_config()
        self.memory_snapshot = memory_snapshot or MemorySnapshot()
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
        self._turn = start_turn

    def forward(
        self,
        query: str,
        session_history: str,
        session_ending: bool = False,
    ) -> HarnessOutput:
        """Run one full harness turn.

        Args:
            query: The current question.
            session_history: The transcript to inspect.
            session_ending: Whether this is the final turn (permits consolidation).

        Returns:
            A fully populated :class:`HarnessOutput`.
        """
        task_category = classify_task(query)

        # Adaptive narrowing (opt-in): scale the Inspector's window budget with the
        # session size so long-context haystacks are not over-narrowed. A compact
        # context stays at the base budget, so the default behaviour is unchanged.
        if self.config.adaptive_windows:
            n_lines = sum(1 for line in session_history.split("\n") if line.strip())
            self.inspector.max_windows = adaptive_max_windows(n_lines, self.config.max_windows, self.config.adaptive_window_ratio)
        else:
            self.inspector.max_windows = self.config.max_windows
        self.inspector.adaptive_windows = self.config.adaptive_windows

        inspected = self.inspector(session_history=session_history, query=query)
        windows = list(inspected["evidence_windows"])

        # Memory recall: consult the episodic store + MEMORY.md snapshot for
        # query-relevant evidence beyond the current session history (read-only).
        if self.config.recall_memory:
            windows.extend(
                recall_evidence(
                    self.memory_gate.store,
                    self.memory_gate.memory_md,
                    query,
                    self.config.recall_limit,
                )
            )

        retrieved = self.retriever(
            evidence_windows=windows,
            query=query,
            task_category=task_category,
            context_budget_tokens=self.config.context_budget_tokens,
        )
        reasoned = self.reasoner(
            query=query,
            ranked_evidence=retrieved["ranked_evidence"],
            task_category=task_category,
            memory_context=self.memory_snapshot,
        )
        gated = self.memory_gate(
            query=query,
            answer=reasoned["answer"],
            evidence_citations=reasoned["evidence_citations"],
            requires_consolidation=reasoned["requires_consolidation"],
            task_category=task_category,
            turn_id=self._turn,
            session_ending=session_ending,
            explicit_request=reasoned.get("explicit_request"),
        )
        self._turn += 1

        return HarnessOutput(
            answer=reasoned["answer"],
            reasoning_trace=reasoned["reasoning_trace"],
            evidence_citations=tuple(reasoned["evidence_citations"]),
            ranked_evidence=tuple(retrieved["ranked_evidence"]),
            task_category=task_category,
            memory_written=gated["episodic_entry"],
            consolidation_applied=gated["consolidation_action"] != "none",
            delivery_mode=retrieved["delivery_mode"],
            inspector_metadata=inspected["metadata"],
        )

    def run(self, example) -> HarnessOutput:
        """Convenience adapter: run an :class:`EvalExample`-shaped object.

        Accepts any object exposing ``query`` and ``session_history`` attributes.
        """
        return self.forward(query=example.query, session_history=example.session_history)


def build_run_fn(
    config: HarnessConfig,
    lm: LMClient | None = None,
) -> Callable[[object], HarnessOutput]:
    """Return an ``example -> HarnessOutput`` runner with a fresh harness per call.

    A fresh harness (and fresh in-memory episodic store) per example makes
    evaluation order-independent and reproducible — the contract the compilers
    rely on.

    Args:
        config: The configuration to evaluate.
        lm: Optional language model override.

    Returns:
        A callable suitable for :func:`src.compiler.metrics.evaluate`.
    """

    def run(example) -> HarnessOutput:
        return AutoHarness(config=config, lm=lm).run(example)

    return run


__all__ = ["AutoHarness", "build_run_fn"]
