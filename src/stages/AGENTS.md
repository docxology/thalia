# `src/stages/` — Agent contract

Barrel package: `from src.stages import Inspector, Retriever, Reasoner, MemoryGate`

## Role

The four sequential pipeline stages. Each is a `Module` subclass with a
declarative `Signature` contract. Stages are composed by `AutoHarness` in
`src/harness.py`; they must not be imported from `infrastructure.*`.

## Module map

| Module | Stage | Responsibility |
|--------|-------|----------------|
| [`inspector.py`](inspector.py) | Stage 0 | RLM-style context narrowing: loads session history into a `REPLEnvironment`, greps and ranks lines, emits `EvidenceWindow` objects |
| [`retriever.py`](retriever.py) | Stage 1 | Hybrid lexical + semantic retrieval with RRF fusion; budgets evidence for inline/file-based delivery |
| [`reasoner.py`](reasoner.py) | Stage 2 | Typed declarative reasoning over ranked evidence; the **only** stage allowed to call the LM |
| [`memory_gate.py`](memory_gate.py) | Stage 3 | Episodic append + gated MEMORY.md consolidation |
| [`__init__.py`](__init__.py) | — | Barrel re-export; also re-exports `classify_task` from `src.routing` |

## Module protocol

Every stage inherits `src.module.Module`:

```python
class Module:
    signature: type[Signature]          # declared on the class, not the instance
    def forward(self, **kwargs) -> Prediction: ...
    def __call__(self, **kwargs) -> Prediction: ...  # delegates to forward
```

`Prediction` is an attribute bag (`values: dict[str, Any]`); access fields
via attribute or subscript. Stages validate inputs with
`self.signature.validate_inputs(**kwargs)` before processing.

## Stage contracts

| Stage | Constructor key params | `forward` inputs | `forward` outputs (Prediction keys) |
|-------|------------------------|-----------------|--------------------------------------|
| `Inspector(max_windows=15)` | `partition_threshold`, `partition_size` | `session_history`, `query` | `evidence_windows: list[EvidenceWindow]`, `metadata: InspectorMetadata` |
| `Retriever(top_k=8, k=60)` | `lexical_weight`, `semantic_weight`, `rerank`, `mmr_lambda`, `query_expansion`, `recency_weight` | `evidence_windows`, `query`, `task_category`, `context_budget_tokens` | `ranked_evidence: list[RankedEvidence]`, `delivery_mode: DeliveryMode` |
| `Reasoner(lm?, max_evidence=5)` | `verify`, `grounding_threshold` | `query`, `ranked_evidence`, `task_category`, `memory_context` | `reasoning_trace`, `answer`, `evidence_citations: list[EvidenceCitation]`, `requires_consolidation: bool` |
| `MemoryGate(episodic_store?, memory_md='')` | — | `query`, `answer`, `evidence_citations`, `requires_consolidation`, `task_category`, `turn_id?`, `session_ending`, `explicit_request?` | `episodic_entry: EpisodicEntry`, `consolidation_action: str`, `memory_delta: str`; ownership-aware `close()`/context manager |

## Key invariants

- **LM isolation**: Only `Reasoner` calls `lm.complete`. Inspector, Retriever,
  and MemoryGate are deterministic and network-free.
- **Append-only episodic log**: `MemoryGate` always persists the raw episode
  first; consolidation is conditional (see `src/memory/AGENTS.md`).
- **Consolidation dual-key gate**: `MemoryGate` consolidates only when
  `requires_consolidation` (Reasoner output) **and** a criterion holds.
- **Task routing**: `Reasoner` selects the `react_style` strategy for
  `REACT_CATEGORIES` tasks (multi-session, code, knowledge-update), and
  `single_pass` otherwise. The ReAct-style path performs deterministic
  read→integrate selection followed by one model completion; it is not a hidden
  chain-of-thought trace. Routing is deterministic via `classify_task` from
  `src.routing`.
- **Turn-id collision safety**: `MemoryGate` derives next turn id from
  `store.max_turn_id() + 1` (not `count()`), safe when explicit and
  auto-assigned ids are mixed.

## Extension points

- Swap the LM: pass any `LMClient` (implements `complete(prompt) -> str`) to
  `Reasoner(lm=…)`.
- `Retriever(rerank='mmr')` activates MMR diversity re-ranking in place of
  pure RRF order.
- `Retriever(query_expansion=True)` enables pseudo-relevance-feedback expansion
  before both retrieval lanes.

## `__all__` exports

`Inspector`, `REPLEnvironment`, `Retriever`, `estimate_tokens`, `Reasoner`,
`classify_task`, `MemoryGate`
