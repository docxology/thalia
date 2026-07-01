# SKILL.md — thalia-retriever

## Purpose
Lexical-first hybrid retriever (Stage 1). Ranks Inspector windows with a BM25/grep
lane and a semantic lane, optionally expands queries, fuses lanes via weighted
Reciprocal Rank Fusion, can apply MMR re-ranking, and budgets delivery (inline
vs. file-based).

## Inputs
- `evidence_windows: list[EvidenceWindow]` — windows from the Inspector
- `query: str` — current task or question
- `task_category: TaskCategory` — selects lane weights
- `context_budget_tokens: int` — inline delivery budget

## Outputs
- `ranked_evidence: list[RankedEvidence]` — top-k after RRF fusion, with lane ranks
- `delivery_mode: DeliveryMode` — inline if within budget, else file_based

## Invocation
```python
from src.stages.retriever import Retriever
from src.signatures import TaskCategory
result = Retriever(top_k=8)(
    evidence_windows=windows, query=query,
    task_category=TaskCategory.SINGLE_SESSION, context_budget_tokens=2048,
)
```

## Constraints
- Lexical lane is primary; semantic lane is a swappable fallback (default: a
  deterministic hashing-embedding surrogate — replace with a learned embedder via
  the same `SemanticIndex` interface).
- RRF defaults: k=60, lexical weight 0.65, semantic weight 0.35.
- Query expansion, recency weighting, and MMR are explicit `HarnessConfig` knobs;
  defaults preserve the lexical-first RRF path.
- Deterministic ordering; ties break on ascending source index.

## Signature
`src.signatures.RetrieverSignature`
