"""Concrete stage signature classes."""

from __future__ import annotations

from .framework import InputField, OutputField, Signature
from .payloads import (
    DeliveryMode,
    EpisodicEntry,
    EvidenceCitation,
    EvidenceWindow,
    InspectorMetadata,
    MemorySnapshot,
    RankedEvidence,
    TaskCategory,
)


class InspectorSignature(Signature):
    """Inspect session history as external state."""

    session_history: str = InputField("Raw session transcript (arbitrarily long).")
    query: str = InputField("Current task or question.")
    evidence_windows: list[EvidenceWindow] = OutputField(
        "Compact evidence snippets filtered from session history.",
        annotation=list[EvidenceWindow],
    )
    metadata: InspectorMetadata = OutputField(
        "Grep patterns used, window indices, confidence scores.",
        annotation=InspectorMetadata,
    )


class RetrieverSignature(Signature):
    """Rank evidence using hybrid lexical + semantic search."""

    evidence_windows: list[EvidenceWindow] = InputField(
        "Windows emitted by the Inspector.",
        annotation=list[EvidenceWindow],
    )
    query: str = InputField("Current task or question.")
    task_category: TaskCategory = InputField("Detected task category.", TaskCategory)
    context_budget_tokens: int = InputField("Max tokens for inline injection.", int)
    ranked_evidence: list[RankedEvidence] = OutputField(
        "Top-k evidence after RRF fusion.",
        annotation=list[RankedEvidence],
    )
    delivery_mode: DeliveryMode = OutputField("inline if within budget, else file_based.", DeliveryMode)


class ReasonerSignature(Signature):
    """Reason over pre-filtered evidence to produce a structured answer."""

    query: str = InputField("Current task or question.")
    ranked_evidence: list[RankedEvidence] = InputField(
        "Ranked evidence from the Retriever.",
        annotation=list[RankedEvidence],
    )
    task_category: TaskCategory = InputField("Detected task category.", TaskCategory)
    memory_context: MemorySnapshot = InputField("Frozen MEMORY.md + USER.md snapshot (read-only).", MemorySnapshot)
    reasoning_trace: str = OutputField(
        "Auditable routing and evidence-use trace; not hidden chain-of-thought."
    )
    answer: str = OutputField("Final answer or action.")
    evidence_citations: list[EvidenceCitation] = OutputField(
        "Raw source windows cited.",
        annotation=list[EvidenceCitation],
    )
    requires_consolidation: bool = OutputField(
        "True only if a novel task class or explicit memory update is needed.", bool
    )


class MemoryGateSignature(Signature):
    """Episodic-first memory management."""

    query: str = InputField("Current task or question.")
    answer: str = InputField("The produced answer.")
    evidence_citations: list[EvidenceCitation] = InputField(
        "Citations from the Reasoner.",
        annotation=list[EvidenceCitation],
    )
    requires_consolidation: bool = InputField("Reasoner's consolidation flag.", bool)
    session_episode_count: int = InputField("Episodes recorded this session.", int)
    episodic_entry: EpisodicEntry = OutputField("Raw turn record to append.", EpisodicEntry)
    consolidation_action: str = OutputField("none | append_memory | update_memory.")
    memory_delta: str = OutputField("Delta to MEMORY.md if consolidating, else ''.")


__all__ = [
    "InspectorSignature",
    "RetrieverSignature",
    "ReasonerSignature",
    "MemoryGateSignature",
]
