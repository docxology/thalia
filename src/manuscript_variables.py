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
from .config import HarnessConfig, default_config
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
from .harness import build_run_fn

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_NEURAL_EVAL_PATH = _DATA_DIR / "neural_eval.json"
_LEARNED_EVAL_PATH = _DATA_DIR / "learned_retrieval.json"
_INJECTION_EVAL_PATH = _DATA_DIR / "injection_eval.json"
_LME_PATH = _DATA_DIR / "longmemeval_results.json"
_LME_BN_PATH = _DATA_DIR / "longmemeval_bottleneck.json"
_OPENROUTER_EVAL_PATH = _DATA_DIR / "openrouter_eval.json"


def _fmt(value: float, places: int = 3) -> str:
    """Format a float to a fixed number of decimal places."""
    return f"{value:.{places}f}"


def _coverage_gate() -> int:
    """Read the enforced ``src/`` coverage gate from pyproject.toml (no hard-coding)."""
    try:
        import tomllib  # Python >= 3.11
    except ModuleNotFoundError:  # pragma: no cover - exercised only on 3.10
        import tomli as tomllib  # type: ignore[no-redef]

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
    results = run_full_eval(config)
    comparison = results["retriever_comparison"]

    # Noise-regime endpoint: at the highest distractor level the lexical and the
    # hashing-surrogate "semantic" lanes diverge. Exposing these as tokens binds
    # the §evaluation noise prose to the measured numbers (it cannot drift).
    noise = noise_scaling_experiment()
    noise_max_level = noise["lexical"][-1][0]
    noise_lexical = noise["lexical"][-1][1]
    noise_semantic = noise["semantic"][-1][1]

    dataset = build_demo_dataset()
    compiled = MIPROCompiler(auto="heavy").compile(lambda cfg: build_run_fn(cfg), dataset)

    variables: dict[str, str] = {
        # Configuration
        "CONFIG_TOP_K": str(config.top_k),
        "CONFIG_MAX_WINDOWS": str(config.max_windows),
        "CONFIG_MAX_EVIDENCE": str(config.max_evidence),
        "CONFIG_RRF_K": str(config.rrf_k),
        "CONFIG_CONTEXT_BUDGET": str(config.context_budget_tokens),
        "CONFIG_NUM_STAGES": "5",
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
        "CONFIG_CI_LEVEL": "95",
        "CONFIG_BACKEND_FIGURE_WIDTH": "75",
        "CONFIG_COV_GATE": str(_coverage_gate()),
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

    # Scaling and variance: the seeded large dataset with bootstrap CIs.
    large = large_dataset_eval()
    variables.update(
        {
            "RESULT_LARGE_N": str(large["n"]),
            "RESULT_LARGE_PER_CAT": str(large["per_category"]),
            "RESULT_LARGE_COMPOSITE": _fmt(large["composite_mean"]),
            "RESULT_LARGE_COMPOSITE_CI": f"[{_fmt(large['composite_lo'])}, {_fmt(large['composite_hi'])}]",
        }
    )

    # Real LongMemEval_S benchmark (committed aggregates; external data not committed).
    lme = json.loads(_LME_PATH.read_text())
    ci = lambda t: f"[{_fmt(t[1])}, {_fmt(t[2])}]"  # noqa: E731
    variables.update(
        {
            "RESULT_LME_N_EXT": str(lme["n_extractive"]),
            "RESULT_LME_N_NEURAL": str(lme["n_neural"]),
            "RESULT_LME_MODEL": str(lme["neural_model"]),
            "RESULT_LME_EXT_ACC": _fmt(lme["extractive_accuracy"][0]),
            "RESULT_LME_EXT_ACC_CI": ci(lme["extractive_accuracy"]),
            "RESULT_LME_NEURAL_ACC": _fmt(lme["neural_accuracy"][0]),
            "RESULT_LME_NEURAL_ACC_CI": ci(lme["neural_accuracy"]),
            "RESULT_LME_GROUNDING": _fmt(lme["extractive_grounding"][0]),
            "RESULT_LME_GROUNDING_CI": ci(lme["extractive_grounding"]),
            # Derived neural/extractive accuracy ratio, so the "~Nx" prose tracks the data.
            "RESULT_LME_NEURAL_RATIO": _fmt(lme["neural_accuracy"][0] / lme["extractive_accuracy"][0], 1),
        }
    )

    # LongMemEval bottleneck localisation + the max_windows fix (committed aggregates).
    bn = json.loads(_LME_BN_PATH.read_text())
    lo, hi = str(min(bn["sweep_values"])), str(max(bn["sweep_values"]))
    bn_neural = {str(k): v for k, v in bn["neural_by_maxwindows"].items()}
    bn_grnd = {str(k): v for k, v in bn["extractive_grounding_by_maxwindows"].items()}
    variables.update(
        {
            "RESULT_BN_N": str(bn["n_ranking"]),
            "RESULT_BN_N_NEURAL": str(bn["n_neural"]),
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
        }
    )
    # Optional learned-embedder per-mode probe. Older committed bottleneck
    # aggregates only carry the full-haystack ranking recall; keep that truthful
    # instead of raising or fabricating dense/hybrid rows when the local embedder
    # is unavailable.
    modes = bn.get("ranking_recall_by_mode") or {}
    variables["RESULT_BN_RECALL_MODE_N"] = str(modes.get("n", bn["n_ranking"]))
    variables["RESULT_BN_RECALL_LEXICAL"] = _fmt(modes.get("lexical", bn["ranking_recall_at_10"]), 2)
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
        }
    )
    return variables


__all__ = ["generate_variables"]
