"""Domain payloads and task taxonomy flowing between ATLAS stages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
    """The full result of one AutoHarness turn."""

    answer: str
    reasoning_trace: str
    evidence_citations: tuple[EvidenceCitation, ...]
    ranked_evidence: tuple[RankedEvidence, ...]
    task_category: TaskCategory
    memory_written: EpisodicEntry
    consolidation_applied: bool = False
    delivery_mode: DeliveryMode = DeliveryMode.INLINE
    inspector_metadata: InspectorMetadata | None = None


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
