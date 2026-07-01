# SKILL.md — thalia-pipeline

## Purpose
Composable stage chain for the THALIA harness. `Pipeline` exposes the four
runtime stages (Inspector → Retriever → Reasoner → Memory Gate) as an
explicit, inspectable chain so callers can insert custom steps, swap a single
stage, inspect intermediate outputs after each step, or build variants
(lexical-only, no-memory, etc.) without touching `AutoHarness`.

The pipeline is fully deterministic: it reuses the same stage classes and
config defaults as `AutoHarness`, so identical inputs yield identical outputs.

## Inputs
- `config: HarnessConfig | None` — tunable parameters (defaults to `default_config()`)
- `lm: LMClient | None` — language model for the Reasoner (defaults to the deterministic LM)
- `episodic_store: EpisodicStore | None` — shared episodic store (optional)
- `memory_snapshot: MemorySnapshot | None` — frozen MEMORY/USER snapshot injected at start
- `query: str`, `session_history: str` — passed to `run()`

## Outputs
- `HarnessOutput` — answer, citations, ranked evidence, task category, memory record
- `pipeline.intermediates` — `list[tuple[str, PipelineContext]]` snapshot after each step

## Invocation
```python
from src.pipeline import Pipeline

# Full four-stage pipeline
pipe = (
    Pipeline(config)
    .with_inspector()
    .with_retriever()
    .with_reasoner()
    .with_memory_gate()
)
result = pipe.run(query="What is the wifi password?", session_history="...")
print(result.answer)

# Convenience shorthand — identical to the four .with_* calls above
pipe = Pipeline(config).with_all_stages()
result = pipe.run(query="What is the wifi password?", session_history="...")

# Inserting a custom logging step between Inspector and Retriever
pipe = (
    Pipeline(config)
    .with_inspector()
    .add_step("log_windows",
              lambda ctx: (ctx.extras.update({"n": len(ctx.evidence_windows)}), ctx)[1])
    .with_retriever()
    .with_reasoner()
    .with_memory_gate()
)

# Inspecting intermediate outputs after run()
for step_name, ctx in pipe.intermediates:
    print(step_name, ctx.answer or ctx.ranked_evidence)
```

## Key Types
- `PipelineContext` — mutable state bag threaded through every step; carries
  `query`, `session_history`, `task_category`, `evidence_windows`, `metadata`,
  `ranked_evidence`, `delivery_mode`, `answer`, `reasoning_trace`,
  `evidence_citations`, `requires_consolidation`, `consolidation_action`,
  `memory_delta`, `episodic_entry`, and a free-form `extras` dict for custom stages.
- `PipelineStep(name, fn)` — one registered step; `fn` maps `PipelineContext → PipelineContext`.

## Constraints
- Steps execute in insertion order; `add_step` / `with_*` methods return `self` for chaining.
- Each `with_*` call instantiates its stage once; calling `with_inspector()` twice appends two inspector steps.
- `with_all_stages()` is equivalent to `.with_inspector().with_retriever().with_reasoner().with_memory_gate()`.
- `pipeline.intermediates` is reset on every `run()` call.
- Deterministic: same inputs, same config → same outputs (asserted by the invariant suite).

## Module
`src.pipeline`
