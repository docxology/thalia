"""Composable Pipeline: chain THALIA stages explicitly, step by step.

:class:`AutoHarness` bundles the four runtime stages into one ``forward`` call.
:class:`Pipeline` exposes the same stages as an inspectable, composable chain so
callers can:

* insert custom stages between Inspector and Retriever (e.g. a reranker, a
  logging hook);
* inspect the intermediate output of each stage (the Pipeline records every
  intermediate result);
* swap a single stage without touching the wiring of the others;
* build variants (lexical-only, semantic-only, no-memory) by omitting stages.

The Pipeline is still fully deterministic: it reuses the same stage classes and
config defaults as :class:`AutoHarness`, so identical inputs yield identical
outputs (asserted by the invariant suite).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .config import HarnessConfig, default_config
from .memory.episodic_store import EpisodicStore
from .module import LMClient
from .recall import recall_evidence
from .routing import classify_task
from .signatures import HarnessOutput, MemorySnapshot, TaskCategory
from .stages.inspector import Inspector
from .stages.memory_gate import MemoryGate
from .stages.reasoner import Reasoner
from .stages.retriever import Retriever


@dataclass
class PipelineStep:
    """One named stage in a :class:`Pipeline`.

    Attributes:
        name: Human-readable step name.
        fn: Callable that maps a ``PipelineContext`` to an updated context.
    """

    name: str
    fn: Callable[["PipelineContext"], "PipelineContext"]


@dataclass
class PipelineContext:
    """Mutable state bag passed through the :class:`Pipeline` chain.

    Each stage reads from and writes to this context. The initial context carries
    the query + session history; each stage enriches it with its output.

    Attributes:
        query: The current question.
        session_history: The transcript to inspect.
        task_category: Detected task category.
        evidence_windows: Windows emitted by the Inspector.
        metadata: Inspector metadata.
        ranked_evidence: Ranked evidence from the Retriever.
        delivery_mode: Inline or file-based delivery.
        answer: The produced answer.
        reasoning_trace: The reasoning trace.
        evidence_citations: Citations from the Reasoner.
        requires_consolidation: The Reasoner's consolidation flag.
        explicit_request: Whether the query has an explicit memory cue.
        consolidation_action: The Memory Gate's action.
        memory_delta: The derived memory delta.
        episodic_entry: The persisted episodic entry.
        extras: Free-form bag for custom stages to store intermediate data.
    """

    query: str = ""
    session_history: str = ""
    task_category: TaskCategory = TaskCategory.SINGLE_SESSION
    evidence_windows: list = field(default_factory=list)
    metadata: Any = None
    ranked_evidence: list = field(default_factory=list)
    delivery_mode: Any = None
    answer: str = ""
    reasoning_trace: str = ""
    evidence_citations: list = field(default_factory=list)
    requires_consolidation: bool = False
    explicit_request: bool = False
    consolidation_action: str = "none"
    memory_delta: str = ""
    episodic_entry: Any = None
    extras: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """Composable chain of THALIA stages.

    Build a pipeline by creating an instance and calling the ``with_*`` methods
    (or adding custom steps via :meth:`add_step`). The pipeline executes in
    insertion order when :meth:`run` is called.

    Example::

        pipe = (
            Pipeline(config)
            .with_inspector()
            .with_retriever()
            .with_reasoner()
            .with_memory_gate()
        )
        result = pipe.run(query="What is the wifi password?", session_history="...")
        print(result.answer)

    A custom step can be inserted anywhere::

        pipe = (
            Pipeline(config)
            .with_inspector()
            .add_step("log_windows", lambda ctx: (ctx.extras.update({"n": len(ctx.evidence_windows)}), ctx)[1])
            .with_retriever()
            .with_reasoner()
            .with_memory_gate()
        )

    Args:
        config: Tunable parameters (defaults to :func:`default_config`).
        lm: Language model for the Reasoner (defaults to the deterministic LM).
        episodic_store: Optional shared episodic store.
        memory_snapshot: Frozen MEMORY/USER snapshot injected at start.
    """

    def __init__(
        self,
        config: HarnessConfig | None = None,
        lm: LMClient | None = None,
        episodic_store: EpisodicStore | None = None,
        memory_snapshot: MemorySnapshot | None = None,
    ) -> None:
        self.config = config or default_config()
        self.memory_snapshot = memory_snapshot or MemorySnapshot()
        self._lm = lm
        self._episodic_store = episodic_store
        self._steps: list[PipelineStep] = []
        self._inspector: Inspector | None = None
        self._retriever: Retriever | None = None
        self._reasoner: Reasoner | None = None
        self._memory_gate: MemoryGate | None = None
        self._intermediates: list[tuple[str, PipelineContext]] = []

    @property
    def steps(self) -> list[PipelineStep]:
        """Return the ordered list of registered steps."""
        return list(self._steps)

    def __repr__(self) -> str:
        """Return a human-readable description of the registered stage chain."""
        names = [s.name for s in self._steps]
        return f"Pipeline(steps={names}, total={len(names)})"

    @property
    def intermediates(self) -> list[tuple[str, PipelineContext]]:
        """Return the (step_name, context) snapshot after each step's execution."""
        return list(self._intermediates)

    def add_step(self, name: str, fn: Callable[[PipelineContext], PipelineContext]) -> "Pipeline":
        """Append a custom step to the chain; returns ``self`` for chaining."""
        self._steps.append(PipelineStep(name=name, fn=fn))
        return self

    def with_inspector(self) -> "Pipeline":
        """Add the Inspector (Stage 0) to the chain."""
        self._inspector = Inspector(
            max_windows=self.config.max_windows,
            partition_threshold=self.config.partition_threshold,
            partition_size=self.config.partition_size,
        )
        self._steps.append(PipelineStep(name="inspector", fn=self._run_inspector))
        return self

    def with_retriever(self) -> "Pipeline":
        """Add the Retriever (Stage 1) to the chain."""
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
        """Add the Reasoner (Stage 2) to the chain."""
        self._reasoner = Reasoner(
            lm=self._lm,
            max_evidence=self.config.max_evidence,
            verify=self.config.verify,
            grounding_threshold=self.config.grounding_threshold,
        )
        self._steps.append(PipelineStep(name="reasoner", fn=self._run_reasoner))
        return self

    def with_memory_gate(self) -> "Pipeline":
        """Add the Memory Gate (Stage 3) to the chain."""
        self._memory_gate = MemoryGate(
            episodic_store=self._episodic_store,
            memory_md=self.memory_snapshot.memory_md,
        )
        self._steps.append(PipelineStep(name="memory_gate", fn=self._run_memory_gate))
        return self

    def with_all_stages(self) -> "Pipeline":
        """Convenience: add Inspector + Retriever + Reasoner + Memory Gate."""
        return self.with_inspector().with_retriever().with_reasoner().with_memory_gate()

    def _run_inspector(self, ctx: PipelineContext) -> PipelineContext:
        """Execute the Inspector and update the context."""
        assert self._inspector is not None, "Inspector not configured"
        if self.config.adaptive_windows:
            n_lines = sum(1 for line in ctx.session_history.split("\n") if line.strip())
            from .stages.inspector import adaptive_max_windows
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
        """Execute the Retriever and update the context."""
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
        """Execute the Reasoner and update the context."""
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
        """Execute the Memory Gate and update the context."""
        assert self._memory_gate is not None, "Memory Gate not configured"
        gated = self._memory_gate(
            query=ctx.query,
            answer=ctx.answer,
            evidence_citations=ctx.evidence_citations,
            requires_consolidation=ctx.requires_consolidation,
            task_category=ctx.task_category,
            session_ending=False,
            explicit_request=ctx.explicit_request,
        )
        ctx.episodic_entry = gated["episodic_entry"]
        ctx.consolidation_action = gated["consolidation_action"]
        ctx.memory_delta = gated["memory_delta"]
        return ctx

    def run(self, query: str, session_history: str = "") -> HarnessOutput:
        """Execute the pipeline and return a :class:`HarnessOutput`.

        Args:
            query: The question to answer.
            session_history: The transcript to inspect (may be empty).

        Returns:
            A fully populated :class:`HarnessOutput`.
        """
        ctx = PipelineContext(
            query=query,
            session_history=session_history,
            task_category=classify_task(query),
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
