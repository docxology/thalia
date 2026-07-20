"""GEPA-style trace-reflective configuration evolution.

GEPA (Genetic-Pareto prompt evolution) reads *execution traces* to understand
**why** a system underperforms, then proposes targeted improvements. The THALIA
analogue reflects on the aggregate metric components (accuracy / grounding /
efficiency) from :class:`~src.compiler.metrics.EvalReport`, identifies the weakest
component, and applies a targeted, bounded mutation to the :class:`HarnessConfig`.

It also enforces the artifact constraints used by ``hermes-agent-self-evolution``:
every evolved skill file must stay within a size budget and remain non-empty, and
provides an optional bridge to a real ``dspy.Signature`` when DSPy is installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import dspy as _dspy

from ..config import HarnessConfig, default_config
from ..signatures import HarnessOutput, Signature
from .metrics import EvalExample, EvalReport, evaluate
from .mipro import CompileResult

# Skill-file size budget mirrored from hermes-agent-self-evolution (skills <= 15KB).
SKILL_MAX_BYTES = 15 * 1024


@dataclass(frozen=True)
class SkillConstraintReport:
    """Result of validating an evolved skill artifact.

    Attributes:
        ok: True if every constraint passed.
        size_bytes: UTF-8 byte length of the artifact.
        within_size: Whether the artifact is within the size budget.
        non_empty: Whether the artifact has non-whitespace content.
        reasons: Human-readable failure reasons (empty when ``ok``).
    """

    ok: bool
    size_bytes: int
    within_size: bool
    non_empty: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def check_skill_constraints(text: str, max_bytes: int = SKILL_MAX_BYTES) -> SkillConstraintReport:
    """Validate an evolved skill artifact against size and non-empty constraints.

    Args:
        text: The candidate skill content.
        max_bytes: Maximum permitted UTF-8 byte length (default 15 KiB).

    Returns:
        A :class:`SkillConstraintReport`.
    """
    size = len(text.encode("utf-8"))
    within = size <= max_bytes
    non_empty = bool(text.strip())
    reasons: list[str] = []
    if not within:
        reasons.append(f"size {size}B exceeds budget {max_bytes}B")
    if not non_empty:
        reasons.append("artifact is empty")
    return SkillConstraintReport(
        ok=within and non_empty,
        size_bytes=size,
        within_size=within,
        non_empty=non_empty,
        reasons=tuple(reasons),
    )


class GEPAOptimizer:
    """Trace-reflective evolutionary search over :class:`HarnessConfig`.

    Args:
        max_top_k: Upper bound for the retriever depth mutation.
        max_evidence_cap: Upper bound for the reasoner evidence mutation.
        max_windows_cap: Upper bound for the inspector window mutation.
    """

    def __init__(
        self,
        max_top_k: int = 12,
        max_evidence_cap: int = 8,
        max_windows_cap: int = 25,
    ) -> None:
        self.max_top_k = max_top_k
        self.max_evidence_cap = max_evidence_cap
        self.max_windows_cap = max_windows_cap

    def reflect(self, config: HarnessConfig, report: EvalReport) -> HarnessConfig:
        """Propose a targeted mutation from the weakest metric component.

        * grounding weakest -> deepen retrieval (more windows to cite);
        * accuracy weakest -> emphasise lexical matching + widen the inspector;
        * efficiency weakest -> tighten retrieval depth.

        Returns the original config unchanged if the mutation would be invalid or
        a no-op at the bounds.
        """
        weakest = min(
            ("accuracy", report.accuracy),
            ("grounding", report.grounding),
            ("efficiency", report.efficiency),
            key=lambda pair: pair[1],
        )[0]
        try:
            if weakest == "grounding":
                return config.with_(
                    top_k=min(self.max_top_k, config.top_k + 1),
                    max_evidence=min(self.max_evidence_cap, config.max_evidence + 1),
                )
            if weakest == "accuracy":
                return config.with_(
                    max_windows=min(self.max_windows_cap, config.max_windows + 2),
                    lexical_weight=0.8,
                    semantic_weight=0.2,
                )
            # efficiency
            return config.with_(
                top_k=max(2, config.top_k - 1),
                max_evidence=max(1, config.max_evidence - 1),
            )
        except ValueError:
            return config

    def evolve(
        self,
        build_fn: Callable[[HarnessConfig], Callable[[EvalExample], HarnessOutput]],
        dataset: list[EvalExample],
        seed_config: HarnessConfig | None = None,
        iterations: int = 8,
    ) -> CompileResult:
        """Evolve a configuration via reflective mutation for ``iterations`` rounds.

        Args:
            build_fn: Maps a config to a runnable ``example -> HarnessOutput``.
            dataset: Evaluation examples.
            seed_config: Starting config (defaults to :func:`default_config`).
            iterations: Number of reflective mutation rounds.

        Returns:
            A :class:`CompileResult` whose trace records every candidate tried.

        Raises:
            ValueError: If ``dataset`` is empty or ``iterations`` is negative.
        """
        if not dataset:
            raise ValueError("dataset must be non-empty")
        if iterations < 0:
            raise ValueError(f"iterations must be non-negative, got {iterations}")

        current = seed_config or default_config()
        current_report = evaluate(build_fn(current), dataset)
        best_config = current
        best_score = current_report.composite
        trace: list[tuple[HarnessConfig, float]] = [(current, best_score)]

        for _ in range(iterations):
            candidate = self.reflect(current, current_report)
            candidate_report = evaluate(build_fn(candidate), dataset)
            trace.append((candidate, candidate_report.composite))
            if candidate_report.composite > best_score:
                best_score = candidate_report.composite
                best_config = candidate
            # Walk to the candidate (reflection always perturbs the incumbent),
            # while ``best_config`` retains the global maximum seen so far.
            current, current_report = candidate, candidate_report

        return CompileResult(
            best_config=best_config,
            best_score=best_score,
            trace=tuple(trace),
            n_candidates=len(trace),
        )


# ---------------------------------------------------------------------------
# DSPy signature bridge (real dspy.Signature from any THALIA signature)
# ---------------------------------------------------------------------------

DSPY_AVAILABLE = True


def to_dspy_signature(signature: type[Signature]) -> Any:
    """Build a real ``dspy.Signature`` from a THALIA signature.

    Args:
        signature: A THALIA :class:`~src.signatures.Signature` subclass.

    Returns:
        A dynamically constructed ``dspy.Signature`` class.
    """
    fields: dict[str, Any] = {}
    annotations: dict[str, Any] = {}
    for name, fld in signature.inputs().items():
        fields[name] = _dspy.InputField(desc=fld.desc)
        annotations[name] = fld.annotation
    for name, fld in signature.outputs().items():
        fields[name] = _dspy.OutputField(desc=fld.desc)
        annotations[name] = fld.annotation
    fields["__doc__"] = signature.instructions()
    fields["__annotations__"] = annotations
    return type(signature.__name__, (_dspy.Signature,), fields)


__all__ = [
    "SKILL_MAX_BYTES",
    "SkillConstraintReport",
    "check_skill_constraints",
    "GEPAOptimizer",
    "to_dspy_signature",
]
