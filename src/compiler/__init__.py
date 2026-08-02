"""Self-improvement layer for the THALIA harness.

Closes the loop between the pipeline and its evaluation:

* :mod:`src.compiler.metrics` — the ``harness_metric`` (answer token-F1 + citation support +
  efficiency) and dataset/eval primitives.
* :mod:`src.compiler.mipro` — MIPRO-style metric-driven config search.
* :mod:`src.compiler.gepa` — GEPA-style trace-reflective config evolution and
  the size/semantic constraints every evolved skill artifact must satisfy.
"""

from typing import TYPE_CHECKING

from .metrics import (
    EvalExample,
    EvalReport,
    answer_score,
    citation_precision,
    citation_support_proxy,
    efficiency_score,
    evaluate,
    grounding_score,
    harness_metric,
    session_reachability_score,
    source_recall,
    token_f1,
)
from .mipro import CompileResult, MIPROCompiler, default_search_space

if TYPE_CHECKING:
    from .gepa import GEPAOptimizer, SkillConstraintReport, check_skill_constraints, to_dspy_signature

__all__ = [
    "EvalExample",
    "EvalReport",
    "harness_metric",
    "evaluate",
    "token_f1",
    "answer_score",
    "citation_support_proxy",
    "citation_precision",
    "source_recall",
    "session_reachability_score",
    "grounding_score",
    "efficiency_score",
    "MIPROCompiler",
    "CompileResult",
    "default_search_space",
    "GEPAOptimizer",
    "SkillConstraintReport",
    "check_skill_constraints",
    "to_dspy_signature",
]

_GEPA_EXPORTS = {
    "GEPAOptimizer",
    "SkillConstraintReport",
    "check_skill_constraints",
    "to_dspy_signature",
}


def __getattr__(name: str):
    """Lazily expose the optional DSPy-backed GEPA bridge.

    Importing deterministic compiler metrics must not import the optional DSPy
    SDK.  The optional GEPA names load only when a caller requests them.
    """
    if name in _GEPA_EXPORTS:
        from . import gepa

        return getattr(gepa, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
