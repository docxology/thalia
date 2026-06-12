# SKILL.md — atlas-compiler

## Purpose
Bounded trace-evolution layer (Stage 4). Operates on the harness offline: a
MIPRO-style metric-driven search over `HarnessConfig`, and a GEPA-style
trace-reflective evolution that mutates the weakest metric component. Enforces
the Hermes skill-artifact constraints and optionally bridges to real DSPy.

## Inputs
- `build_fn: Callable[[HarnessConfig], Callable[[EvalExample], HarnessOutput]]`
- `dataset: list[EvalExample]`
- (GEPA) `seed_config: HarnessConfig`, `iterations: int`

## Outputs
- `CompileResult` — best_config, best_score, trace, n_candidates

## Invocation
```python
from src.compiler.mipro import MIPROCompiler
from src.compiler.gepa import GEPAOptimizer, check_skill_constraints
from src.harness import build_run_fn
from src.evaluation import build_demo_dataset

ds = build_demo_dataset()
mipro = MIPROCompiler(auto="heavy").compile(lambda c: build_run_fn(c), ds)
gepa = GEPAOptimizer().evolve(lambda c: build_run_fn(c), ds, iterations=8)
assert check_skill_constraints(open("SKILL.md").read()).ok
```

## Constraints
- Evaluation builds a fresh harness per example (order-independent, reproducible).
- Evolved skill artifacts must be ≤ 15 KB and non-empty (`check_skill_constraints`).
- `to_dspy_signature` is gated on the optional `dspy` import; the core never needs it.
- The in-house compilers are "-style" analogues. Real DSPy use is only the gated
  `src.dspy_runtime.py` path.

## Modules
`src.compiler.metrics`, `src.compiler.mipro`, `src.compiler.gepa`
