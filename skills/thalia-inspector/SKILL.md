# SKILL.md — thalia-inspector

## Purpose
RLM-style context inspector (Stage 0). Loads session history as external state,
applies recursive partitioning plus grep/regex anchored on query terms, and emits
compact evidence windows plus auditable metadata. Never loads the full context
into a neural call.

## Inputs
- `session_history: str` — raw session transcript (arbitrarily long)
- `query: str` — current task or question

## Outputs
- `evidence_windows: list[EvidenceWindow]` — compact, query-anchored snippets
- `metadata: InspectorMetadata` — grep patterns, selected indices, confidence,
  session length, line count, effective window budget, partition diagnostics, and
  the adaptive-window flag

## Invocation
```python
from src.stages.inspector import Inspector
result = Inspector(max_windows=15)(session_history=history, query=query)
windows, meta = result["evidence_windows"], result["metadata"]
```

Adaptive windowing is configured at the harness/CLI layer
(`HarnessConfig.adaptive_windows`, `--adaptive-windows`); it scales the effective
Inspector budget with long contexts while preserving the default on compact ones.

## Constraints
- Never load the full context into the neural call.
- Emit at most `max_windows` windows per call.
- Grep patterns must be grounded in query terms (stop-words removed).
- Deterministic: identical inputs produce identical windows.

## Signature
`src.signatures.InspectorSignature`
