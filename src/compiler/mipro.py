"""MIPRO-style metric-driven configuration search.

DSPy's MIPROv2 bootstraps candidate few-shot demonstrations, proposes instruction
variants, and searches the combined space against a metric. The ATLAS pipeline's
deterministic core has no free-text instructions to mutate at run time, so the
analogue here searches the **structural** configuration space (:class:`HarnessConfig`)
against :func:`src.compiler.metrics.evaluate`. The search is exhaustive over the
provided candidate set (optionally truncated by an ``auto`` budget) and fully
deterministic — identical inputs reproduce the same winning config and trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..config import HarnessConfig, default_config
from ..signatures import HarnessOutput
from .metrics import EvalExample, evaluate

# Candidate counts per ``auto`` budget tier (truncation of the search space).
_AUTO_BUDGET: dict[str, int] = {"light": 4, "medium": 9, "heavy": 10_000}


@dataclass(frozen=True)
class CompileResult:
    """Outcome of a compilation/evolution run.

    Attributes:
        best_config: The highest-scoring configuration found.
        best_score: Its mean composite metric.
        trace: (config, score) pairs in evaluation order.
        n_candidates: Number of candidates actually evaluated.
    """

    best_config: HarnessConfig
    best_score: float
    trace: tuple[tuple[HarnessConfig, float], ...] = field(default_factory=tuple)
    n_candidates: int = 0


def default_search_space() -> list[HarnessConfig]:
    """Return a deterministic grid of candidate configurations.

    Varies the retriever depth, reasoner evidence cap, and lane weighting — the
    parameters the agentic-search study shows matter most for retrieval quality.
    """
    base = default_config()
    space: list[HarnessConfig] = []
    for top_k in (4, 8, 12):
        for max_evidence in (3, 5):
            space.append(base.with_(top_k=top_k, max_evidence=max_evidence))
    # Two explicit lane-weight variants (lexical-heavy and balanced).
    space.append(base.with_(top_k=8, max_evidence=5, lexical_weight=0.8, semantic_weight=0.2))
    space.append(base.with_(top_k=8, max_evidence=5, lexical_weight=0.5, semantic_weight=0.5))
    return space


class MIPROCompiler:
    """Exhaustive metric-driven search over harness configurations.

    Args:
        auto: Budget tier — ``"light"``, ``"medium"`` or ``"heavy"``.

    Raises:
        ValueError: If ``auto`` is not a known budget tier.
    """

    def __init__(self, auto: str = "light") -> None:
        if auto not in _AUTO_BUDGET:
            raise ValueError(f"auto must be one of {sorted(_AUTO_BUDGET)}, got {auto!r}")
        self.auto = auto

    def compile(
        self,
        build_fn: Callable[[HarnessConfig], Callable[[EvalExample], HarnessOutput]],
        dataset: list[EvalExample],
        candidates: list[HarnessConfig] | None = None,
    ) -> CompileResult:
        """Evaluate each candidate config and return the best.

        Args:
            build_fn: Maps a config to a runnable ``example -> HarnessOutput``.
            dataset: Evaluation examples.
            candidates: Candidate configs (defaults to :func:`default_search_space`).

        Returns:
            A :class:`CompileResult`. Ties resolve to the earliest candidate.

        Raises:
            ValueError: If the candidate set or dataset is empty.
        """
        if candidates is None:
            candidates = default_search_space()
        if not candidates:
            raise ValueError("candidate set must be non-empty")
        if not dataset:
            raise ValueError("dataset must be non-empty")

        budget = _AUTO_BUDGET[self.auto]
        evaluated = candidates[:budget]

        trace: list[tuple[HarnessConfig, float]] = []
        best_config = evaluated[0]
        best_score = float("-inf")
        for config in evaluated:
            score = evaluate(build_fn(config), dataset).composite
            trace.append((config, score))
            if score > best_score:
                best_score = score
                best_config = config
        return CompileResult(
            best_config=best_config,
            best_score=best_score,
            trace=tuple(trace),
            n_candidates=len(evaluated),
        )


__all__ = ["CompileResult", "MIPROCompiler", "default_search_space"]
