"""Evaluation metrics and dataset primitives for harness compilation.

The compiler optimizes a single scalar ``harness_metric`` per example, a convex
combination of three components:

* **accuracy** — token-F1 of the answer against the gold answer (weight 0.6);
* **grounding** — did the answer cite the expected source(s), and is it supported
  by the cited excerpts (weight 0.3);
* **efficiency** — a sparse-context-budgeting reward: fewer evidence windows for
  the same answer scores higher (weight 0.1).

All components are deterministic functions of a :class:`HarnessOutput` and an
:class:`EvalExample`, so identical inputs always yield identical scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..module import tokenize
from ..signatures import HarnessOutput, TaskCategory

ACCURACY_WEIGHT = 0.6
GROUNDING_WEIGHT = 0.3
EFFICIENCY_WEIGHT = 0.1
_EFFICIENCY_SCALE = 16  # evidence windows beyond which efficiency reward is 0


@dataclass(frozen=True)
class EvalExample:
    """One evaluation instance for the harness.

    Attributes:
        session_history: The transcript the harness inspects.
        query: The question to answer.
        expected_answer: Gold answer string.
        expected_source_indices: Source indices that should be cited (optional).
        task_category: Expected task category (optional; for diagnostics).
    """

    session_history: str
    query: str
    expected_answer: str
    expected_source_indices: tuple[int, ...] = ()
    task_category: TaskCategory | None = None


def token_f1(prediction: str, gold: str) -> float:
    """Token-level F1 between two strings (0..1).

    Returns 1.0 when both are empty, 0.0 when exactly one is empty.
    """
    pred_tokens = tokenize(prediction)
    gold_tokens = tokenize(gold)
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    pred_set = set(pred_tokens)
    gold_set = set(gold_tokens)
    overlap = len(pred_set & gold_set)
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_set)
    recall = overlap / len(gold_set)
    return 2 * precision * recall / (precision + recall)


def answer_score(output: HarnessOutput, example: EvalExample) -> float:
    """Accuracy component: token-F1 of the answer against the gold answer."""
    return token_f1(output.answer, example.expected_answer)


def grounding_score(output: HarnessOutput, example: EvalExample) -> float:
    """Grounding component in [0, 1].

    If expected source indices are provided, half the score rewards citing at
    least one of them; the other half rewards the answer being lexically
    supported by the cited excerpts. Without expected indices, the full score is
    the citation-support term.
    """
    cited_indices = {c.source_index for c in output.evidence_citations}
    cited_text = " ".join(c.excerpt for c in output.evidence_citations)
    support = token_f1(output.answer, cited_text) if cited_text else 0.0

    if example.expected_source_indices:
        hit = 1.0 if cited_indices & set(example.expected_source_indices) else 0.0
        return 0.5 * hit + 0.5 * support
    return support


def efficiency_score(output: HarnessOutput) -> float:
    """Efficiency component: reward using fewer evidence windows (1..0)."""
    n = len(output.ranked_evidence)
    return max(0.0, 1.0 - n / _EFFICIENCY_SCALE)


def harness_metric(output: HarnessOutput, example: EvalExample) -> float:
    """Composite metric in [0, 1] combining accuracy, grounding, efficiency."""
    return (
        ACCURACY_WEIGHT * answer_score(output, example)
        + GROUNDING_WEIGHT * grounding_score(output, example)
        + EFFICIENCY_WEIGHT * efficiency_score(output)
    )


@dataclass(frozen=True)
class EvalReport:
    """Aggregate evaluation results across a dataset.

    Attributes:
        composite: Mean composite metric.
        accuracy: Mean accuracy component.
        grounding: Mean grounding component.
        efficiency: Mean efficiency component.
        n: Number of examples evaluated.
        per_example: Composite score per example, in dataset order.
    """

    composite: float
    accuracy: float
    grounding: float
    efficiency: float
    n: int
    per_example: tuple[float, ...] = field(default_factory=tuple)


def evaluate(
    run_fn: Callable[[EvalExample], HarnessOutput],
    dataset: list[EvalExample],
) -> EvalReport:
    """Run ``run_fn`` over ``dataset`` and aggregate metric components.

    Args:
        run_fn: Maps an example to a HarnessOutput (e.g. ``AutoHarness.run``).
        dataset: Evaluation examples.

    Returns:
        An :class:`EvalReport`.

    Raises:
        ValueError: If ``dataset`` is empty.
    """
    if not dataset:
        raise ValueError("dataset must be non-empty")
    composites: list[float] = []
    acc = grd = eff = 0.0
    for example in dataset:
        output = run_fn(example)
        a = answer_score(output, example)
        g = grounding_score(output, example)
        e = efficiency_score(output)
        composites.append(ACCURACY_WEIGHT * a + GROUNDING_WEIGHT * g + EFFICIENCY_WEIGHT * e)
        acc += a
        grd += g
        eff += e
    n = len(dataset)
    return EvalReport(
        composite=sum(composites) / n,
        accuracy=acc / n,
        grounding=grd / n,
        efficiency=eff / n,
        n=n,
        per_example=tuple(composites),
    )


__all__ = [
    "EvalExample",
    "EvalReport",
    "token_f1",
    "answer_score",
    "grounding_score",
    "efficiency_score",
    "harness_metric",
    "evaluate",
    "ACCURACY_WEIGHT",
    "GROUNDING_WEIGHT",
    "EFFICIENCY_WEIGHT",
]
