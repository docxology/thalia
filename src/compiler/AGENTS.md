# `src/compiler/` — Agent contract

Barrel package: `from src.compiler import MIPROCompiler, GEPAOptimizer, harness_metric, …`

## Role

Self-improvement layer: closes the loop between pipeline execution and
evaluation. Provides the composite metric, two complementary optimizers
(exhaustive search and reflective evolution), and a DSPy signature bridge.

## Module map

| Module | Contents |
|--------|----------|
| [`metrics.py`](metrics.py) | `harness_metric`, `evaluate`, component scorers, `EvalExample`, `EvalReport` |
| [`mipro.py`](mipro.py) | `MIPROCompiler` — exhaustive config search; `CompileResult`, `default_search_space` |
| [`gepa.py`](gepa.py) | `GEPAOptimizer` — trace-reflective evolution; `check_skill_constraints`, `to_dspy_signature`, `DSPY_AVAILABLE` |
| [`__init__.py`](__init__.py) | Barrel re-export of all three modules |

## `harness_metric`

```
harness_metric(output: HarnessOutput, example: EvalExample) -> float  # in [0, 1]
  = 0.6 * token_F1(answer, gold)           # accuracy
  + 0.3 * grounding_score(output, example) # citation hit + lexical support
  + 0.1 * efficiency_score(output)         # fewer evidence windows = higher reward
```

`grounding_score`: if `expected_source_indices` are provided, 0.5 × citation-hit
+ 0.5 × lexical-support; otherwise full score is citation-support only.

`efficiency_score`: `max(0, 1 − n_evidence / 16)` — reward for sparse retrieval.

`evaluate(run_fn, dataset) -> EvalReport` — runs `run_fn` over every example
and returns mean components. Raises `ValueError` on empty dataset.

## `MIPROCompiler` (config search)

Analogous to DSPy MIPROv2: searches the **structural** `HarnessConfig` space
(retriever depth, reasoner evidence cap, lane weights) rather than free-text
instructions.

```
MIPROCompiler(auto='light'|'medium'|'heavy')
  .compile(build_fn, dataset, candidates?) -> CompileResult
```

- `build_fn: HarnessConfig -> (EvalExample -> HarnessOutput)` — must be
  order-independent (fresh harness per call; see `build_run_fn` in `harness.py`).
- Budget tiers: `light=4`, `medium=9`, `heavy=10 000` candidates evaluated.
- `default_search_space()` — 8 deterministic candidates varying `top_k` ∈
  {4, 8, 12}, `max_evidence` ∈ {3, 5}, and two lane-weight presets.
- Ties resolve to the earliest candidate in evaluation order.

`CompileResult(best_config, best_score, trace, n_candidates)` — frozen
dataclass; `trace` is a tuple of `(HarnessConfig, float)` pairs.

## `GEPAOptimizer` (reflective evolution)

Analogous to GEPA (Genetic-Pareto prompt evolution): reads `EvalReport`
components to identify the weakest dimension, then applies a targeted mutation.

```
GEPAOptimizer(max_top_k=12, max_evidence_cap=8, max_windows_cap=25)
  .reflect(config, report) -> HarnessConfig   # single mutation step
  .evolve(build_fn, dataset, seed_config?, iterations=8) -> CompileResult
```

Mutation rules (applied by `reflect`):

| Weakest component | Mutation |
|-------------------|----------|
| `grounding` | `top_k += 1`, `max_evidence += 1` (deepen retrieval) |
| `accuracy` | `max_windows += 2`, `lexical_weight=0.8` (widen inspector, emphasise lexical) |
| `efficiency` | `top_k -= 1`, `max_evidence -= 1` (tighten retrieval) |

Returns the original config unchanged if the mutation is a no-op at the bounds.
`evolve` always walks to the candidate (not just the best), ensuring reflection
perturbs the incumbent each round.

## `check_skill_constraints`

```
check_skill_constraints(text: str, max_bytes=15360) -> SkillConstraintReport
```

Validates an evolved skill artifact: must be non-empty and within the 15 KiB
size budget (mirrored from `hermes-agent-self-evolution`). Used before writing
any compiler-generated artifact to disk.

## DSPy bridge (optional)

`gepa.py` detects DSPy lazily. Importing deterministic compiler metrics does not
load the SDK; requesting `to_dspy_signature` does. `DSPY_AVAILABLE` is false
when the optional extra is absent, and the bridge raises an actionable install
error in that environment. Install with `uv sync --extra neural` for the real
DSPy bridge/runtime.

`to_dspy_signature(signature: type[Signature]) -> dspy.Signature` — builds a
real `dspy.Signature` class dynamically from any THALIA `Signature` subclass by
mirroring its `InputField` / `OutputField` annotations and instructions.

## Key invariants

- **Determinism**: identical `build_fn`, `dataset`, and `candidates` always
  produce the same `CompileResult`; no randomness in either optimizer.
- **Order-independent evaluation**: `build_fn` must create a fresh harness per
  call (use `build_run_fn(config)` from `harness.py`).
- **Metric is the single truth signal**: compilers never inspect internal stage
  state directly — all feedback flows through `harness_metric`.
- **No LM in metrics or mipro**: `gepa.py` may import DSPy for the bridge, but
  the optimizers themselves never call a language model.

## `__all__` exports (barrel)

`EvalExample`, `EvalReport`, `harness_metric`, `evaluate`, `token_f1`,
`answer_score`, `grounding_score`, `efficiency_score`,
`MIPROCompiler`, `CompileResult`, `default_search_space`,
`GEPAOptimizer`, `SkillConstraintReport`, `check_skill_constraints`,
`to_dspy_signature`
