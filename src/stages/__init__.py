"""The four THALIA pipeline stages.

Each stage is a :class:`src.module.Module` with a declarative
:class:`src.signatures.Signature` contract:

* Stage 0 :class:`~src.stages.inspector.Inspector` — RLM-style context narrowing.
* Stage 1 :class:`~src.stages.retriever.Retriever` — lexical-first hybrid retrieval.
* Stage 2 :class:`~src.stages.reasoner.Reasoner` — typed declarative reasoning.
* Stage 3 :class:`~src.stages.memory_gate.MemoryGate` — episodic-first memory.
"""

from .inspector import Inspector, REPLEnvironment
from .memory_gate import MemoryGate
from ..routing import classify_task
from .reasoner import Reasoner
from .retriever import Retriever, estimate_tokens

__all__ = [
    "Inspector",
    "REPLEnvironment",
    "Retriever",
    "estimate_tokens",
    "Reasoner",
    "classify_task",
    "MemoryGate",
]
