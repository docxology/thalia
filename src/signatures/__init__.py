"""Typed signature framework and domain payloads for the THALIA harness."""

from .framework import Field, FieldKind, InputField, OutputField, Signature
from .payloads import (
    REACT_CATEGORIES,
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
from .stages import (
    InspectorSignature,
    MemoryGateSignature,
    ReasonerSignature,
    RetrieverSignature,
)

__all__ = [
    "TaskCategory",
    "REACT_CATEGORIES",
    "FieldKind",
    "Field",
    "InputField",
    "OutputField",
    "Signature",
    "EvidenceWindow",
    "InspectorMetadata",
    "RankedEvidence",
    "EvidenceCitation",
    "MemorySnapshot",
    "EpisodicEntry",
    "DeliveryMode",
    "HarnessOutput",
    "InspectorSignature",
    "RetrieverSignature",
    "ReasonerSignature",
    "MemoryGateSignature",
]
