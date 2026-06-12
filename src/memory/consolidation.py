"""Explicitly gated memory consolidation.

Zhang et al. (2026) show that consolidating memory after *every* interaction
degrades utility below the no-memory baseline; agents that preserve raw episodes
and gate consolidation via explicit Retain/Delete/Consolidate actions roughly
double accuracy. This module encodes that gate. Consolidation fires only when the
Reasoner requests it AND an explicit criterion holds (session end, novel task
class, or explicit user request). The derived MEMORY.md delta is a read-only
artifact computed from the raw episode; it never mutates the episode itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..signatures import EpisodicEntry

# Canonical explicit-memory cues (Reasoner + Memory Gate share this list).
EXPLICIT_MEMORY_MARKERS: tuple[str, ...] = (
    "remember",
    "note that",
    "don't forget",
    "do not forget",
    "keep in mind",
    "make a note",
    "/remember",
)


def has_explicit_memory_cue(query: str) -> bool:
    """True when ``query`` contains an explicit remember / note-this cue."""
    lowered = query.lower()
    return any(marker in lowered for marker in EXPLICIT_MEMORY_MARKERS)


class ConsolidationAction(str, Enum):
    """Outcome of the consolidation gate."""

    NONE = "none"
    APPEND_MEMORY = "append_memory"
    UPDATE_MEMORY = "update_memory"


@dataclass(frozen=True)
class ConsolidationCriteria:
    """Explicit triggers permitting consolidation.

    Attributes:
        session_ending: The session is closing.
        novel_task_class: A task class not seen earlier this session appeared.
        explicit_request: The user explicitly asked to remember something.
    """

    session_ending: bool = False
    novel_task_class: bool = False
    explicit_request: bool = False

    def any_met(self) -> bool:
        """True if at least one explicit criterion holds."""
        return self.session_ending or self.novel_task_class or self.explicit_request


def should_consolidate(
    requires_consolidation: bool,
    criteria: ConsolidationCriteria,
) -> bool:
    """Return True only if the Reasoner requested it AND a criterion is met.

    This is the core safety gate: it is impossible to consolidate purely because
    a turn completed. Both conditions are required.
    """
    return bool(requires_consolidation) and criteria.any_met()


def decide_action(
    requires_consolidation: bool,
    criteria: ConsolidationCriteria,
    memory_exists: bool,
) -> ConsolidationAction:
    """Map gate inputs to a concrete consolidation action.

    Args:
        requires_consolidation: The Reasoner's flag.
        criteria: Explicit consolidation triggers.
        memory_exists: Whether a MEMORY.md snapshot already has content.

    Returns:
        ``NONE`` if the gate is closed; ``UPDATE_MEMORY`` for explicit
        user requests against existing memory; otherwise ``APPEND_MEMORY``.
    """
    if not should_consolidate(requires_consolidation, criteria):
        return ConsolidationAction.NONE
    if criteria.explicit_request and memory_exists:
        return ConsolidationAction.UPDATE_MEMORY
    return ConsolidationAction.APPEND_MEMORY


def derive_memory_delta(entry: EpisodicEntry) -> str:
    """Derive a MEMORY.md delta line grounded in a raw episode.

    The delta cites the source turn so the consolidated fact remains traceable to
    veridical evidence — the property whose loss causes the consolidation fault.

    Args:
        entry: The raw episode to summarize.

    Returns:
        A single Markdown bullet referencing the source turn.
    """
    answer = entry.answer.strip().replace("\n", " ")
    return f"- [{entry.task_category}] {entry.query.strip()} -> {answer} (turn {entry.turn_id})"


def consolidate_snapshot(existing_memory_md: str, deltas: list[str]) -> str:
    """Append deltas to an existing MEMORY.md snapshot without rewriting it.

    Consolidation only ever *adds* derived bullets under a stable heading; prior
    content is preserved verbatim, so a bad consolidation cannot silently corrupt
    earlier facts.

    Args:
        existing_memory_md: Current MEMORY.md content (possibly empty).
        deltas: New derived bullets to append.

    Returns:
        The updated MEMORY.md content.
    """
    if not deltas:
        return existing_memory_md
    body = existing_memory_md.rstrip()
    if "## Consolidated Memory" not in body:
        header = "# MEMORY\n\n## Consolidated Memory" if not body else "\n\n## Consolidated Memory"
        body = f"{body}{header}" if body else header
    new_lines = [d for d in deltas if d.strip()]
    return body + "\n" + "\n".join(new_lines) + "\n"


__all__ = [
    "EXPLICIT_MEMORY_MARKERS",
    "has_explicit_memory_cue",
    "ConsolidationAction",
    "ConsolidationCriteria",
    "should_consolidate",
    "decide_action",
    "derive_memory_delta",
    "consolidate_snapshot",
]
