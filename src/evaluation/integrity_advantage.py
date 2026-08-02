"""Source-bound screen of THALIA's current integrity-related endpoints.

This module keeps the legacy lexical cited-excerpt/source-exposure proxy separate
from adjudicated provenance, poisoning, and answer-quality claims.
It re-analyzes the recorded paired probes and held-out compiler rows, records the
missing uncertainty where an aggregate lacks paired rows, and assigns a cautious
promotion status to each comparison.  Positive ``advantage_delta`` always means
the left condition is better after applying the declared direction of the outcome;
the raw delta remains in the record for auditability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .ablation import no_harness_baseline
from .accounting import file_provenance
from .dataset import build_demo_dataset
from ..compiler.metrics import ACCURACY_WEIGHT, EFFICIENCY_WEIGHT, GROUNDING_WEIGHT
from .statistics import (
    binary_rate,
    clustered_paired_comparison,
    exact_paired_binary,
    holm_named,
    paired_bootstrap_delta,
)


_CONFIDENCE = 0.95
_BOOTSTRAP_SEED = 1701
_PERMUTATION_SEED = 1702
_RESAMPLES = 5000
_SCREEN_PROMOTION_STATUS = "screen_only_unpromoted"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _require_rows(value: object, name: str) -> list[dict[str, Any]]:
    """Validate a committed aggregate's row collection."""
    if not isinstance(value, list) or not value or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{name} must contain a non-empty list of row objects")
    return [dict(row) for row in value]


def _record_sources(paths: Iterable[Path]) -> list[dict[str, object]]:
    return [file_provenance(path) for path in sorted(paths, key=lambda item: str(item))]


def _binary_comparison(
    *,
    comparison_id: str,
    label: str,
    construct: str,
    comparator: str,
    left_label: str,
    right_label: str,
    left: list[bool],
    right: list[bool],
    direction: str,
    unit: str,
    evidence_tier: str,
    claim_status: str,
    interpretation: str,
) -> dict[str, object]:
    if direction not in {"higher_is_better", "lower_is_better"}:
        raise ValueError(f"unsupported direction: {direction}")
    paired = exact_paired_binary(left, right)
    delta_interval = paired_bootstrap_delta(
        left,
        right,
        resamples=_RESAMPLES,
        seed=_BOOTSTRAP_SEED,
        confidence=_CONFIDENCE,
    )
    left_rate = binary_rate(sum(left), len(left), unit=unit)
    right_rate = binary_rate(sum(right), len(right), unit=unit)
    raw_delta = left_rate.rate - right_rate.rate
    advantage_delta = raw_delta if direction == "higher_is_better" else -raw_delta
    raw_low, raw_high = delta_interval.low, delta_interval.high
    # The paired bootstrap is computed in the raw left-minus-right orientation.
    # Keep that record for audit, but transform both ends when the reported
    # estimand reverses lower-is-better outcomes.  Negation reverses interval
    # order, so leaving these bounds untouched would draw an interval around a
    # direction-normalized point estimate in the wrong coordinate system.
    advantage_low, advantage_high = (
        (raw_low, raw_high)
        if direction == "higher_is_better"
        else (-raw_high, -raw_low)
    )
    return {
        "id": comparison_id,
        "label": label,
        "construct": construct,
        "comparator": comparator,
        "left_label": left_label,
        "right_label": right_label,
        "raw_delta": raw_delta,
        "advantage_delta": advantage_delta,
        "estimate": advantage_delta,
        "low": advantage_low,
        "high": advantage_high,
        "raw_low": raw_low,
        "raw_high": raw_high,
        "p_value": paired.p_value,
        "adjusted_p_value": None,
        "n": paired.n,
        "unit": unit,
        "direction": direction,
        "evidence_tier": evidence_tier,
        "claim_status": claim_status,
        "promotion_status": _SCREEN_PROMOTION_STATUS,
        "statistical_method": paired.method,
        "interval_method": "paired_percentile_bootstrap_delta_plus_wilson_rate_intervals",
        "interval_seed": _BOOTSTRAP_SEED,
        "interval_resamples": _RESAMPLES,
        "paired": True,
        "uncertainty_available": True,
        "small_cluster_warning": False,
        "left_rate": left_rate.to_dict(),
        "right_rate": right_rate.to_dict(),
        "left_success_right_failure": paired.left_success_right_failure,
        "left_failure_right_success": paired.left_failure_right_success,
        "interpretation": interpretation,
    }


def _point_comparison(
    *,
    comparison_id: str,
    label: str,
    construct: str,
    comparator: str,
    left_label: str,
    right_label: str,
    raw_delta: float,
    n: int,
    unit: str,
    direction: str,
    evidence_tier: str,
    claim_status: str,
    interpretation: str,
    paired: bool = False,
    uncertainty_available: bool = False,
) -> dict[str, object]:
    if direction not in {"higher_is_better", "lower_is_better"}:
        raise ValueError(f"unsupported direction: {direction}")
    advantage_delta = raw_delta if direction == "higher_is_better" else -raw_delta
    return {
        "id": comparison_id,
        "label": label,
        "construct": construct,
        "comparator": comparator,
        "left_label": left_label,
        "right_label": right_label,
        "raw_delta": float(raw_delta),
        "advantage_delta": float(advantage_delta),
        "estimate": float(advantage_delta),
        "low": None,
        "high": None,
        "p_value": None,
        "adjusted_p_value": None,
        "n": int(n),
        "unit": unit,
        "direction": direction,
        "evidence_tier": evidence_tier,
        "claim_status": claim_status,
        "promotion_status": _SCREEN_PROMOTION_STATUS,
        "statistical_method": "finite_point_difference",
        "interval_method": "not_available_for_recorded_aggregate",
        "paired": paired,
        "uncertainty_available": uncertainty_available,
        "small_cluster_warning": False,
        "interpretation": interpretation,
    }


def build_integrity_advantage_report(project_root: str | Path | None = None) -> dict[str, object]:
    """Build the current integrity-advantage evidence screen.

    The report is intentionally an evidence screen, not a pooled meta-analysis.
    Comparisons retain their native units and are ranked by claimability rather
    than by the numerical magnitude of their outcome scales.
    """
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    data_dir = root / "data"
    generated_dir = root / "output" / "data"
    injection_path = data_dir / "injection_eval.json"
    learned_path = data_dir / "learned_retrieval.json"
    neural_path = data_dir / "neural_eval.json"
    bottleneck_path = data_dir / "longmemeval_bottleneck.json"
    compiler_path = generated_dir / "compiler_generalization.json"

    injection = _load_json(injection_path)
    learned = _load_json(learned_path)
    neural = _load_json(neural_path)
    bottleneck = _load_json(bottleneck_path)
    compiler = _load_json(compiler_path)

    injection_rows = _require_rows(injection.get("rows"), "injection rows")
    learned_rows = _require_rows(learned.get("rows"), "learned retrieval rows")
    neural_rows = _require_rows(neural.get("rows"), "neural rows")
    compiler_rows = _require_rows(compiler.get("rows"), "compiler rows")

    comparisons: list[dict[str, object]] = []

    baseline = no_harness_baseline()
    demo_size = len(build_demo_dataset())
    comparisons.append(
        _point_comparison(
            comparison_id="orchestration_composite",
            label="Composite metric: THALIA vs. naive",
            construct="evidence_efficient_orchestration",
            comparator="naive full-context baseline",
            left_label="typed pipeline",
            right_label="naive full context",
            raw_delta=float(baseline["composite_lift"]),
            n=demo_size,
            unit="synthetic_example",
            direction="higher_is_better",
            evidence_tier="finite_synthetic",
            claim_status="conditional_metric_lift",
            interpretation=(
                "The composite lift is supplied by citation support and structural efficiency; "
                "raw answer token-F1 ties under the extractive backend."
            ),
        )
    )
    comparisons[-1]["component_deltas"] = {
        "answer_token_f1": float(baseline["pipeline_accuracy"] - baseline["naive_accuracy"]),
        "citation_support": float(baseline["pipeline_grounding"] - baseline["naive_grounding"]),
        "evidence_efficiency": float(baseline["pipeline_efficiency"] - baseline["naive_efficiency"]),
        "weighted_components": {
            "answer_token_f1": float(
                ACCURACY_WEIGHT * (baseline["pipeline_accuracy"] - baseline["naive_accuracy"])
            ),
            "citation_support": float(
                GROUNDING_WEIGHT * (baseline["pipeline_grounding"] - baseline["naive_grounding"])
            ),
            "evidence_efficiency": float(
                EFFICIENCY_WEIGHT * (baseline["pipeline_efficiency"] - baseline["naive_efficiency"])
            ),
        },
    }

    comparisons.append(
        _binary_comparison(
            comparison_id="provenance_auditability",
            label="Lexical cited-excerpt/source-exposure proxy under injection",
            construct="lexical_cited_excerpt_source_exposure_proxy",
            comparator="naive full-context baseline",
            left_label="THALIA",
            right_label="naive",
            left=[bool(row["harness_auditable"]) for row in injection_rows],
            right=[bool(row["naive_auditable"]) for row in injection_rows],
            direction="higher_is_better",
            unit="attack_probe",
            evidence_tier="deterministic_paired_probe",
            claim_status="strongest_current_lexical_provenance_proxy",
            interpretation=(
                "The harness's cited excerpts lexically contain the supplied gold value on every "
                "recorded probe, while the baseline emits no citation channel. This is a source-"
                "exposure proxy, not a source-record, entailment, or adjudicated-auditability result."
            ),
        )
    )

    comparisons.append(
        _binary_comparison(
            comparison_id="poisoning_rate",
            label="Recorded poisoned-answer rate under injection",
            construct="recorded_poisoned_answer_rate",
            comparator="naive full-context baseline",
            left_label="THALIA",
            right_label="naive",
            left=[bool(row["harness_poisoned"]) for row in injection_rows],
            right=[bool(row["naive_poisoned"]) for row in injection_rows],
            direction="lower_is_better",
            unit="attack_probe",
            evidence_tier="deterministic_paired_probe",
            claim_status="null_poisoning_rate_advantage",
            interpretation="The paired probe records the same poisoned-answer count for both conditions.",
        )
    )

    comparisons.append(
        _binary_comparison(
            comparison_id="learned_retrieval_recall",
            label="Paraphrase retrieval recall@1",
            construct="semantic_retrieval_representation",
            comparator="hashing surrogate",
            left_label="learned embedder",
            right_label="hashing surrogate",
            left=[bool(row["learned_hit"]) for row in learned_rows],
            right=[bool(row["surrogate_hit"]) for row in learned_rows],
            direction="higher_is_better",
            unit="paraphrase_probe",
            evidence_tier="live_model_paired_probe",
            claim_status="promising_unconfirmed_representation_advantage",
            interpretation="The learned embedder wins four paired probes; the exact paired test remains inconclusive.",
        )
    )

    compiler_left = {str(row["seed"]): [float(row["mipro"]["holdout_composite"])] for row in compiler_rows}
    compiler_right = {str(row["seed"]): [float(row["baseline"]["holdout_composite"])] for row in compiler_rows}
    compiler_comparison = clustered_paired_comparison(
        compiler_left,
        compiler_right,
        resamples=_RESAMPLES,
        permutations=_RESAMPLES,
        bootstrap_seed=_BOOTSTRAP_SEED,
        permutation_seed=_PERMUTATION_SEED,
        confidence=_CONFIDENCE,
    )
    compiler_record = _point_comparison(
        comparison_id="compiler_mipro_holdout",
        label="MIPRO-style held-out composite",
        construct="compiler_search_generalization",
        comparator="default configuration",
        left_label="MIPRO-style",
        right_label="baseline",
        raw_delta=compiler_comparison.mean_delta,
        n=compiler_comparison.cluster_count,
        unit="seed_cluster",
        direction="higher_is_better",
        evidence_tier="finite_synthetic_held_out",
        claim_status="promising_finite_cluster_signal",
        interpretation=(
            f"The mean held-out gain is small across {compiler_comparison.cluster_count} "
            "seed clusters; the interval remains descriptive and the screen is unpromoted."
        ),
        paired=True,
        uncertainty_available=True,
    )
    compiler_record.update(
        {
            "low": compiler_comparison.low,
            "high": compiler_comparison.high,
            "p_value": compiler_comparison.p_value,
            "statistical_method": compiler_comparison.p_value_method,
            "interval_method": compiler_comparison.interval_interpretation,
            "cluster_count": compiler_comparison.cluster_count,
            "small_cluster_warning": compiler_comparison.small_cluster_warning,
            "effect_size": compiler_comparison.effect_size,
        }
    )
    comparisons.append(compiler_record)

    recorded_neural = neural.get("paired_neural_minus_extractive") or {}
    if not recorded_neural:
        raise ValueError("neural_eval.json lacks paired_neural_minus_extractive")
    comparisons.append(
        {
            **_point_comparison(
                comparison_id="local_neural_answer_f1",
                label="Local neural answer token-F1",
                construct="answer_generation_quality_proxy",
                comparator="extractive Reasoner",
                left_label=str(neural.get("model", "neural model")),
                right_label="extractive",
                raw_delta=float(recorded_neural["mean_delta"]),
                n=int(neural["n"]),
                unit="paired_synthetic_example",
                direction="higher_is_better",
                evidence_tier="live_model_paired_comparison",
                claim_status="no_general_answer_quality_advantage",
                interpretation="The recorded local aggregate is mixed and its paired interval crosses zero.",
                paired=True,
                uncertainty_available=True,
            ),
            "low": float(recorded_neural["low"]),
            "high": float(recorded_neural["high"]),
            "p_value": float(recorded_neural["p_value"]),
            "statistical_method": str(recorded_neural.get("p_value_method", "recorded_paired_comparison")),
            "interval_method": str(recorded_neural.get("interval_interpretation", "recorded_descriptive_interval")),
        }
    )

    sweep_values = bottleneck.get("sweep_values")
    neural_by_maxwindows = bottleneck.get("neural_by_maxwindows")
    if not isinstance(sweep_values, list) or not sweep_values:
        raise ValueError("bottleneck source must contain non-empty sweep_values")
    if not isinstance(neural_by_maxwindows, dict):
        raise ValueError("bottleneck source must contain neural_by_maxwindows")
    compact_windows = min(int(value) for value in sweep_values)
    adaptive = bottleneck.get("neural_adaptive")
    if not isinstance(adaptive, dict):
        raise ValueError("bottleneck source must contain neural_adaptive")
    compact = neural_by_maxwindows.get(str(compact_windows))
    if not isinstance(compact, dict):
        raise ValueError(f"bottleneck source lacks compact window row {compact_windows}")
    adaptive_delta = float(adaptive["accuracy"]) - float(compact["accuracy"])
    comparisons.append(
        _point_comparison(
            comparison_id="adaptive_context_policy",
            label="Adaptive context policy answer token-F1",
            construct="context_reachability_intervention",
            comparator=f"compact context ({compact_windows} windows)",
            left_label="adaptive policy",
            right_label="compact context",
            raw_delta=adaptive_delta,
            n=int(bottleneck["n_neural"]),
            unit="retained_external_question",
            direction="higher_is_better",
            evidence_tier="external_transfer_point_comparison",
            claim_status="promising_unconfirmed_context_advantage",
            interpretation="The aggregate improves under widened/adaptive context, but paired question-level rows are absent.",
            paired=False,
            uncertainty_available=False,
        )
    )

    p_values: dict[str, float] = {}
    for row in comparisons:
        p_value = row.get("p_value")
        if isinstance(p_value, (int, float)):
            p_values[str(row["id"])] = float(p_value)
    adjusted = holm_named(p_values)
    for row in comparisons:
        if row["id"] in adjusted:
            row["adjusted_p_value"] = adjusted[row["id"]]

    strongest = [
        row["id"]
        for row in comparisons
        if str(row["claim_status"]).startswith("strongest_current_")
    ]
    promising = [
        row["id"]
        for row in comparisons
        if str(row["claim_status"]).startswith("promising_")
    ]
    nulls = [
        row["id"]
        for row in comparisons
        if str(row["claim_status"]).startswith("null_") or str(row["claim_status"]).startswith("no_")
    ]
    return {
        "schema_version": 3,
        "analysis": "integrity_advantage_audit_v1",
        "confidence": _CONFIDENCE,
        "resamples": _RESAMPLES,
        "multiple_comparison_family": {
            "name": "exploratory_current_integrity_advantage_screen",
            "tested_comparisons": list(p_values),
            "correction": "holm_step_down",
            "interpretation": "adjusted values screen heterogeneous endpoints; they do not create a pooled estimand",
        },
        "comparisons": comparisons,
        "current_conclusions": {
            "strongest_current_lexical_provenance_proxy": strongest,
            "conditional_orchestration_lift": ["orchestration_composite"],
            "promising_unconfirmed": promising,
            "null_or_negative": nulls,
            "general_answer_quality_status": "unestablished",
        },
        "promotion": {
            "status": _SCREEN_PROMOTION_STATUS,
            "promoted": False,
            "p0_provenance_confirmation_executed": False,
            "p0_provenance_poisoning_separation_executed": False,
            "promotion_gate_passed": False,
            "reason": (
                "The P0 provenance confirmation and provenance-versus-poisoning "
                "separation studies are unexecuted; this report is an exploratory "
                "source-bound screen, not a promoted integrity claim."
            ),
        },
        "source_counts": {
            "injection_probes": len(injection_rows),
            "learned_retrieval_probes": len(learned_rows),
            "local_neural_examples": len(neural_rows),
            "compiler_seed_clusters": len(compiler_rows),
        },
        "source_provenance": _record_sources(
            [injection_path, learned_path, neural_path, bottleneck_path, compiler_path]
        ),
        "analysis_code": _record_sources(
            [Path(__file__), Path(__file__).with_name("statistics.py"), Path(__file__).with_name("ablation.py")]
        ),
        "design_boundaries": {
            "positive_effect_definition": "left condition minus comparator after direction normalization",
            "native_units_preserved": True,
            "pooled_effect_size": False,
            "population_inference": False,
            "human_quality_labels": False,
            "paired_rows_required_for_confirmation": True,
        },
    }


__all__ = ["build_integrity_advantage_report"]
