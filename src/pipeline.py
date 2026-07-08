"""Composable Pipeline: chain THALIA stages explicitly, step by step.

:class:`AutoHarness` delegates to :class:`Pipeline.with_all_stages`. This module
exposes the same stages as an inspectable, composable chain so callers can insert
custom stages, inspect intermediates, or build variants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .config import HarnessConfig, default_config
from .memory.episodic_store import EpisodicStore
from .module import LMClient
from .recall import recall_evidence
from .routing import classify_task
from .signatures import (
    DeliveryMode,
    EpisodicEntry,
    EvidenceCitation,
    EvidenceWindow,
    HarnessOutput,
    InspectorMetadata,
    MemorySnapshot,
    RankedEvidence,
    TaskCategory,
)
from .stages.inspector import Inspector, adaptive_max_windows
from .stages.memory_gate import MemoryGate
from .stages.reasoner import Reasoner
from .stages.retriever import Retriever


@dataclass
class PipelineStep:
    """One named stage in a :class:`Pipeline`."""

    name: str
    fn: Callable[["PipelineContext"], "PipelineContext"]


@dataclass
class PipelineContext:
    """Mutable state bag passed through the :class:`Pipeline` chain."""

    query: str = ""
    session_history: str = ""
    task_category: TaskCategory = TaskCategory.SINGLE_SESSION
    turn_id: int | None = None
    session_ending: bool = False
    evidence_windows: list[EvidenceWindow] = field(default_factory=list)
    metadata: InspectorMetadata | None = None
    ranked_evidence: list[RankedEvidence] = field(default_factory=list)
    delivery_mode: DeliveryMode | None = None
    answer: str = ""
    reasoning_trace: str = ""
    evidence_citations: list[EvidenceCitation] = field(default_factory=list)
    requires_consolidation: bool = False
    explicit_request: bool = False
    consolidation_action: str = "none"
    memory_delta: str = ""
    episodic_entry: EpisodicEntry | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """Composable chain of THALIA stages."""

    def __init__(
        self,
        config: HarnessConfig | None = None,
        lm: LMClient | None = None,
        episodic_store: EpisodicStore | None = None,
        memory_snapshot: MemorySnapshot | None = None,
        memory_gate: MemoryGate | None = None,
    ) -> None:
        self.config = config or default_config()
        self.memory_snapshot = memory_snapshot or MemorySnapshot()
        self._lm = lm
        self._episodic_store = episodic_store
        self._memory_gate_ref = memory_gate
        self._steps: list[PipelineStep] = []
        self._inspector: Inspector | None = None
        self._retriever: Retriever | None = None
        self._reasoner: Reasoner | None = None
        self._memory_gate: MemoryGate | None = None
        self._intermediates: list[tuple[str, PipelineContext]] = []

    @property
    def steps(self) -> list[PipelineStep]:
        return list(self._steps)

    def __repr__(self) -> str:
        names = [s.name for s in self._steps]
        return f"Pipeline(steps={names}, total={len(names)})"

    @property
    def intermediates(self) -> list[tuple[str, PipelineContext]]:
        return list(self._intermediates)

    def add_step(self, name: str, fn: Callable[[PipelineContext], PipelineContext]) -> "Pipeline":
        self._steps.append(PipelineStep(name=name, fn=fn))
        return self

    def with_inspector(self) -> "Pipeline":
        self._inspector = Inspector(
            max_windows=self.config.max_windows,
            partition_threshold=self.config.partition_threshold,
            partition_size=self.config.partition_size,
        )
        self._steps.append(PipelineStep(name="inspector", fn=self._run_inspector))
        return self

    def with_retriever(self) -> "Pipeline":
        self._retriever = Retriever(
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
        self._steps.append(PipelineStep(name="retriever", fn=self._run_retriever))
        return self

    def with_reasoner(self) -> "Pipeline":
        self._reasoner = Reasoner(
            lm=self._lm,
            max_evidence=self.config.max_evidence,
            verify=self.config.verify,
            grounding_threshold=self.config.grounding_threshold,
        )
        self._steps.append(PipelineStep(name="reasoner", fn=self._run_reasoner))
        return self

    def with_memory_gate(self) -> "Pipeline":
        if self._memory_gate_ref is not None:
            self._memory_gate = self._memory_gate_ref
        else:
            self._memory_gate = MemoryGate(
                episodic_store=self._episodic_store,
                memory_md=self.memory_snapshot.memory_md,
            )
        self._steps.append(PipelineStep(name="memory_gate", fn=self._run_memory_gate))
        return self

    def with_all_stages(self) -> "Pipeline":
        return self.with_inspector().with_retriever().with_reasoner().with_memory_gate()

    def _run_inspector(self, ctx: PipelineContext) -> PipelineContext:
        assert self._inspector is not None, "Inspector not configured"
        if self.config.adaptive_windows:
            n_lines = sum(1 for line in ctx.session_history.split("\n") if line.strip())
            self._inspector.max_windows = adaptive_max_windows(
                n_lines, self.config.max_windows, self.config.adaptive_window_ratio
            )
        else:
            self._inspector.max_windows = self.config.max_windows
        self._inspector.adaptive_windows = self.config.adaptive_windows
        inspected = self._inspector(session_history=ctx.session_history, query=ctx.query)
        ctx.evidence_windows = list(inspected["evidence_windows"])
        ctx.metadata = inspected["metadata"]
        if self.config.recall_memory and self._memory_gate is not None:
            ctx.evidence_windows.extend(
                recall_evidence(
                    self._memory_gate.store,
                    self._memory_gate.memory_md,
                    ctx.query,
                    self.config.recall_limit,
                )
            )
        return ctx

    def _run_retriever(self, ctx: PipelineContext) -> PipelineContext:
        assert self._retriever is not None, "Retriever not configured"
        retrieved = self._retriever(
            evidence_windows=ctx.evidence_windows,
            query=ctx.query,
            task_category=ctx.task_category,
            context_budget_tokens=self.config.context_budget_tokens,
        )
        ctx.ranked_evidence = list(retrieved["ranked_evidence"])
        ctx.delivery_mode = retrieved["delivery_mode"]
        return ctx

    def _run_reasoner(self, ctx: PipelineContext) -> PipelineContext:
        assert self._reasoner is not None, "Reasoner not configured"
        reasoned = self._reasoner(
            query=ctx.query,
            ranked_evidence=ctx.ranked_evidence,
            task_category=ctx.task_category,
            memory_context=self.memory_snapshot,
        )
        ctx.answer = reasoned["answer"]
        ctx.reasoning_trace = reasoned["reasoning_trace"]
        ctx.evidence_citations = list(reasoned["evidence_citations"])
        ctx.requires_consolidation = reasoned["requires_consolidation"]
        ctx.explicit_request = reasoned.get("explicit_request", False)
        return ctx

    def _run_memory_gate(self, ctx: PipelineContext) -> PipelineContext:
        assert self._memory_gate is not None, "Memory Gate not configured"
        turn_id = ctx.turn_id
        if turn_id is None:
            turn_id = self._memory_gate.store.max_turn_id() + 1
        gated = self._memory_gate(
            query=ctx.query,
            answer=ctx.answer,
            evidence_citations=ctx.evidence_citations,
            requires_consolidation=ctx.requires_consolidation,
            task_category=ctx.task_category,
            turn_id=turn_id,
            session_ending=ctx.session_ending,
            explicit_request=ctx.explicit_request,
        )
        ctx.episodic_entry = gated["episodic_entry"]
        ctx.consolidation_action = gated["consolidation_action"]
        ctx.memory_delta = gated["memory_delta"]
        return ctx

    def run(
        self,
        query: str,
        session_history: str = "",
        *,
        session_ending: bool = False,
        turn_id: int | None = None,
    ) -> HarnessOutput:
        """Execute the pipeline and return a :class:`HarnessOutput`."""
        ctx = PipelineContext(
            query=query,
            session_history=session_history,
            task_category=classify_task(query),
            session_ending=session_ending,
            turn_id=turn_id,
        )
        self._intermediates = []
        for step in self._steps:
            ctx = step.fn(ctx)
            self._intermediates.append((step.name, ctx))

        return HarnessOutput(
            answer=ctx.answer,
            reasoning_trace=ctx.reasoning_trace,
            evidence_citations=tuple(ctx.evidence_citations),
            ranked_evidence=tuple(ctx.ranked_evidence),
            task_category=ctx.task_category,
            memory_written=ctx.episodic_entry,
            consolidation_applied=ctx.consolidation_action != "none",
            delivery_mode=ctx.delivery_mode,
            inspector_metadata=ctx.metadata,
        )


__all__ = ["Pipeline", "PipelineStep", "PipelineContext"]
