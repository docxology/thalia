"""Manuscript variable generation: every prose number is a generated token.

Mirrors the template's reproducibility-by-construction discipline: each
``{{TOKEN}}`` used in the manuscript is emitted by exactly this function from the
live evaluation results and configuration. A drift between prose and code shows
up as a missing/changed token, which the manuscript-variable test flags.
"""

from __future__ import annotations

import json
from pathlib import Path

from .compiler.metrics import (
    ACCURACY_WEIGHT,
    EFFICIENCY_WEIGHT,
    GROUNDING_WEIGHT,
    _EFFICIENCY_SCALE,
)
from .compiler.mipro import MIPROCompiler
from .config import (
    DEFAULT_CONFIDENCE_LEVEL,
    NUM_RUNTIME_STAGES,
    NUM_TOTAL_STAGES,
    HarnessConfig,
    default_config,
)
from .figures.manifest import BACKEND_FIGURE_WIDTH_PERCENT
from .retrieval.fusion import DEFAULT_LEXICAL_WEIGHT, DEFAULT_SEMANTIC_WEIGHT
from .retrieval.lexical import DEFAULT_B, DEFAULT_K1
from .evaluation import (
    build_demo_dataset,
    composite_weight_sensitivity,
    injection_resistance,
    large_dataset_eval,
    memory_recall_ablation,
    no_harness_baseline,
    noise_scaling_experiment,
    run_full_eval,
)
from .evaluation.budget import TIGHT_MAX_EVIDENCE, TIGHT_TOP_K
from .harness import build_run_fn
from .formalism_traceability import load_and_validate_traceability, traceability_markdown
from .manuscript_integrity import load_paper_audit
from .project_config import load_thalia_overlay_section
from .signatures import TaskCategory

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_NEURAL_EVAL_PATH = _DATA_DIR / "neural_eval.json"
_LEARNED_EVAL_PATH = _DATA_DIR / "learned_retrieval.json"
_INJECTION_EVAL_PATH = _DATA_DIR / "injection_eval.json"
_LME_PATH = _DATA_DIR / "longmemeval_results.json"
_LME_BN_PATH = _DATA_DIR / "longmemeval_bottleneck.json"
_OPENROUTER_EVAL_PATH = _DATA_DIR / "openrouter_eval.json"
_EVAL_RESULTS_PATH = _DATA_DIR.parent / "output" / "data" / "eval_results.json"
_SEED_SENSITIVITY_PATH = _DATA_DIR.parent / "output" / "data" / "seed_sensitivity.json"
_COMPILER_GENERALIZATION_PATH = _DATA_DIR.parent / "output" / "data" / "compiler_generalization.json"
_INTEGRITY_ADVANTAGE_PATH = _DATA_DIR / "integrity_advantage.json"


def _fmt(value: float, places: int = 3) -> str:
    """Format a float to a fixed number of decimal places."""
    return f"{value:.{places}f}"


def _fmt_signed(value: float, places: int = 3) -> str:
    """Format an effect with an explicit sign."""
    return f"{value:+.{places}f}"


def _fmt_p(value: float) -> str:
    """Format a p-value without collapsing small values to zero."""
    if value < 0.001:
        return f"{value:.2e}"
    if value < 0.1:
        return f"{value:.4f}"
    return f"{value:.3f}"


def _coverage_gate() -> int:
    """Read the enforced ``src/`` coverage gate from pyproject.toml (no hard-coding)."""
    try:
        import tomllib  # Python >= 3.11
    except ModuleNotFoundError:  # pragma: no cover - exercised only on 3.10
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    return int(data["tool"]["coverage"]["report"]["fail_under"])


def _load_neural_eval() -> dict:
    """Load the committed extractive-vs-neural measurement (regenerable offline).

    Produced by ``scripts/run_neural_eval.py`` against a live Ollama model. It is a
    tracked artifact so the manuscript's neural tokens generate without re-running
    the model; raises clearly if it is missing rather than silently dropping tokens.
    """
    if not _NEURAL_EVAL_PATH.exists():
        raise FileNotFoundError(
            f"{_NEURAL_EVAL_PATH} is missing; regenerate with "
            "`python scripts/run_neural_eval.py` on a host serving the Ollama model."
        )
    return json.loads(_NEURAL_EVAL_PATH.read_text())


def _load_learned_eval() -> dict:
    """Load the committed surrogate-vs-learned retrieval measurement (regenerable)."""
    if not _LEARNED_EVAL_PATH.exists():
        raise FileNotFoundError(
            f"{_LEARNED_EVAL_PATH} is missing; regenerate with "
            "`python scripts/run_learned_retrieval.py` on a host serving the embedding model."
        )
    return json.loads(_LEARNED_EVAL_PATH.read_text())


def _load_generated_eval(path: Path, command: str) -> dict:
    """Load a generated aggregate and fail closed when its lane was skipped."""
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; regenerate with `{command}` before manuscript generation.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"generated aggregate {path} is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"generated aggregate {path} must contain a JSON object")
    return payload


def _load_quality_plan() -> dict[str, object]:
    """Load the planned quality-study scope from the THALIA-owned overlay."""
    return load_thalia_overlay_section("model_quality")


def generate_variables(config: HarnessConfig | None = None) -> dict[str, str]:
    """Generate the full ``{{TOKEN}} -> value`` map for the manuscript.

    Args:
        config: Harness configuration to report and evaluate (defaults to
            :func:`~src.config.default_config`).

    Returns:
        A dict of string tokens to string values, covering configuration, headline
        evaluation results, the retriever comparison, and the compiled optimum.
    """
    config = config or default_config()
    audit_ledger = load_paper_audit()
    traceability = load_and_validate_traceability()
    if traceability["status"] != "pass":
        raise ValueError(f"formalism traceability failed: {traceability['issues']}")
    results = run_full_eval(config)
    comparison = results["retriever_comparison"]
    seed_sensitivity = _load_generated_eval(
        _SEED_SENSITIVITY_PATH,
        "uv run --project . --extra dev python scripts/run_seed_sensitivity.py",
    )
    compiler_generalization = _load_generated_eval(
        _COMPILER_GENERALIZATION_PATH,
        "uv run --project . --extra dev python scripts/run_compiler_generalization.py",
    )
    integrity_advantage = _load_generated_eval(
        _INTEGRITY_ADVANTAGE_PATH,
        "uv run --project . --extra dev python scripts/analyze_integrity_advantage.py",
    )
    integrity_rows = {
        str(row["id"]): row
        for row in integrity_advantage.get("comparisons", [])
        if isinstance(row, dict) and "id" in row
    }
    required_integrity_ids = {
        "orchestration_composite",
        "provenance_auditability",
        "poisoning_rate",
        "learned_retrieval_recall",
        "compiler_mipro_holdout",
        "local_neural_answer_f1",
        "adaptive_context_policy",
    }
    if not required_integrity_ids <= integrity_rows.keys():
        missing = sorted(required_integrity_ids - integrity_rows.keys())
        raise ValueError(f"integrity advantage aggregate is missing comparisons: {missing}")

    # Noise-regime endpoint: at the highest distractor level the lexical and the
    # hashing-surrogate "semantic" lanes diverge. Exposing these as tokens binds
    # the §evaluation noise prose to the measured numbers (it cannot drift).
    noise = noise_scaling_experiment()
    noise_max_level = noise["lexical"][-1][0]
    noise_lexical = noise["lexical"][-1][1]
    noise_semantic = noise["semantic"][-1][1]

    dataset = build_demo_dataset()
    compiled = MIPROCompiler(auto="heavy").compile(lambda cfg: build_run_fn(cfg), dataset)
    quality_plan = _load_quality_plan()
    quality_pilot = quality_plan.get("pilot")
    quality_confirmatory = quality_plan.get("confirmatory")
    quality_models = quality_plan.get("models")
    quality_conditions = quality_plan.get("conditions")
    if not isinstance(quality_pilot, dict) or not isinstance(quality_confirmatory, dict):
        raise ValueError("model_quality pilot and confirmatory plans must be mappings")
    if not isinstance(quality_models, list) or not quality_models:
        raise ValueError("model_quality models must be a non-empty list")
    if not isinstance(quality_conditions, list) or not quality_conditions:
        raise ValueError("model_quality conditions must be a non-empty list")
    quality_total_raw = quality_plan.get("total_questions", 0)
    quality_pilot_raw = quality_pilot.get("total_questions", 0)
    quality_confirmatory_raw = quality_confirmatory.get("total_questions", 0)
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (quality_total_raw, quality_pilot_raw, quality_confirmatory_raw)
    ):
        raise ValueError("model_quality question counts must be integers")
    quality_total = quality_total_raw
    quality_pilot_total = quality_pilot_raw
    quality_confirmatory_total = quality_confirmatory_raw
    if quality_total != quality_pilot_total + quality_confirmatory_total:
        raise ValueError("model_quality pilot and confirmatory counts must sum to total_questions")
    quality_annotation = quality_plan.get("annotation")
    quality_primary = quality_plan.get("primary_outcome")
    if not isinstance(quality_annotation, dict) or not isinstance(quality_primary, dict):
        raise ValueError("model_quality annotation and primary_outcome must be mappings")

    variables: dict[str, str] = {
        # Configuration
        "CONFIG_TOP_K": str(config.top_k),
        "CONFIG_MAX_WINDOWS": str(config.max_windows),
        "CONFIG_MAX_EVIDENCE": str(config.max_evidence),
        "CONFIG_RRF_K": str(config.rrf_k),
        "CONFIG_CONTEXT_BUDGET": str(config.context_budget_tokens),
        "CONFIG_NUM_STAGES": str(NUM_TOTAL_STAGES),
        "CONFIG_NUM_RUNTIME_STAGES": str(NUM_RUNTIME_STAGES),
        "CONFIG_NUM_CATEGORIES": str(len(TaskCategory)),
        "CONFIG_TIGHT_TOP_K": str(TIGHT_TOP_K),
        "CONFIG_TIGHT_MAX_EVIDENCE": str(TIGHT_MAX_EVIDENCE),
        # Algorithm constants sourced from code so the prose/equations cannot drift.
        "CONFIG_WEIGHT_ACC": _fmt(ACCURACY_WEIGHT, 1),
        "CONFIG_WEIGHT_GROUND": _fmt(GROUNDING_WEIGHT, 1),
        "CONFIG_WEIGHT_EFF": _fmt(EFFICIENCY_WEIGHT, 1),
        "CONFIG_LEXICAL_WEIGHT": _fmt(DEFAULT_LEXICAL_WEIGHT, 2),
        "CONFIG_SEMANTIC_WEIGHT": _fmt(DEFAULT_SEMANTIC_WEIGHT, 2),
        "CONFIG_EFFICIENCY_SCALE": str(_EFFICIENCY_SCALE),
        "CONFIG_BM25_K1": _fmt(DEFAULT_K1, 1),
        "CONFIG_BM25_B": _fmt(DEFAULT_B, 2),
        "CONFIG_ADAPTIVE_RATIO": str(config.adaptive_window_ratio),
        "CONFIG_CI_LEVEL": str(round(DEFAULT_CONFIDENCE_LEVEL * 100)),
        "CONFIG_BACKEND_FIGURE_WIDTH": str(BACKEND_FIGURE_WIDTH_PERCENT),
        "CONFIG_COV_GATE": str(_coverage_gate()),
        # Planned quality-study scope. These are protocol metadata, not observed
        # results; keeping them tokenised prevents the manuscript plan from drifting
        # away from experiment_plan.yaml.
        "RESULT_QUALITY_TOTAL_N": str(quality_total),
        "RESULT_QUALITY_PILOT_N": str(quality_pilot_total),
        "RESULT_QUALITY_CONFIRMATORY_N": str(quality_confirmatory_total),
        "RESULT_QUALITY_CONDITIONS": str(len(quality_models) * len(quality_conditions)),
        "RESULT_QUALITY_RATERS": str(quality_annotation.get("raters", "pending")),
        "RESULT_QUALITY_PRIMARY": str(quality_primary.get("name", "pending")),
        # The formalism graph is a generated manuscript input, not a hand-maintained
        # claim.  The table itself is injected below so code/test anchors stay in
        # lock-step with the validated registry.
        "RESULT_FORMALISM_COUNT": str(traceability["n_formalisms"]),
        "RESULT_TRACEABILITY_EDGE_COUNT": str(traceability["n_connections"]),
        "RESULT_CLAIM_COUNT": str(traceability["n_claims"]),
        "RESULT_TRACEABILITY_STATUS": str(traceability["status"]),
        "FORMALISM_TRACEABILITY_TABLE": traceability_markdown(audit_ledger),
        # Dataset / headline results
        "RESULT_NUM_EXAMPLES": str(results["n_examples"]),
        "RESULT_COMPOSITE": _fmt(results["composite"]),
        "RESULT_ACCURACY": _fmt(results["accuracy"]),
        "RESULT_GROUNDING": _fmt(results["grounding"]),
        "RESULT_EFFICIENCY": _fmt(results["efficiency"]),
        # Retriever comparison
        "RESULT_LEXICAL_COMPOSITE": _fmt(comparison["lexical"]),
        "RESULT_SEMANTIC_COMPOSITE": _fmt(comparison["semantic"]),
        "RESULT_HYBRID_COMPOSITE": _fmt(comparison["hybrid"]),
        "RESULT_BEST_MODE": str(comparison["best_mode"]),
        # Noise-regime endpoint (highest distractor level)
        "RESULT_NOISE_MAX_DISTRACTORS": str(noise_max_level),
        "RESULT_NOISE_LEXICAL": _fmt(noise_lexical),
        "RESULT_NOISE_SEMANTIC": _fmt(noise_semantic),
        # Compiled optimum
        "RESULT_COMPILED_SCORE": _fmt(compiled.best_score),
        "RESULT_COMPILED_TOP_K": str(compiled.best_config.top_k),
        "RESULT_COMPILED_MAX_EVIDENCE": str(compiled.best_config.max_evidence),
        "RESULT_NUM_CANDIDATES": str(compiled.n_candidates),
    }

    # Current integrity-advantage screen. These tokens bind the manuscript to the
    # same endpoint-level report used by the audit figure and handoff document.
    audit_row = integrity_rows["provenance_auditability"]
    poison_row = integrity_rows["poisoning_rate"]
    learned_row = integrity_rows["learned_retrieval_recall"]
    compiler_row = integrity_rows["compiler_mipro_holdout"]
    neural_row = integrity_rows["local_neural_answer_f1"]
    adaptive_row = integrity_rows["adaptive_context_policy"]
    variables.update(
        {
            "RESULT_INTEGRITY_COMPOSITE_LIFT": _fmt_signed(
                float(integrity_rows["orchestration_composite"]["advantage_delta"])
            ),
            "RESULT_INTEGRITY_AUDIT_N": str(audit_row["n"]),
            "RESULT_INTEGRITY_AUDIT_DELTA": _fmt_signed(float(audit_row["advantage_delta"])),
            "RESULT_INTEGRITY_AUDIT_CI": (
                f"[{_fmt(float(audit_row['low']))}, {_fmt(float(audit_row['high']))}]"
            ),
            "RESULT_INTEGRITY_AUDIT_RATE": _fmt(float(audit_row["left_rate"]["rate"])),
            "RESULT_INTEGRITY_AUDIT_P": _fmt_p(float(audit_row["p_value"])),
            "RESULT_INTEGRITY_AUDIT_ADJ_P": _fmt_p(float(audit_row["adjusted_p_value"])),
            "RESULT_INTEGRITY_POISON_DELTA": _fmt_signed(float(poison_row["advantage_delta"])),
            "RESULT_INTEGRITY_POISON_CI": (
                f"[{_fmt(float(poison_row['low']))}, {_fmt(float(poison_row['high']))}]"
            ),
            "RESULT_INTEGRITY_POISON_P": _fmt_p(float(poison_row["p_value"])),
            "RESULT_INTEGRITY_POISON_ADJ_P": _fmt_p(float(poison_row["adjusted_p_value"])),
            "RESULT_INTEGRITY_LEARNED_DELTA": _fmt_signed(float(learned_row["advantage_delta"])),
            "RESULT_INTEGRITY_LEARNED_CI": (
                f"[{_fmt(float(learned_row['low']))}, {_fmt(float(learned_row['high']))}]"
            ),
            "RESULT_INTEGRITY_LEARNED_P": _fmt_p(float(learned_row["p_value"])),
            "RESULT_INTEGRITY_LEARNED_ADJ_P": _fmt_p(float(learned_row["adjusted_p_value"])),
            "RESULT_INTEGRITY_COMPILER_DELTA": _fmt_signed(float(compiler_row["advantage_delta"]), 4),
            "RESULT_INTEGRITY_COMPILER_CI": (
                f"[{_fmt(float(compiler_row['low']), 4)}, {_fmt(float(compiler_row['high']), 4)}]"
            ),
            "RESULT_INTEGRITY_COMPILER_P": _fmt_p(float(compiler_row["p_value"])),
            "RESULT_INTEGRITY_COMPILER_ADJ_P": _fmt_p(float(compiler_row["adjusted_p_value"])),
            "RESULT_INTEGRITY_NEURAL_DELTA": _fmt_signed(float(neural_row["advantage_delta"])),
            "RESULT_INTEGRITY_NEURAL_CI": (
                f"[{_fmt(float(neural_row['low']))}, {_fmt(float(neural_row['high']))}]"
            ),
            "RESULT_INTEGRITY_NEURAL_P": _fmt_p(float(neural_row["p_value"])),
            "RESULT_INTEGRITY_NEURAL_ADJ_P": _fmt_p(float(neural_row["adjusted_p_value"])),
            "RESULT_INTEGRITY_ADAPTIVE_DELTA": _fmt_signed(float(adaptive_row["advantage_delta"])),
            "RESULT_INTEGRITY_ADAPTIVE_N": str(adaptive_row["n"]),
        }
    )

    # No-harness baseline + composite-weight sensitivity (deterministic ablations).
    baseline = no_harness_baseline(dataset)
    sweep = composite_weight_sensitivity(dataset)
    weights = sweep["accuracy_weights"]
    win_k, win_e = sweep["distinct_winners"][0]
    variables.update(
        {
            "RESULT_NAIVE_ACCURACY": _fmt(baseline["naive_accuracy"]),
            "RESULT_NAIVE_COMPOSITE": _fmt(baseline["naive_composite"]),
            "RESULT_ORCHESTRATION_LIFT": _fmt(baseline["composite_lift"]),
            "RESULT_WEIGHT_ROBUST": "invariant" if sweep["robust"] else "sensitive",
            "RESULT_WEIGHT_SWEEP_LOW": _fmt(min(weights), 1),
            "RESULT_WEIGHT_SWEEP_HIGH": _fmt(max(weights), 1),
            "RESULT_WEIGHT_WINNER": f"top-k {win_k}, max-evidence {win_e}",
        }
    )

    memory = memory_recall_ablation()
    variables.update(
        {
            "RESULT_MEMORY_RECALL_WINDOWS": str(memory["recalled_windows"]),
            "RESULT_MEMORY_NO_STORE_WINDOWS": str(memory["no_store_windows"]),
        }
    )

    # Scaling and variance: the seeded large dataset with descriptive bootstrap intervals.
    large = large_dataset_eval()
    variables.update(
        {
            "RESULT_LARGE_N": str(large["n"]),
            "RESULT_LARGE_PER_CAT": str(large["per_category"]),
            "RESULT_LARGE_COMPOSITE": _fmt(large["composite_mean"]),
            "RESULT_LARGE_COMPOSITE_CI": f"[{_fmt(large['composite_lo'])}, {_fmt(large['composite_hi'])}]",
            "RESULT_LARGE_ACCURACY": _fmt(large["accuracy_mean"]),
            "RESULT_LARGE_ACCURACY_CI": f"[{_fmt(large['accuracy_lo'])}, {_fmt(large['accuracy_hi'])}]",
        }
    )

    if not _EVAL_RESULTS_PATH.is_file():
        raise FileNotFoundError("run_harness_eval.py must generate output/data/eval_results.json before manuscript hydration")
    bundle = json.loads(_EVAL_RESULTS_PATH.read_text())
    audit = bundle["statistical_scaling"]
    audit_accounting = audit["accounting"]
    audit_contract = audit["analysis_contract"]
    audit_sizes = audit["per_category_values"]
    audit_seeds = audit["seed_values"]
    audit_strata = audit_accounting["strata"]
    audit_unique = audit_accounting["n_unique_examples"]
    audit_methods = audit_accounting["n_method_evaluations"]
    variables.update(
        {
            "RESULT_AUDIT_UNIQUE_N": str(audit_unique),
            "RESULT_AUDIT_METHOD_N": str(audit_methods),
            "RESULT_AUDIT_CONFIDENCE": str(round(float(audit["confidence"]) * 100)),
            "RESULT_AUDIT_FAMILY_SIZE": str(audit["comparison_family"]["size"]),
            "RESULT_AUDIT_DATASET_FINGERPRINT": str(audit["dataset_fingerprint"]),
            "RESULT_AUDIT_SOURCE_FINGERPRINT": str(audit["source_fingerprint"]),
            "RESULT_AUDIT_SIZES": "(" + ", ".join(str(value) for value in audit_sizes) + ")",
            "RESULT_AUDIT_SEED_COUNT": str(len(audit_seeds)),
            "RESULT_AUDIT_CATEGORY_COUNT": str(audit["categories"]),
            "RESULT_AUDIT_STRATA_COUNT": str(len(audit_strata)),
            "RESULT_AUDIT_FAILURES": str(audit_accounting["n_failed"]),
            "RESULT_AUDIT_INTERVAL_LABEL": str(audit_contract["interval_interpretation"]),
            "RESULT_AUDIT_CLUSTER_WARNING": (
                "small-cluster warning applies"
                if audit_contract["small_cluster_warning"]
                else "diagnostic small-cluster threshold not triggered; intervals remain descriptive"
            ),
        }
    )

    # Pre-registered extensions remain separate from the publication-size audit
    # and are read from validated generated aggregates rather than recomputed prose.
    seed_accounting = seed_sensitivity.get("sample_accounting") or {}
    seed_pairs = seed_sensitivity.get("paired_comparisons") or {}
    compiler_rows = compiler_generalization.get("rows") or []
    compiler_summary = compiler_generalization.get("summary") or {}
    if not isinstance(compiler_rows, list) or not compiler_rows:
        raise ValueError("compiler generalization aggregate must contain non-empty rows")
    first_compiler_row = compiler_rows[0]
    if not isinstance(first_compiler_row, dict):
        raise ValueError("compiler generalization rows must be mappings")
    variables.update(
        {
            "RESULT_SEED_SENSITIVITY_SEEDS": str(seed_sensitivity.get("n_seeds", "pending")),
            "RESULT_SEED_SENSITIVITY_UNIQUE_N": str(seed_sensitivity.get("n_unique_examples", "pending")),
            "RESULT_SEED_SENSITIVITY_EVALUATIONS": str(seed_accounting.get("n_evaluated", "pending")),
            "RESULT_SEED_SENSITIVITY_WARNING": (
                "applies" if seed_accounting.get("small_cluster_warning") else "does not apply"
            ),
            "RESULT_SEED_HYBRID_LEXICAL_DELTA": _fmt(
                float(seed_pairs["hybrid_vs_lexical"]["mean_delta"])
            ),
            "RESULT_SEED_HYBRID_LEXICAL_P": _fmt(
                float(seed_pairs["hybrid_vs_lexical"]["p_value"]), 3
            ),
            "RESULT_SEED_HYBRID_SEMANTIC_DELTA": _fmt(
                float(seed_pairs["hybrid_vs_semantic"]["mean_delta"])
            ),
            "RESULT_SEED_HYBRID_SEMANTIC_P": _fmt(
                float(seed_pairs["hybrid_vs_semantic"]["p_value"]), 3
            ),
            "RESULT_COMPILER_SEEDS": str(compiler_generalization.get("n_seeds", "pending")),
            "RESULT_COMPILER_TRAIN_N": str(first_compiler_row.get("n_train", "pending")),
            "RESULT_COMPILER_HOLDOUT_N": str(first_compiler_row.get("n_holdout", "pending")),
            "RESULT_COMPILER_ACCOUNTED_N": str(
                (compiler_generalization.get("sample_accounting") or {}).get("n_evaluated", "pending")
            ),
            "RESULT_COMPILER_CANDIDATE_N": str(
                sum(
                    int(row[method].get("n_candidates", 0))
                    for row in compiler_rows
                    if isinstance(row, dict)
                    for method in ("mipro", "gepa")
                    if isinstance(row.get(method), dict)
                )
            ),
            "RESULT_COMPILER_BASELINE_HOLDOUT": _fmt(float(compiler_summary["baseline"]["mean_holdout_composite"])),
            "RESULT_COMPILER_MIPRO_HOLDOUT": _fmt(float(compiler_summary["mipro"]["mean_holdout_composite"])),
            "RESULT_COMPILER_MIPRO_DELTA": _fmt(float(compiler_summary["mipro"]["mean_holdout_delta"])),
            "RESULT_COMPILER_GEPA_HOLDOUT": _fmt(float(compiler_summary["gepa"]["mean_holdout_composite"])),
            "RESULT_COMPILER_GEPA_DELTA": _fmt(float(compiler_summary["gepa"]["mean_holdout_delta"])),
        }
    )

    # Real LongMemEval_S benchmark (committed aggregates; external data not committed).
    lme = json.loads(_LME_PATH.read_text())
    ci = lambda t: f"[{_fmt(t[1])}, {_fmt(t[2])}]"  # noqa: E731
    def optional_triple(value: object) -> tuple[str, str]:
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            return "not recorded", ""
        return _fmt(value[0]), ci(value)

    lme_reach, lme_reach_ci = optional_triple(lme.get("extractive_session_reachability"))
    variables.update(
        {
            "RESULT_LME_N_EXT": str(lme["n_extractive"]),
            "RESULT_LME_N_NEURAL": str(lme["n_neural"]),
            "RESULT_LME_MODEL": str(lme["neural_model"]),
            "RESULT_LME_BENCHMARK": str((lme.get("sample_accounting") or {}).get("benchmark", "external benchmark")),
            "RESULT_LME_EXT_ACC": _fmt(lme["extractive_accuracy"][0]),
            "RESULT_LME_EXT_ACC_CI": ci(lme["extractive_accuracy"]),
            "RESULT_LME_NEURAL_ACC": _fmt(lme["neural_accuracy"][0]),
            "RESULT_LME_NEURAL_ACC_CI": ci(lme["neural_accuracy"]),
            "RESULT_LME_GROUNDING": _fmt(lme["extractive_grounding"][0]),
            "RESULT_LME_GROUNDING_CI": ci(lme["extractive_grounding"]),
            "RESULT_LME_SESSION_REACHABILITY": lme_reach,
            "RESULT_LME_SESSION_REACHABILITY_CI": lme_reach_ci,
            # Derived neural/extractive accuracy ratio, so the "~Nx" prose tracks the data.
            "RESULT_LME_NEURAL_RATIO": _fmt(lme["neural_accuracy"][0] / lme["extractive_accuracy"][0], 1),
            "RESULT_LME_BENCHMARK_SHA256": str((lme.get("benchmark_provenance") or {}).get("sha256", "pending")),
            "RESULT_LME_BENCHMARK_BYTES": str((lme.get("benchmark_provenance") or {}).get("size_bytes", "pending")),
            "RESULT_LME_MODEL_DIGEST": str((lme.get("neural_model_metadata") or {}).get("digest", "pending")),
            "RESULT_LME_BENCHMARK_STATUS": str((lme.get("sample_accounting") or {}).get("neural", {}).get("status", "unknown")),
        }
    )

    # LongMemEval bottleneck localisation + the max_windows fix (committed aggregates).
    bn = json.loads(_LME_BN_PATH.read_text())
    lo, hi = str(min(bn["sweep_values"])), str(max(bn["sweep_values"]))
    bn_neural = {str(k): v for k, v in bn["neural_by_maxwindows"].items()}
    bn_grnd = {str(k): v for k, v in bn["extractive_grounding_by_maxwindows"].items()}
    bn_accounting = (bn.get("sample_accounting") or {}).get("neural") or {}
    variables.update(
        {
            "RESULT_BN_N": str(bn["n_ranking"]),
            "RESULT_BN_N_NEURAL": str(bn["n_neural"]),
            "RESULT_BN_ACCOUNTING_NEURAL_N": str(bn_accounting.get("n_evaluated", bn["n_neural"])),
            "RESULT_BN_RANKING_RECALL": _fmt(bn["ranking_recall_at_10"], 2),
            "RESULT_BN_INSPECTOR_RECALL": _fmt(bn["inspector_recall"], 2),
            "RESULT_BN_MAXWIN_LO": lo,
            "RESULT_BN_MAXWIN_HI": hi,
            "RESULT_BN_GROUNDING_LO": _fmt(bn_grnd[lo]),
            "RESULT_BN_GROUNDING_HI": _fmt(bn_grnd[hi]),
            "RESULT_BN_MODEL": str(bn["neural_model"]),
            "RESULT_BN_NEURAL_ACC_LO": _fmt(bn_neural[lo]["accuracy"]),
            "RESULT_BN_NEURAL_ACC_HI": _fmt(bn_neural[hi]["accuracy"]),
            "RESULT_BN_ADAPTIVE_ACC": _fmt(bn["neural_adaptive"]["accuracy"]),
            "RESULT_BN_NEURAL_RATIO": _fmt(bn_neural[hi]["accuracy"] / bn_neural[lo]["accuracy"], 1),
        }
    )
    modes = bn["ranking_recall_by_mode"]
    variables["RESULT_BN_RECALL_MODE_N"] = str(modes["n"])
    variables["RESULT_BN_RECALL_LEXICAL"] = _fmt(modes["lexical"], 2)
    if modes.get("available"):
        variables["RESULT_BN_RECALL_DENSE"] = _fmt(modes["dense"], 2)
        variables["RESULT_BN_RECALL_HYBRID"] = _fmt(modes["hybrid"], 2)

    # Context-poisoning resistance (deterministic harness/naive live; neural recorded).
    inj = injection_resistance()
    n_inj = inj["n_probes"]
    injection = json.loads(_INJECTION_EVAL_PATH.read_text()) if _INJECTION_EVAL_PATH.exists() else {}
    neural_poison = injection.get("neural_poison_rate")
    variables.update(
        {
            "RESULT_INJECT_N": str(n_inj),
            "RESULT_INJECT_HARNESS_POISON": f"{round(inj['harness_poison_rate'] * n_inj)} of {n_inj}",
            "RESULT_INJECT_HARNESS_AUDIT": f"{round(inj['harness_audit_rate'] * n_inj)} of {n_inj}",
            "RESULT_INJECT_NAIVE_AUDIT": f"{round(inj['naive_audit_rate'] * n_inj)} of {n_inj}",
            "RESULT_INJECT_NEURAL_POISON": "—" if neural_poison is None else f"{round(neural_poison * n_inj)} of {n_inj}",
        }
    )

    # Real extractive-vs-neural measurement (Gemma via Ollama through real dspy).
    # Binds the §evaluation neural prose to the recorded token-F1 numbers so the
    # claim "a real LM raises accuracy" is measured, not asserted.
    neural = _load_neural_eval()
    variables.update(
        {
            "RESULT_NEURAL_MODEL": str(neural["model"]),
            "RESULT_NEURAL_N": str(neural["n"]),
            "RESULT_EXTRACTIVE_MEAN_F1": _fmt(neural["mean_extractive_f1"]),
            "RESULT_NEURAL_MEAN_F1": _fmt(neural["mean_neural_f1"]),
            "RESULT_EXTRACTIVE_CODE_F1": _fmt(neural["category_extractive_f1"]["code"]),
            "RESULT_NEURAL_CODE_F1": _fmt(neural["category_neural_f1"]["code"]),
            "RESULT_EXTRACTIVE_MULTI_F1": _fmt(neural["category_extractive_f1"]["multi_session"]),
            "RESULT_NEURAL_MULTI_F1": _fmt(neural["category_neural_f1"]["multi_session"]),
            "RESULT_NEURAL_PAIRED_DELTA": _fmt(neural["paired_neural_minus_extractive"]["mean_delta"]),
            "RESULT_NEURAL_PAIRED_CI": (
                f"[{_fmt(neural['paired_neural_minus_extractive']['low'])}, "
                f"{_fmt(neural['paired_neural_minus_extractive']['high'])}]"
            ),
            "RESULT_NEURAL_PAIRED_P": _fmt(neural["paired_neural_minus_extractive"]["p_value"], 3),
            "RESULT_NEURAL_TEMPERATURE": str((neural.get("generation_options") or {}).get("temperature", "pending")),
            "RESULT_NEURAL_MAX_TOKENS": str((neural.get("generation_options") or {}).get("max_tokens", "pending")),
        }
    )

    # OpenRouter/Hy3 neural evaluation (cloud backend, tencent/hy3-preview).
    if _OPENROUTER_EVAL_PATH.exists():
        or_data = json.loads(_OPENROUTER_EVAL_PATH.read_text())
        variables.update(
            {
                "RESULT_OPENROUTER_MODEL": str(or_data["model"]),
                "RESULT_OPENROUTER_N": str(or_data["n_examples"]),
                "RESULT_OPENROUTER_EXT_MEAN_F1": _fmt(or_data["extractive"]["mean_f1"]),
                "RESULT_OPENROUTER_NEURAL_MEAN_F1": _fmt(or_data["neural"]["mean_f1"]),
                "RESULT_OPENROUTER_EXT_PASS": str(or_data["extractive"]["pass_count"]),
                "RESULT_OPENROUTER_NEURAL_PASS": str(or_data["neural"]["pass_count"]),
                "RESULT_OPENROUTER_LIFT_F1": _fmt(or_data["lift"]["mean_f1_delta"]),
                "RESULT_OPENROUTER_LIFT_PASS": f"{or_data['lift']['pass_delta']:+d}",
                "RESULT_OPENROUTER_TEMPERATURE": str(or_data["temperature"]),
                "RESULT_OPENROUTER_MAX_TOKENS": str(or_data["max_tokens"]),
                "RESULT_OPENROUTER_RUST_EXT_F1": _fmt(or_data["extractive"]["examples"][1]["f1"]),
                "RESULT_OPENROUTER_RUST_NEURAL_F1": _fmt(or_data["neural"]["examples"][1]["f1"]),
                "RESULT_OPENROUTER_BUDGET_EXT_F1": _fmt(or_data["extractive"]["examples"][3]["f1"]),
                "RESULT_OPENROUTER_BUDGET_NEURAL_F1": _fmt(or_data["neural"]["examples"][3]["f1"]),
                "RESULT_OPENROUTER_MULTIHOP_EXT_F1": _fmt(or_data["extractive"]["examples"][2]["f1"]),
                "RESULT_OPENROUTER_MULTIHOP_NEURAL_F1": _fmt(or_data["neural"]["examples"][2]["f1"]),
            }
        )

    # Real surrogate-vs-learned semantic-lane measurement (paraphrase recall@1).
    learned = _load_learned_eval()
    variables.update(
        {
            "RESULT_EMBED_MODEL": str(learned["model"]),
            "RESULT_NUM_PROBES": str(learned["n_probes"]),
            "RESULT_SURROGATE_RECALL": _fmt(learned["surrogate_recall_at_1"], 2),
            "RESULT_LEARNED_RECALL": _fmt(learned["learned_recall_at_1"], 2),
            "RESULT_SURROGATE_RECALL_CI": (
                f"[{_fmt(learned['surrogate_recall_ci'][1], 2)}, {_fmt(learned['surrogate_recall_ci'][2], 2)}]"
            ),
            "RESULT_LEARNED_RECALL_CI": (
                f"[{_fmt(learned['learned_recall_ci'][1], 2)}, {_fmt(learned['learned_recall_ci'][2], 2)}]"
            ),
            "RESULT_EMBED_PAIRED_P": _fmt(learned["paired_binary_comparison"]["p_value"], 3),
            "RESULT_EMBED_MODEL_DIGEST": str((learned.get("model_metadata") or {}).get("digest", "pending")),
            "RESULT_EMBED_QUERY_PREFIX": str(learned.get("embedding_query_prefix", "pending")),
            "RESULT_EMBED_DOCUMENT_PREFIX": str(learned.get("embedding_document_prefix", "pending")),
        }
    )
    return variables


__all__ = ["generate_variables"]
