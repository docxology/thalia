"""THALIA — Agentic Typed-pipeline with Lexical And Structured stages.

A typed, declaratively-specified agentic harness that fuses DSPy's
compiler-driven optimization with the Hermes Agent layered-memory and
trace-evolution ecosystem. Prompts are parameterized code (typed signatures),
context is inspectable external state (RLM-style Inspector), memory is
episodic-first evidence (gated consolidation), and retrieval is a lexical-anchored
hybrid (BM25/grep + hashing-embedding + weighted RRF). The pipeline records
bounded optimization traces through structured search (MIPRO-style) and
trace-reflective evolution (GEPA-style) rather than ad-hoc prompt tweaking.

The full design rationale lives in ``docs/manuscript/``; this package is the runnable,
deterministic, fully-tested implementation.
"""

__version__ = "0.1.0"

from .cli import run_query
from .config import (
    HarnessConfig,
    apply_env_overrides,
    default_config,
    load_config,
    save_config,
)
from .dashboard import render_dashboard_html, write_dashboard
from .harness import AutoHarness, build_run_fn
from .invariants import InvariantResult, all_invariants
from .llm import CallableLM, OllamaError, OllamaLM
from .module import ExtractiveLM, LMClient, Module, Predict, Prediction, render_signature_prompt, tokenize
from .pipeline import Pipeline, PipelineContext, PipelineStep
from .recall import recall_evidence
from .retrieval import expand_query, mmr_rerank
from .session import Session
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
from .routing import classify_task
from .stages import Inspector, MemoryGate, Reasoner, Retriever

__all__ = [
    "__version__",
    # Top-level harness
    "AutoHarness",
    "build_run_fn",
    "Pipeline",
    "PipelineStep",
    "PipelineContext",
    "Session",
    "run_query",
    "HarnessConfig",
    "default_config",
    "load_config",
    "save_config",
    "apply_env_overrides",
    # LM adapters
    "CallableLM",
    "OllamaLM",
    "OllamaError",
    # Validation + visualization
    "all_invariants",
    "InvariantResult",
    "render_dashboard_html",
    "write_dashboard",
    "mmr_rerank",
    "expand_query",
    "recall_evidence",
    # Stages
    "Inspector",
    "Retriever",
    "Reasoner",
    "MemoryGate",
    "classify_task",
    # Module/LM layer
    "Module",
    "Predict",
    "Prediction",
    "LMClient",
    "ExtractiveLM",
    "tokenize",
    "render_signature_prompt",
    # Payloads
    "TaskCategory",
    "EvidenceWindow",
    "InspectorMetadata",
    "RankedEvidence",
    "EvidenceCitation",
    "MemorySnapshot",
    "EpisodicEntry",
    "DeliveryMode",
    "HarnessOutput",
]
