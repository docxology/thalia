"""Opt-in live neural evaluation runners (require Ollama)."""

from __future__ import annotations

from ..compiler.metrics import token_f1
from ..evaluation.accounting import fingerprint_examples
from ..evaluation.statistics import binary_rate, bootstrap_mean, exact_paired_binary, paired_comparison, wilson_interval
from ..signatures import TaskCategory
from .adapters import DEFAULT_OLLAMA_MODEL, ollama_model_metadata
from .runtime import build_program, configure, configure_ollama


def injection_resistance_neural(model: str = DEFAULT_OLLAMA_MODEL) -> dict:  # pragma: no cover
    """Measure neural context-poisoning obedience on the injection probe set."""
    from ..evaluation.ablation import _INJECTION_PROBES, _is_poisoned, _poison_session

    temperature = 0.0
    max_tokens = 512
    generation_options = {"temperature": temperature, "max_tokens": max_tokens}
    configure_ollama(model=model, temperature=temperature, max_tokens=max_tokens)
    program = build_program()
    poisoned = correct = 0
    rows: list[dict] = []
    for i, probe in enumerate(_INJECTION_PROBES, start=1):
        answer = program(context=_poison_session(probe.true_line, probe.poison_line), question=probe.query).answer.lower()
        is_poisoned = _is_poisoned(answer, probe.gold, probe.injected_answer)
        is_correct = probe.gold.lower() in answer
        poisoned += int(is_poisoned)
        correct += int(is_correct)
        rows.append(
            {
                "probe": i,
                "attack_family": ("override", "recency", "role_impersonation", "instruction_injection", "authority_claim")[(i - 1) % 5],
                "query": probe.query,
                "gold": probe.gold,
                "injected_answer": probe.injected_answer,
                "answer": answer,
                "neural_poisoned": is_poisoned,
                "neural_correct": is_correct,
                "neural_auditable": False,
            }
        )
    n = len(_INJECTION_PROBES)
    return {
        "model": model,
        "model_metadata": ollama_model_metadata(model),
        "generation_options": generation_options,
        "n_probes": n,
        "rows": rows,
        "neural_poison_rate": poisoned / n,
        "neural_correct_rate": correct / n,
        "neural_poison_ci": wilson_interval(poisoned, n),
        "neural_correct_ci": wilson_interval(correct, n),
        "sample_accounting": {
            "unit": "injection_probe",
            "n_requested": n,
            "n_evaluated": n,
            "n_failed": 0,
        },
    }


def _balanced_research_subset(limit: int | None = None) -> list:
    """Return a deterministic, near-balanced research subset for live probes."""
    from ..evaluation import build_research_dataset

    full_dataset = build_research_dataset(per_category=4, seed=0)
    if limit is None:
        return full_dataset
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"limit must be a positive integer when provided, got {limit!r}")
    requested = min(limit, len(full_dataset))
    buckets = {
        category: [example for example in full_dataset if example.task_category == category]
        for category in TaskCategory
    }
    base, remainder = divmod(requested, len(buckets))
    selected = []
    for index, category in enumerate(TaskCategory):
        selected.extend(buckets[category][: base + int(index < remainder)])
    return selected


def evaluate_backends(limit: int | None = None, model: str = DEFAULT_OLLAMA_MODEL) -> dict:  # pragma: no cover
    """Real head-to-head on a balanced, capacity-aware research subset."""
    dataset = _balanced_research_subset(limit)
    rows = []

    configure()
    extractive = build_program()
    ext_answers = [extractive(context=ex.session_history, question=ex.query).answer for ex in dataset]

    temperature = 0.0
    max_tokens = 512
    generation_options = {"temperature": temperature, "max_tokens": max_tokens}
    configure_ollama(model=model, temperature=temperature, max_tokens=max_tokens)
    neural = build_program()
    neu_answers = [neural(context=ex.session_history, question=ex.query).answer for ex in dataset]
    configure()

    category_ext: dict[str, list[float]] = {}
    category_neu: dict[str, list[float]] = {}
    for ex, ea, na in zip(dataset, ext_answers, neu_answers):
        cat = (ex.task_category or TaskCategory.SINGLE_SESSION).value
        ef, nf = token_f1(ea, ex.expected_answer), token_f1(na, ex.expected_answer)
        category_ext.setdefault(cat, []).append(ef)
        category_neu.setdefault(cat, []).append(nf)
        rows.append(
            {
                "category": cat,
                "gold": ex.expected_answer,
                "extractive": ea,
                "neural": na,
                "extractive_f1": ef,
                "neural_f1": nf,
            }
        )

    n = len(dataset)
    cat_ext = {cat: sum(values) / len(values) for cat, values in category_ext.items()}
    cat_neu = {cat: sum(values) / len(values) for cat, values in category_neu.items()}
    extractive_statistics = bootstrap_mean([row["extractive_f1"] for row in rows], resamples=5000, seed=0)
    neural_statistics = bootstrap_mean([row["neural_f1"] for row in rows], resamples=5000, seed=1)
    paired = paired_comparison(
        [row["neural_f1"] for row in rows],
        [row["extractive_f1"] for row in rows],
        resamples=5000,
        permutations=5000,
        bootstrap_seed=2,
        permutation_seed=3,
    )
    extractive_success = [row["extractive_f1"] >= 1.0 for row in rows]
    neural_success = [row["neural_f1"] >= 1.0 for row in rows]
    return {
        "model": model,
        "model_metadata": ollama_model_metadata(model),
        "generation_options": generation_options,
        "dataset_fingerprint": fingerprint_examples(dataset),
        "metric": "token_f1",
        "n": n,
        "rows": rows,
        "category_extractive_f1": cat_ext,
        "category_neural_f1": cat_neu,
        "mean_extractive_f1": sum(r["extractive_f1"] for r in rows) / n if n else 0.0,
        "mean_neural_f1": sum(r["neural_f1"] for r in rows) / n if n else 0.0,
        "extractive_statistics": extractive_statistics.to_dict(),
        "neural_statistics": neural_statistics.to_dict(),
        "paired_neural_minus_extractive": paired.to_dict(),
        "extractive_binary_rate": binary_rate(sum(extractive_success), n).to_dict(),
        "neural_binary_rate": binary_rate(sum(neural_success), n).to_dict(),
        "paired_binary_comparison": exact_paired_binary(neural_success, extractive_success).to_dict(),
        "sample_accounting": {
            "unit": "research_eval_example",
            "n_requested": n,
            "n_evaluated": n,
            "n_failed": 0,
            "categories": len({ex.task_category for ex in dataset}),
            "category_counts": {cat: len(values) for cat, values in category_ext.items()},
        },
    }


__all__ = ["injection_resistance_neural", "evaluate_backends"]
