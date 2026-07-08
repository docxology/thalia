"""Typed payloads for committed evaluation JSON consumed by figure plotters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        )


@dataclass(frozen=True)
class ScalingCiPayload:
    n: int
    per_category: int
    category_accuracy: dict[str, tuple[float, float, float]]

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

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LearnedRetrievalPayload:
        return cls(
            model=str(data["model"]),
            n_probes=int(data["n_probes"]),
            surrogate_recall_at_1=float(data["surrogate_recall_at_1"]),
            learned_recall_at_1=float(data["learned_recall_at_1"]),
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
    "InjectionProbeRow",
    "InjectionEvalPayload",
    "OrchestrationBaseline",
    "LearnedRetrievalPayload",
]
