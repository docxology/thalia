# SKILL.md — thalia-reasoner

## Purpose
Typed declarative reasoner (Stage 2). Classifies the task, routes multi-hop / code
/ knowledge-update tasks through a ReAct read→integrate loop and others through
chain-of-thought, and returns a typed answer with raw-window citations. The
language model is swappable; the default is a deterministic extractive responder.

## Inputs
- `query: str` — current task or question
- `ranked_evidence: list[RankedEvidence]` — from the Retriever
- `task_category: TaskCategory` — selects strategy
- `memory_context: MemorySnapshot` — frozen, read-only MEMORY/USER snapshot

## Outputs
- `reasoning_trace: str` — chain of thought grounded in evidence
- `answer: str` — final answer or action
- `evidence_citations: list[EvidenceCitation]` — raw windows cited (enables audit)
- `requires_consolidation: bool` — true only on knowledge-update / explicit cues

## Invocation
```python
from src.stages.reasoner import Reasoner
result = Reasoner()(query=query, ranked_evidence=ranked,
                    task_category=category, memory_context=snapshot)
```

## Constraints
- Deterministic code selects/routes evidence; the LM handles only judgment.
- Citations are raw windows overlapping the answer (≥1 when evidence exists).
- The injected memory snapshot is read-only and never mutated mid-turn.

## Signature
`src.signatures.ReasonerSignature`
