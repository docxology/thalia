"""Typed payloads for committed evaluation JSON consumed by figure plotters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import DEFAULT_CONFIDENCE_LEVEL


def _int_keyed_floats(raw: dict[str | int, float]) -> dict[int, float]:
    return {int(k): float(v) for k, v in raw.items()}


@dataclass(frozen=True)
class NeuralEvalRow:
    category: str
    extractive_f1: float
    neural_f1: float


@dataclass(frozen=True)
class NeuralEvalPayload:
    model: str
    n: int
    mean_extractive_f1: float
    mean_neural_f1: float
    rows: tuple[NeuralEvalRow, ...]
    extractive_statistics: StatisticalSummaryPayload | None = None
    neural_statistics: StatisticalSummaryPayload | None = None
    paired_comparison: dict[str, Any] | None = None
    generation_options: dict[str, Any] | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> NeuralEvalPayload:
        rows = tuple(
            NeuralEvalRow(
                category=str(row["category"]),
                extractive_f1=float(row["extractive_f1"]),
                neural_f1=float(row["neural_f1"]),
            )
            for row in data["rows"]
        )
        return cls(
            model=str(data["model"]),
            n=int(data["n"]),
            mean_extractive_f1=float(data["mean_extractive_f1"]),
            mean_neural_f1=float(data["mean_neural_f1"]),
            rows=rows,
            extractive_statistics=(
                StatisticalSummaryPayload.from_json(data["extractive_statistics"])
                if data.get("extractive_statistics")
                else None
            ),
            neural_statistics=(
                StatisticalSummaryPayload.from_json(data["neural_statistics"])
                if data.get("neural_statistics")
                else None
            ),
            paired_comparison=dict(data["paired_neural_minus_extractive"])
            if data.get("paired_neural_minus_extractive")
            else None,
            generation_options=dict(data["generation_options"])
            if data.get("generation_options")
            else None,
        )


@dataclass(frozen=True)
class BottleneckNeuralRow:
    accuracy: float | None
    grounding: float | None


@dataclass(frozen=True)
class BottleneckRankingModes:
    available: bool
    n: int
    k: int
    lexical: float
    dense: float
    hybrid: float


@dataclass(frozen=True)
class BottleneckAdaptive:
    accuracy: float
    grounding: float | None = None


@dataclass(frozen=True)
class BottleneckPayload:
    n_ranking: int
    ranking_recall_at_10: float
    inspector_recall: float
    neural_model: str
    extractive_grounding_by_maxwindows: dict[int, float]
    neural_by_maxwindows: dict[int, BottleneckNeuralRow]
    ranking_recall_by_mode: BottleneckRankingModes | None
    neural_adaptive: BottleneckAdaptive | None
    n_neural: int | None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BottleneckPayload:
        neural: dict[int, BottleneckNeuralRow] = {}
        for key, row in data["neural_by_maxwindows"].items():
            neural[int(key)] = BottleneckNeuralRow(
                accuracy=row.get("accuracy"),
                grounding=row.get("grounding"),
            )
        mode_raw = data.get("ranking_recall_by_mode") or {}
        mode = None
        if mode_raw.get("available"):
            mode = BottleneckRankingModes(
                available=True,
                n=int(mode_raw["n"]),
                k=int(mode_raw.get("k", 10)),
                lexical=float(mode_raw["lexical"]),
                dense=float(mode_raw["dense"]),
                hybrid=float(mode_raw["hybrid"]),
            )
        adaptive_raw = data.get("neural_adaptive")
        adaptive = (
            BottleneckAdaptive(accuracy=float(adaptive_raw["accuracy"]), grounding=adaptive_raw.get("grounding"))
            if adaptive_raw
            else None
        )
        return cls(
            n_ranking=int(data["n_ranking"]),
            ranking_recall_at_10=float(data["ranking_recall_at_10"]),
            inspector_recall=float(data["inspector_recall"]),
            neural_model=str(data["neural_model"]),
            extractive_grounding_by_maxwindows=_int_keyed_floats(data["extractive_grounding_by_maxwindows"]),
            neural_by_maxwindows=neural,
            ranking_recall_by_mode=mode,
            neural_adaptive=adaptive,
            n_neural=data.get("n_neural"),
        )


@dataclass(frozen=True)
class LongMemEvalPayload:
    n_extractive: int
    n_neural: int
    neural_model: str
    extractive_accuracy: tuple[float, float, float]
    neural_accuracy: tuple[float, float, float]
    extractive_grounding: tuple[float, float, float]
    neural_grounding: tuple[float, float, float]
    confidence: float = 0.95

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LongMemEvalPayload:
        def _triple(key: str) -> tuple[float, float, float]:
            values = data[key]
            return (float(values[0]), float(values[1]), float(values[2]))

        return cls(
            n_extractive=int(data["n_extractive"]),
            n_neural=int(data["n_neural"]),
            neural_model=str(data["neural_model"]),
            extractive_accuracy=_triple("extractive_accuracy"),
            neural_accuracy=_triple("neural_accuracy"),
            extractive_grounding=_triple("extractive_grounding"),
            neural_grounding=_triple("neural_grounding"),
            confidence=float(
                (data.get("neural_accuracy_statistics") or {}).get(
                    "confidence", (data.get("extractive_accuracy_statistics") or {}).get("confidence", DEFAULT_CONFIDENCE_LEVEL)
                )
            ),
        )


@dataclass(frozen=True)
class ScalingCiPayload:
    n: int
    per_category: int
    category_accuracy: dict[str, tuple[float, float, float]]
    confidence: float = DEFAULT_CONFIDENCE_LEVEL

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ScalingCiPayload:
        category_accuracy = {
            str(cat): (float(triple[0]), float(triple[1]), float(triple[2]))
            for cat, triple in data["category_accuracy"].items()
        }
        return cls(
            n=int(data["n"]),
            per_category=int(data["per_category"]),
            category_accuracy=category_accuracy,
            confidence=float(data.get("confidence", DEFAULT_CONFIDENCE_LEVEL)),
        )


@dataclass(frozen=True)
class StatisticalSummaryPayload:
    """Typed mean summary with uncertainty and provenance."""

    estimate: float
    low: float
    high: float
    n: int
    confidence: float
    method: str
    seed: int
    resamples: int
    standard_deviation: float
    standard_error: float
    median: float
    interval_interpretation: str = "descriptive_resampling_interval"
    small_cluster_warning: bool = False

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StatisticalSummaryPayload:
        return cls(
            estimate=float(data["estimate"]),
            low=float(data["low"]),
            high=float(data["high"]),
            n=int(data["n"]),
            confidence=float(data["confidence"]),
            method=str(data["method"]),
            seed=int(data["seed"]),
            resamples=int(data["resamples"]),
            standard_deviation=float(data["standard_deviation"]),
            standard_error=float(data["standard_error"]),
            median=float(data["median"]),
            interval_interpretation=str(data.get("interval_interpretation", "descriptive_resampling_interval")),
            small_cluster_warning=bool(data.get("small_cluster_warning", False)),
        )


@dataclass(frozen=True)
class SampleSizePointPayload:
    """One row of the multi-seed sample-size precision experiment."""

    per_category: int
    n_per_seed: int
    n_total: int
    n_seeds: int
    methods: dict[str, StatisticalSummaryPayload]
    paired_comparisons: dict[str, dict[str, float | int]]
    precision_plan: dict[str, float | int]
    stratum_statistics: dict[str, dict[str, dict[str, Any]]]
    stratum_paired_comparisons: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> SampleSizePointPayload:
        return cls(
            per_category=int(data["per_category"]),
            n_per_seed=int(data["n_per_seed"]),
            n_total=int(data["n_total"]),
            n_seeds=int(data["n_seeds"]),
            methods={
                str(name): StatisticalSummaryPayload.from_json(summary)
                for name, summary in data["methods"].items()
            },
            paired_comparisons={
                str(name): {str(key): value for key, value in comparison.items()}
                for name, comparison in data["paired_comparisons"].items()
            },
            precision_plan={str(key): value for key, value in data["precision_plan"].items()},
            stratum_statistics={
                str(method): {str(stratum): dict(summary) for stratum, summary in values.items()}
                for method, values in data.get("stratum_statistics", {}).items()
            },
            stratum_paired_comparisons={
                str(comparison): {
                    str(stratum): dict(summary) for stratum, summary in values.items()
                }
                for comparison, values in data.get("stratum_paired_comparisons", {}).items()
            },
        )


@dataclass(frozen=True)
class SampleSizePayload:
    """Typed aggregate for the sample-size and statistical-rigor figure."""

    experiment: str
    categories: int
    per_category_values: tuple[int, ...]
    seed_values: tuple[int, ...]
    confidence: float
    n_boot: int
    rows: tuple[SampleSizePointPayload, ...]
    comparison_family: dict[str, Any] | None = None
    accounting: dict[str, Any] | None = None
    analysis_contract: dict[str, Any] | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> SampleSizePayload:
        return cls(
            experiment=str(data["experiment"]),
            categories=int(data["categories"]),
            per_category_values=tuple(int(value) for value in data["per_category_values"]),
            seed_values=tuple(int(value) for value in data["seed_values"]),
            confidence=float(data["confidence"]),
            n_boot=int(data["n_boot"]),
            rows=tuple(SampleSizePointPayload.from_json(row) for row in data["rows"]),
            comparison_family=dict(data["comparison_family"])
            if data.get("comparison_family")
            else None,
            accounting=dict(data["accounting"]) if data.get("accounting") else None,
            analysis_contract=dict(data["analysis_contract"]) if data.get("analysis_contract") else None,
        )


@dataclass(frozen=True)
class InjectionProbeRow:
    probe: int
    harness_poisoned: bool
    harness_auditable: bool
    naive_poisoned: bool
    naive_auditable: bool
    neural_poisoned: bool | None = None
    neural_auditable: bool | None = None


@dataclass(frozen=True)
class InjectionEvalPayload:
    n_probes: int
    harness_poison_rate: float
    harness_audit_rate: float
    naive_poison_rate: float
    naive_audit_rate: float
    rows: tuple[InjectionProbeRow, ...]
    neural_model: str | None
    neural_poison_rate: float | None
    neural_rows: tuple[InjectionProbeRow, ...]
    harness_poison_ci: tuple[float, float, float] | None = None
    naive_poison_ci: tuple[float, float, float] | None = None
    neural_poison_ci: tuple[float, float, float] | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> InjectionEvalPayload:
        rows = tuple(
            InjectionProbeRow(
                probe=int(row["probe"]),
                harness_poisoned=bool(row["harness_poisoned"]),
                harness_auditable=bool(row["harness_auditable"]),
                naive_poisoned=bool(row["naive_poisoned"]),
                naive_auditable=bool(row["naive_auditable"]),
            )
            for row in data["rows"]
        )
        neural_rows = tuple(
            InjectionProbeRow(
                probe=int(row["probe"]),
                harness_poisoned=False,
                harness_auditable=False,
                naive_poisoned=False,
                naive_auditable=False,
                neural_poisoned=bool(row.get("neural_poisoned", False)),
                neural_auditable=bool(row.get("neural_auditable", False)),
            )
            for row in data.get("neural_rows", [])
        )
        return cls(
            n_probes=int(data["n_probes"]),
            harness_poison_rate=float(data["harness_poison_rate"]),
            harness_audit_rate=float(data["harness_audit_rate"]),
            naive_poison_rate=float(data["naive_poison_rate"]),
            naive_audit_rate=float(data["naive_audit_rate"]),
            rows=rows,
            neural_model=data.get("neural_model"),
            neural_poison_rate=data.get("neural_poison_rate"),
            neural_rows=neural_rows,
            harness_poison_ci=tuple(data["harness_poison_ci"]) if data.get("harness_poison_ci") else None,
            naive_poison_ci=tuple(data["naive_poison_ci"]) if data.get("naive_poison_ci") else None,
            neural_poison_ci=tuple(data["neural_poison_ci"]) if data.get("neural_poison_ci") else None,
        )


@dataclass(frozen=True)
class OrchestrationBaseline:
    naive_accuracy: float
    naive_grounding: float
    naive_efficiency: float
    naive_composite: float
    pipeline_accuracy: float
    pipeline_grounding: float
    pipeline_efficiency: float
    pipeline_composite: float

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> OrchestrationBaseline:
        return cls(
            naive_accuracy=float(data["naive_accuracy"]),
            naive_grounding=float(data["naive_grounding"]),
            naive_efficiency=float(data["naive_efficiency"]),
            naive_composite=float(data["naive_composite"]),
            pipeline_accuracy=float(data["pipeline_accuracy"]),
            pipeline_grounding=float(data["pipeline_grounding"]),
            pipeline_efficiency=float(data["pipeline_efficiency"]),
            pipeline_composite=float(data["pipeline_composite"]),
        )


@dataclass(frozen=True)
class LearnedRetrievalPayload:
    model: str
    n_probes: int
    surrogate_recall_at_1: float
    learned_recall_at_1: float
    surrogate_recall_ci: tuple[float, float, float] | None = None
    learned_recall_ci: tuple[float, float, float] | None = None
    paired_comparison: dict[str, Any] | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LearnedRetrievalPayload:
        return cls(
            model=str(data["model"]),
            n_probes=int(data["n_probes"]),
            surrogate_recall_at_1=float(data["surrogate_recall_at_1"]),
            learned_recall_at_1=float(data["learned_recall_at_1"]),
            surrogate_recall_ci=tuple(data["surrogate_recall_ci"]) if data.get("surrogate_recall_ci") else None,
            learned_recall_ci=tuple(data["learned_recall_ci"]) if data.get("learned_recall_ci") else None,
            paired_comparison=dict(data["paired_binary_comparison"])
            if data.get("paired_binary_comparison")
            else None,
        )


__all__ = [
    "NeuralEvalRow",
    "NeuralEvalPayload",
    "BottleneckNeuralRow",
    "BottleneckRankingModes",
    "BottleneckAdaptive",
    "BottleneckPayload",
    "LongMemEvalPayload",
    "ScalingCiPayload",
    "StatisticalSummaryPayload",
    "SampleSizePointPayload",
    "SampleSizePayload",
    "InjectionProbeRow",
    "InjectionEvalPayload",
    "OrchestrationBaseline",
    "LearnedRetrievalPayload",
]
