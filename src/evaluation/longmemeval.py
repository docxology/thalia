"""Loader for the LongMemEval_S benchmark (real, external, long-context data).

LongMemEval (Wu et al., 2025) is the real long-term-memory benchmark the synthetic
dataset only approximates: ~500 questions over ~40-session, ~115k-token haystacks.
This adapter maps it onto the project's :class:`EvalExample` contract so every
existing stage, metric, and experiment runs over it unchanged.

The data is external (not committed; download via ``scripts/get_longmemeval.sh`` or
the HuggingFace ``xiaowu0162/longmemeval-cleaned`` repo), so results over it are
reproducible from *code + the downloaded benchmark*, not code alone — an honest
relaxation of the self-contained determinism thesis, disclosed in the manuscript.

Grounding is **session-level**: ``expected_source_indices`` is set to every line that
belongs to an evidence session (``answer_session_ids``), so the existing grounding
metric measures "did the citation come from the right session?" with no metric change.
Because any line of the gold session counts, this is an *upper bound* on stricter
line-level grounding — read it as "retrieval reached the right session", not the line.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..compiler.metrics import EvalExample
from ..signatures import TaskCategory

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "longmemeval" / "longmemeval_s.json"

# LongMemEval question types -> the project's task categories (no CODE in the benchmark).
_TYPE_MAP = {
    "single-session-user": TaskCategory.SINGLE_SESSION,
    "single-session-assistant": TaskCategory.SINGLE_SESSION,
    "single-session-preference": TaskCategory.PREFERENCE,
    "temporal-reasoning": TaskCategory.TEMPORAL,
    "knowledge-update": TaskCategory.KNOWLEDGE_UPDATE,
    "multi-session": TaskCategory.MULTI_SESSION,
}


def longmemeval_available(path: str | Path = DEFAULT_PATH) -> bool:
    """True when the LongMemEval_S file has been downloaded."""
    return Path(path).exists()


def _item_to_example(item: dict) -> EvalExample:
    lines: list[str] = []
    line_session: list[str] = []
    for sid, session in zip(item["haystack_session_ids"], item["haystack_sessions"]):
        for turn in session:
            role = str(turn.get("role", "user")).capitalize()
            content = str(turn.get("content", "")).replace("\n", " ").strip()
            lines.append(f"{role}: {content}")
            line_session.append(sid)
    answer_sessions = set(item.get("answer_session_ids", []))
    evidence = tuple(i for i, sid in enumerate(line_session) if sid in answer_sessions)
    return EvalExample(
        session_history="\n".join(lines),
        query=str(item["question"]),
        expected_answer=str(item["answer"]),
        expected_source_indices=evidence,
        task_category=_TYPE_MAP[item["question_type"]],
    )


def load_longmemeval(path: str | Path = DEFAULT_PATH, limit: int | None = None) -> list[EvalExample]:
    """Load LongMemEval_S as ``EvalExample``s (session-level grounding indices).

    Raises a clear error when the benchmark is not downloaded.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download LongMemEval_S first:\n"
            "  bash scripts/get_longmemeval.sh   (or wget the file from "
            "huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)"
        )
    data = json.loads(path.read_text())
    if limit is not None:
        data = data[:limit]
    return [_item_to_example(item) for item in data]


def longmemeval_eval(extractive_limit: int | None = None, neural_limit: int = 50, neural_model: str = "gemma3:4b") -> dict:  # pragma: no cover - requires the downloaded benchmark
    """Run the harness over real LongMemEval_S and aggregate the metrics.

    Extractive backend over ``extractive_limit`` examples (fast), and the neural
    backend (real LM in the Reasoner, Inspector windows first) over ``neural_limit``
    examples (slow). Returns accuracy, session-level grounding, and composite means
    with bootstrap CIs — the real-data counterpart to the synthetic headline.
    """
    from ..compiler.metrics import answer_score, grounding_score, harness_metric
    from ..config import default_config
    from ..harness import AutoHarness, build_run_fn
    from ..llm import OllamaLM
    from ..dspy_runtime import ollama_model_metadata
    from .scaling import bootstrap_ci

    full = load_longmemeval(limit=extractive_limit)
    run = build_run_fn(default_config())
    ext_acc, ext_grnd, ext_comp = [], [], []
    cat_acc: dict[str, list[float]] = {}
    for ex in full:
        out = run(ex)
        a = answer_score(out, ex)
        ext_acc.append(a)
        ext_grnd.append(grounding_score(out, ex))
        ext_comp.append(harness_metric(out, ex))
        cat_acc.setdefault(ex.task_category.name.lower(), []).append(a)

    neural = load_longmemeval(limit=neural_limit)
    nlm = OllamaLM(model=neural_model)
    nh = AutoHarness(config=default_config(), lm=nlm)
    neu_acc, neu_grnd = [], []
    for ex in neural:
        out = nh.forward(ex.query, ex.session_history)
        neu_acc.append(answer_score(out, ex))
        neu_grnd.append(grounding_score(out, ex))

    ea_m, ea_lo, ea_hi = bootstrap_ci(ext_acc)
    eg_m, eg_lo, eg_hi = bootstrap_ci(ext_grnd)
    na_m, na_lo, na_hi = bootstrap_ci(neu_acc)
    ng_m, ng_lo, ng_hi = bootstrap_ci(neu_grnd)
    return {
        "n_extractive": len(full),
        "n_neural": len(neural),
        "neural_model": neural_model,
        "neural_model_metadata": ollama_model_metadata(neural_model),
        "neural_generation_options": {"temperature": 0.0},
        "extractive_accuracy": (ea_m, ea_lo, ea_hi),
        "extractive_grounding": (eg_m, eg_lo, eg_hi),
        "extractive_composite": bootstrap_ci(ext_comp),
        "neural_accuracy": (na_m, na_lo, na_hi),
        "neural_grounding": (ng_m, ng_lo, ng_hi),
        "category_accuracy": {c: bootstrap_ci(v) for c, v in cat_acc.items()},
    }


def _gold_lines(example) -> set:
    return set(example.expected_source_indices)


def _rrf_rank(rankings: list[list[int]], k0: int = 60) -> list[int]:
    """Reciprocal-rank fusion of several full line-index rankings."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k0 + rank)
    return sorted(scores, key=lambda i: -scores[i])


def _ranking_recall_by_mode(examples: list, neural_model: str, k: int = 10) -> dict:  # pragma: no cover - requires the embedder
    """hit@k of the gold evidence session under lexical / dense / hybrid full-haystack ranking.

    Tests the claim that retrieval *ranking* is not the bottleneck: every mode recovers
    the evidence, so they tie. Dense/hybrid need the embedder; returns ``available: False``
    (lexical only) when it is absent so the recorder still writes a usable aggregate.
    """
    from ..retrieval.learned import LearnedSemanticIndex, embed_model_available
    from ..retrieval.lexical import BM25Index

    probe = [e for e in examples if _gold_lines(e)]
    if not probe:
        return {"available": False, "n": 0}
    have_embed = embed_model_available(model=neural_model)
    lex_hits = dense_hits = hyb_hits = 0
    embed_error: str | None = None
    for ex in probe:
        gold = _gold_lines(ex)
        lines = [ln for ln in ex.session_history.split("\n") if ln.strip()]
        lex_full = [i for i, _ in BM25Index(lines).top_k(ex.query, k=len(lines))]
        lex_hits += 1 if set(lex_full[:k]) & gold else 0
        if have_embed:
            try:
                index = LearnedSemanticIndex(lines, model=neural_model)
                dense_full = [i for i, _ in index.top_k(ex.query, k=len(lines))]
                dense_hits += 1 if set(dense_full[:k]) & gold else 0
                hyb = _rrf_rank([lex_full, dense_full])
                hyb_hits += 1 if set(hyb[:k]) & gold else 0
            except Exception as exc:  # pragma: no cover - depends on local Ollama state
                have_embed = False
                embed_error = f"{type(exc).__name__}: {exc}"
    n = len(probe)
    out = {"available": have_embed, "n": n, "k": k, "lexical": lex_hits / n}
    if have_embed:
        out["dense"] = dense_hits / n
        out["hybrid"] = hyb_hits / n
    elif embed_error:
        out["embed_error"] = embed_error
    return out


def bottleneck_analysis(ranking_limit: int = 40, sweep_values=(15, 30, 50, 100), neural_limit: int = 30, neural_model: str = "gemma3:4b", recall_modes_limit: int = 8, embed_model_for_modes: str = "nomic-embed-text") -> dict:  # pragma: no cover - requires the benchmark (+ ollama for neural rows)
    """Localise the LongMemEval bottleneck and measure the fix.

    (1) Ranking recall vs Inspector recall — shows retrieval *ranking* is not the
    bottleneck (the full-haystack ranking recovers the evidence), the Inspector's
    context-narrowing is. (2) An extractive ``max_windows`` sweep — grounding climbs as
    narrowing relaxes, but accuracy stays LM-bound. (3) The neural composition — a wider
    Inspector *plus* a real Reasoner converts recovered recall into accuracy.
    """
    from ..compiler.metrics import answer_score, grounding_score
    from ..config import default_config
    from ..harness import AutoHarness, build_run_fn
    from ..llm import OllamaLM
    from ..dspy_runtime import ollama_model_metadata
    from ..retrieval.learned import embed_model_metadata
    from ..retrieval.lexical import BM25Index
    from ..stages.inspector import Inspector

    examples = [e for e in load_longmemeval(limit=ranking_limit) if _gold_lines(e)]
    cfg = default_config()
    inspector = Inspector(max_windows=cfg.max_windows, partition_threshold=cfg.partition_threshold, partition_size=cfg.partition_size)
    rank_hits = insp_hits = 0
    for ex in examples:
        gold = _gold_lines(ex)
        lines = [ln for ln in ex.session_history.split("\n") if ln.strip()]
        ranked = {i for i, _ in BM25Index(lines).top_k(ex.query, k=10)}
        rank_hits += 1 if ranked & gold else 0
        windows = {w.source_index for w in inspector(session_history=ex.session_history, query=ex.query)["evidence_windows"]}
        insp_hits += 1 if windows & gold else 0
    n_rank = len(examples)

    # Three-way ranking recall (lexical / dense / hybrid) on a small subset, so the
    # "ranking is not the bottleneck — every mode recovers the evidence" claim is
    # measured rather than asserted. Dense needs the embedder; recorded when available.
    ranking_modes = _ranking_recall_by_mode(examples[:recall_modes_limit], neural_model=embed_model_for_modes)

    sweep_examples = [e for e in load_longmemeval(limit=60) if _gold_lines(e)]
    extractive_sweep = {}
    for mw in sweep_values:
        run = build_run_fn(cfg.with_(max_windows=mw))
        grs = [grounding_score(run(e), e) for e in sweep_examples]
        extractive_sweep[mw] = sum(grs) / len(grs)

    neural_examples = [e for e in load_longmemeval(limit=neural_limit) if _gold_lines(e)]
    lm = OllamaLM(model=neural_model)

    def _neural_run(config):
        harness = AutoHarness(config=config, lm=lm)
        accs, grs = [], []
        for ex in neural_examples:
            out = harness.forward(ex.query, ex.session_history)
            accs.append(answer_score(out, ex))
            grs.append(grounding_score(out, ex))
        return {"accuracy": sum(accs) / len(accs), "grounding": sum(grs) / len(grs)}

    neural = {mw: _neural_run(cfg.with_(max_windows=mw)) for mw in (min(sweep_values), max(sweep_values))}
    # The shipped fix: the adaptive Inspector recovers accuracy with no manual tuning.
    neural_adaptive = _neural_run(cfg.with_(adaptive_windows=True))

    return {
        "n_ranking": n_rank,
        "ranking_recall_at_10": rank_hits / n_rank,
        "ranking_recall_by_mode": ranking_modes,
        "inspector_recall": insp_hits / n_rank,
        "default_max_windows": cfg.max_windows,
        "sweep_values": list(sweep_values),
        "extractive_grounding_by_maxwindows": extractive_sweep,
        "n_neural": len(neural_examples),
        "neural_model": neural_model,
        "neural_model_metadata": ollama_model_metadata(neural_model),
        "neural_generation_options": {"temperature": 0.0},
        "embed_model_for_modes": embed_model_for_modes,
        "embed_model_metadata": embed_model_metadata(embed_model_for_modes),
        "neural_by_maxwindows": neural,
        "neural_adaptive": neural_adaptive,
    }


__all__ = ["load_longmemeval", "longmemeval_available", "longmemeval_eval", "bottleneck_analysis", "DEFAULT_PATH"]
