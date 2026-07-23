"""Domain payloads and task taxonomy flowing between THALIA stages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskCategory(str, Enum):
    """Detected task class used for harness-conditioned prompting."""

    TEMPORAL = "temporal"
    PREFERENCE = "preference"
    MULTI_SESSION = "multi_session"
    SINGLE_SESSION = "single_session"
    KNOWLEDGE_UPDATE = "knowledge_update"
    CODE = "code"

    @classmethod
    def from_str(cls, value: str) -> "TaskCategory":
        """Coerce a string to a TaskCategory, defaulting to SINGLE_SESSION."""
        try:
            return cls(value)
        except ValueError:
            return cls.SINGLE_SESSION


REACT_CATEGORIES: frozenset[TaskCategory] = frozenset(
    {
        TaskCategory.MULTI_SESSION,
        TaskCategory.CODE,
        TaskCategory.KNOWLEDGE_UPDATE,
    }
)


@dataclass(frozen=True)
class EvidenceWindow:
    """A compact slice of session history, emitted by the Inspector."""

    text: str
    source_index: int
    relevance: float = 0.0
    start: int = 0
    end: int = 0


@dataclass(frozen=True)
class InspectorMetadata:
    """Provenance for an Inspector run."""

    grep_patterns: tuple[str, ...]
    window_indices: tuple[int, ...]
    confidence: float
    session_length: int
    line_count: int = 0
    effective_max_windows: int = 0
    partition_threshold: int = 0
    partition_size: int = 0
    partition_blocks_considered: int = 0
    adaptive_windows: bool = False


@dataclass(frozen=True)
class RankedEvidence:
    """An evidence window after hybrid retrieval ranking."""

    window: EvidenceWindow
    score: float
    lexical_rank: int = -1
    semantic_rank: int = -1


@dataclass(frozen=True)
class EvidenceCitation:
    """A raw source window cited by the Reasoner."""

    source_index: int
    excerpt: str


@dataclass(frozen=True)
class MemorySnapshot:
    """Frozen, read-only memory injected at session start."""

    memory_md: str = ""
    user_md: str = ""


@dataclass(frozen=True)
class EpisodicEntry:
    """A raw turn record appended to the episodic store."""

    turn_id: int
    query: str
    answer: str
    evidence_indices: tuple[int, ...] = ()
    task_category: str = TaskCategory.SINGLE_SESSION.value


class DeliveryMode(str, Enum):
    """How retrieved evidence is delivered to the Reasoner."""

    INLINE = "inline"
    FILE_BASED = "file_based"


@dataclass(frozen=True)
class HarnessOutput:
    """The full result of one AutoHarness turn.

    Attributes:
        answer: The produced answer string.
        reasoning_trace: Human-readable trace of the reasoning strategy.
        evidence_citations: Source windows cited by the Reasoner.
        ranked_evidence: Evidence ranked by the Retriever.
        task_category: Detected task category for the query.
        memory_written: The episodic entry persisted by the Memory Gate, or ``None``
            when a partial pipeline omitted that stage.
        consolidation_applied: Whether memory consolidation fired this turn.
        delivery_mode: How evidence was delivered, or ``None`` when a partial
            pipeline omitted the Retriever stage.
        inspector_metadata: Provenance from the Inspector stage.
    """

    answer: str
    reasoning_trace: str
    evidence_citations: tuple[EvidenceCitation, ...]
    ranked_evidence: tuple[RankedEvidence, ...]
    task_category: TaskCategory
    memory_written: EpisodicEntry | None
    consolidation_applied: bool = False
    delivery_mode: DeliveryMode | None = DeliveryMode.INLINE
    inspector_metadata: InspectorMetadata | None = None

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation.

        Mirrors :func:`src.cli.output_to_dict` but lives on the dataclass so any
        consumer (not just the CLI) can serialise a HarnessOutput without
        duplicating the field mapping. Tuples are converted to lists for JSON.
        """
        inspector = self.inspector_metadata
        return {
            "answer": self.answer,
            "task_category": self.task_category.value,
            "delivery_mode": self.delivery_mode.value if self.delivery_mode is not None else None,
            "reasoning_trace": self.reasoning_trace,
            "consolidation_applied": self.consolidation_applied,
            "citations": [
                {"source_index": c.source_index, "excerpt": c.excerpt}
                for c in self.evidence_citations
            ],
            "ranked_evidence": [
                {"source_index": r.window.source_index, "score": r.score}
                for r in self.ranked_evidence
            ],
            "inspector_metadata": None
            if inspector is None
            else {
                "grep_patterns": list(inspector.grep_patterns),
                "window_indices": list(inspector.window_indices),
                "confidence": inspector.confidence,
                "session_length": inspector.session_length,
                "line_count": inspector.line_count,
                "effective_max_windows": inspector.effective_max_windows,
                "partition_threshold": inspector.partition_threshold,
                "partition_size": inspector.partition_size,
                "partition_blocks_considered": inspector.partition_blocks_considered,
                "adaptive_windows": inspector.adaptive_windows,
            },
        }

    def to_json(self, **json_kwargs: Any) -> str:
        """Return a JSON string representation of this output.

        Args:
            **json_kwargs: Passed through to ``json.dumps`` (e.g. ``indent=2``).

        Returns:
            A JSON string.
        """
        return json.dumps(self.to_dict(), **json_kwargs)


__all__ = [
    "TaskCategory",
    "REACT_CATEGORIES",
    "EvidenceWindow",
    "InspectorMetadata",
    "RankedEvidence",
    "EvidenceCitation",
    "MemorySnapshot",
    "EpisodicEntry",
    "DeliveryMode",
    "HarnessOutput",
]
