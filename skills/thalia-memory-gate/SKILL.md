# SKILL.md — thalia-memory-gate

## Purpose
Episodic-first memory gate (Stage 3). Always appends the raw episode to an
append-only SQLite (+ FTS5) store; only consolidates a derived MEMORY.md delta
when the Reasoner requests it AND an explicit criterion holds. Never overwrites a
raw episode. Implements the consolidation-fault safeguard.

Recall is read-only and happens before retrieval when `HarnessConfig.recall_memory`
is enabled: the harness searches the episodic store and MEMORY.md, appends recalled
evidence windows to the inspected context, and leaves raw episodes unchanged.

## Inputs
- `query: str`, `answer: str` — the turn
- `evidence_citations: list[EvidenceCitation]` — from the Reasoner
- `requires_consolidation: bool` — the Reasoner's flag
- `task_category: TaskCategory`, `turn_id: int`, `session_ending: bool`, `explicit_request: bool|None`

## Outputs
- `episodic_entry: EpisodicEntry` — the raw turn record appended
- `consolidation_action: str` — none | append_memory | update_memory
- `memory_delta: str` — derived MEMORY.md delta if consolidating, else ''

## Invocation
```python
from src.stages.memory_gate import MemoryGate
gate = MemoryGate()
result = gate(query=q, answer=a, evidence_citations=cites,
              requires_consolidation=flag, session_ending=False)
```

## Constraints
- The raw-episode append is never skipped.
- Consolidation requires BOTH the Reasoner flag AND an explicit criterion
  (session end, novel task class, or explicit user request).
- Consolidation only appends derived bullets; prior MEMORY.md content is preserved.
- Recall must not mutate the store or MEMORY.md.

## Signature
`src.signatures.MemoryGateSignature`
