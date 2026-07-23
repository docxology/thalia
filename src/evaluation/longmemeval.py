"""Loader for the LongMemEval_S benchmark (real, external, long-context data).

LongMemEval (Wu et al., 2025) is the real long-term-memory benchmark the synthetic
dataset only approximates: hundreds of questions over long multi-session haystacks.
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
import math
from pathlib import Path
from typing import Any, Mapping

from ..compiler.metrics import EvalExample
from ..signatures import TaskCategory
from .accounting import file_provenance, runtime_provenance

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


_REQUIRED_FIELDS = {
    "question_id",
    "question_type",
    "question_date",
    "question",
    "answer",
    "answer_session_ids",
    "haystack_dates",
    "haystack_sessions",
    "haystack_session_ids",
}


def validate_longmemeval_payload(payload: object) -> list[dict]:
    """Validate every benchmark record and its aligned session/turn arrays."""
    if not isinstance(payload, list) or not payload:
        raise ValueError("LongMemEval_S must contain a non-empty JSON list")
    seen_question_ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"LongMemEval record {index} must be an object")
        missing = sorted(_REQUIRED_FIELDS - set(item))
        if missing:
            raise ValueError(f"LongMemEval record {index} missing fields: {', '.join(missing)}")
        question_id = item["question_id"]
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"LongMemEval record {index} question_id must be non-empty text")
        if question_id in seen_question_ids:
            raise ValueError(f"LongMemEval record {index} duplicates question_id {question_id!r}")
        seen_question_ids.add(question_id)
        if not isinstance(item["question_type"], str) or item["question_type"] not in _TYPE_MAP:
            raise ValueError(f"LongMemEval record {index} has unknown question_type")
        if not isinstance(item["question_date"], str) or not item["question_date"].strip():
            raise ValueError(f"LongMemEval record {index} question_date must be non-empty text")
        if not isinstance(item["question"], str) or not item["question"].strip():
            raise ValueError(f"LongMemEval record {index} question must be non-empty text")
        if not isinstance(item["answer"], (str, int, float, bool)):
            raise ValueError(f"LongMemEval record {index} answer must be scalar text/number")
        if isinstance(item["answer"], float) and not math.isfinite(item["answer"]):
            raise ValueError(f"LongMemEval record {index} answer must be finite")
        sessions = item["haystack_sessions"]
        session_ids = item["haystack_session_ids"]
        dates = item["haystack_dates"]
        if (
            not isinstance(sessions, list)
            or not isinstance(session_ids, list)
            or not isinstance(dates, list)
            or len(sessions) != len(session_ids)
            or len(sessions) != len(dates)
        ):
            raise ValueError(f"LongMemEval record {index} has unaligned haystack session arrays")
        if not isinstance(item["answer_session_ids"], list):
            raise ValueError(f"LongMemEval record {index} answer_session_ids must be a list")
        if any(not isinstance(value, str) or not value.strip() for value in session_ids):
            raise ValueError(f"LongMemEval record {index} haystack_session_ids must be non-empty text")
        if any(not isinstance(value, str) or not value.strip() for value in dates):
            raise ValueError(f"LongMemEval record {index} haystack_dates must be non-empty text")
        if any(not isinstance(value, str) or not value.strip() for value in item["answer_session_ids"]):
            raise ValueError(f"LongMemEval record {index} answer_session_ids must be non-empty text")
        if not set(item["answer_session_ids"]).issubset(set(session_ids)):
            raise ValueError(f"LongMemEval record {index} answer_session_ids reference unknown sessions")
        for session_index, session in enumerate(sessions):
            if not isinstance(session, list):
                raise ValueError(f"LongMemEval record {index} session {session_index} must be a list")
            for turn_index, turn in enumerate(session):
                if not isinstance(turn, dict) or not isinstance(turn.get("content"), str):
                    raise ValueError(f"LongMemEval record {index} turn {session_index}/{turn_index} is invalid")
    return payload


def longmemeval_available(path: str | Path = DEFAULT_PATH) -> bool:
    """True only when the complete local JSON payload passes structural validation."""
    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        return False
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    try:
        validate_longmemeval_payload(payload)
    except ValueError:
        return False
    return True


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
    # Use from_str so the mapping is robust to unexpected question types
    # (defaults to SINGLE_SESSION rather than raising).
    raw_type = str(item["question_type"])
    task_category = TaskCategory.from_str(_TYPE_MAP.get(raw_type, TaskCategory.SINGLE_SESSION).value)
    return EvalExample(
        session_history="\n".join(lines),
        query=str(item["question"]),
        expected_answer=str(item["answer"]),
        expected_source_indices=evidence,
        task_category=task_category,
        example_id=str(item.get("question_id", "")),
        stratum=raw_type,
    )


def load_longmemeval(path: str | Path = DEFAULT_PATH, limit: int | None = None) -> list[EvalExample]:
    """Load LongMemEval_S as ``EvalExample``s (session-level grounding indices).

    Raises a clear error when the benchmark is not downloaded.
    """
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0):
        raise ValueError(f"limit must be a positive integer, got {limit!r}")
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download LongMemEval_S first:\n"
            "  bash scripts/get_longmemeval.sh   (or wget the file from "
            "huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON; the download may be partial") from exc
    validate_longmemeval_payload(data)
    if limit is not None:
        data = data[:limit]
    return [_item_to_example(item) for item in data]


def _load_neural_checkpoint(
    checkpoint: Path,
    *,
    benchmark: dict[str, object],
    model: str,
    generation_options: Mapping[str, object],
    requested_ids: set[str],
) -> dict[str, dict]:
    """Load only valid checkpoint rows matching this benchmark/model/run scope."""
    try:
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if not isinstance(saved, dict):
            return {}
        rows = saved.get("rows")
        if (
            saved.get("benchmark_sha256") != benchmark["sha256"]
            or saved.get("model") != model
            or saved.get("generation_options") != dict(generation_options)
            or saved.get("benchmark_size_bytes") not in (None, benchmark["size_bytes"])
            or not isinstance(rows, list)
        ):
            return {}
        candidate_rows: dict[str, dict] = {}
        for row in rows:
            if not isinstance(row, dict):
                return {}
            example_id = row.get("example_id")
            accuracy = row.get("accuracy")
            grounding = row.get("grounding")
            if (
                not isinstance(example_id, str)
                or not example_id
                or example_id in candidate_rows
                or not isinstance(accuracy, (int, float))
                or not isinstance(grounding, (int, float))
                or not math.isfinite(float(accuracy))
                or not math.isfinite(float(grounding))
                or not 0.0 <= float(accuracy) <= 1.0
                or not 0.0 <= float(grounding) <= 1.0
            ):
                return {}
            candidate_rows[example_id] = row
        return {key: row for key, row in candidate_rows.items() if key in requested_ids}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _write_neural_checkpoint(
    checkpoint: Path,
    rows: Mapping[str, dict],
    *,
    benchmark: dict[str, object],
    model: str,
    generation_options: dict[str, object],
) -> None:
    """Atomically persist a resumable neural checkpoint."""
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "schema_version": 2,
            "benchmark_sha256": benchmark["sha256"],
            "benchmark_size_bytes": benchmark["size_bytes"],
            "model": model,
            "generation_options": generation_options,
            "rows": sorted(rows.values(), key=lambda row: str(row["example_id"])),
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary = checkpoint.with_name(f".{checkpoint.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(checkpoint)


def longmemeval_eval(
    extractive_limit: int | None = None,
    neural_limit: int = 50,
    neural_model: str = "gemma3:4b",
    checkpoint_path: str | Path | None = None,
) -> dict:  # pragma: no cover - requires the downloaded benchmark
    """Run the harness over real LongMemEval_S and aggregate the metrics.

    Extractive backend over ``extractive_limit`` examples (fast), and the neural
    backend (real LM in the Reasoner, Inspector windows first) over ``neural_limit``
    examples (slow). Returns accuracy, session-level grounding, and composite means
    with bootstrap CIs — the real-data counterpart to the synthetic headline.
    """
    if extractive_limit is not None and (isinstance(extractive_limit, bool) or extractive_limit <= 0):
        raise ValueError(f"extractive_limit must be positive when provided, got {extractive_limit!r}")
    if isinstance(neural_limit, bool) or neural_limit <= 0:
        raise ValueError(f"neural_limit must be positive, got {neural_limit!r}")
    from ..compiler.metrics import answer_score, grounding_score, harness_metric
    from ..config import default_config
    from ..harness import AutoHarness, build_run_fn
    from ..llm import OllamaLM
    from ..dspy_runtime import ollama_model_metadata
    from .scaling import bootstrap_ci
    from .statistics import binary_rate, bootstrap_mean

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
        category = ex.task_category or TaskCategory.SINGLE_SESSION
        cat_acc.setdefault(category.name.lower(), []).append(a)

    neural = load_longmemeval(limit=neural_limit)
    # LongMemEval prompts can contain much larger haystacks than the demo set;
    # allow a slow local model to finish without weakening the normal adapter
    # timeout used by interactive queries.
    nlm = OllamaLM(model=neural_model, timeout=120.0)
    neu_acc, neu_grnd = [], []
    checkpoint = Path(checkpoint_path) if checkpoint_path else None
    benchmark_meta = file_provenance(DEFAULT_PATH)
    requested_ids = {example.example_id for example in neural}
    generation_options: dict[str, object] = {"temperature": 0.0}
    checkpoint_rows = (
        _load_neural_checkpoint(
            checkpoint,
            benchmark=benchmark_meta,
            model=neural_model,
            generation_options=generation_options,
            requested_ids=requested_ids,
        )
        if checkpoint and checkpoint.exists()
        else {}
    )
    with AutoHarness(config=default_config(), lm=nlm) as nh:
        for ex in neural:
            if ex.example_id in checkpoint_rows:
                row = checkpoint_rows[ex.example_id]
                neu_acc.append(float(row["accuracy"]))
                neu_grnd.append(float(row["grounding"]))
                continue
            out = nh.forward(ex.query, ex.session_history)
            accuracy = answer_score(out, ex)
            grounding = grounding_score(out, ex)
            neu_acc.append(accuracy)
            neu_grnd.append(grounding)
            if checkpoint:
                checkpoint_rows[ex.example_id] = {
                    "example_id": ex.example_id,
                    "accuracy": accuracy,
                    "grounding": grounding,
                }
                _write_neural_checkpoint(
                    checkpoint,
                    checkpoint_rows,
                    benchmark=benchmark_meta,
                    model=neural_model,
                    generation_options=generation_options,
                )

    ea_m, ea_lo, ea_hi = bootstrap_ci(ext_acc)
    eg_m, eg_lo, eg_hi = bootstrap_ci(ext_grnd)
    na_m, na_lo, na_hi = bootstrap_ci(neu_acc)
    ng_m, ng_lo, ng_hi = bootstrap_ci(neu_grnd)
    ext_acc_stats = bootstrap_mean(ext_acc, resamples=2000, seed=0)
    neural_acc_stats = bootstrap_mean(neu_acc, resamples=2000, seed=1)
    neural_metadata = ollama_model_metadata(neural_model)
    return {
        "n_extractive": len(full),
        "n_neural": len(neural),
        "benchmark_provenance": benchmark_meta,
        "neural_model": neural_model,
        "neural_model_metadata": neural_metadata,
        "neural_generation_options": generation_options,
        "extractive_accuracy": (ea_m, ea_lo, ea_hi),
        "extractive_accuracy_statistics": ext_acc_stats.to_dict(),
        "extractive_grounding": (eg_m, eg_lo, eg_hi),
        "extractive_composite": bootstrap_ci(ext_comp),
        "neural_accuracy": (na_m, na_lo, na_hi),
        "neural_accuracy_statistics": neural_acc_stats.to_dict(),
        "extractive_accuracy_rate": binary_rate(sum(value >= 1.0 for value in ext_acc), len(ext_acc)).to_dict(),
        "neural_accuracy_rate": binary_rate(sum(value >= 1.0 for value in neu_acc), len(neu_acc)).to_dict(),
        "neural_grounding": (ng_m, ng_lo, ng_hi),
        "category_accuracy": {c: bootstrap_ci(v) for c, v in cat_acc.items()},
        "sample_accounting": {
            "unit": "longmemeval_question",
            "extractive": {"n_requested": len(full), "n_evaluated": len(ext_acc), "n_failed": 0, "status": "complete"},
            "neural": {"n_requested": len(neural), "n_evaluated": len(neu_acc), "n_failed": max(0, len(neural) - len(neu_acc)), "status": "complete" if len(neu_acc) == len(neural) else "partial"},
            "benchmark": "LongMemEval_S",
        },
        "runtime_provenance": runtime_provenance(
            models={"neural_model": neural_model, "neural_model_metadata": neural_metadata},
            benchmark=benchmark_meta,
        ),
    }


def _gold_lines(example) -> set:
    return set(example.expected_source_indices)


def _rrf_rank(rankings: list[list[int]], k0: int = 60) -> list[int]:
    """Reciprocal-rank fusion of full line-index rankings.

    This diagnostic uses the same one-based denominator convention as the
    production fusion: an item at zero-based rank ``r`` contributes
    ``1 / (k0 + r + 1)``. The explicit secondary key keeps benchmark ties
    aligned with the production rule.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k0 + rank + 1)
    return sorted(scores, key=lambda i: (-scores[i], i))


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
    out: dict[str, Any] = {"available": have_embed, "n": n, "k": k, "lexical": lex_hits / n}
    if have_embed:
        out["dense"] = dense_hits / n
        out["hybrid"] = hyb_hits / n
    elif embed_error:
        out["embed_error"] = embed_error
    return out


def ranking_diagnostics(
    examples: list[EvalExample],
    *,
    embed_model: str = "nomic-embed-text",
    k: int = 10,
) -> dict:
    """Return lexical/dense/hybrid full-haystack recall diagnostics.

    This is intentionally separate from the live Reasoner campaign: ranking
    diagnostics can be unavailable when the learned embedder is absent, while
    the primary model rows remain resumable and independently accounted.
    """
    if not examples:
        raise ValueError("examples must be non-empty")
    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError("k must be a positive integer")
    return _ranking_recall_by_mode(examples, neural_model=embed_model, k=k)


def bottleneck_analysis(ranking_limit: int = 40, sweep_values=(15, 30, 50, 100), neural_limit: int = 30, neural_model: str = "gemma3:4b", recall_modes_limit: int = 8, embed_model_for_modes: str = "nomic-embed-text") -> dict:  # pragma: no cover - requires the benchmark (+ ollama for neural rows)
    """Localise the LongMemEval bottleneck and measure the fix.

    (1) Ranking recall vs Inspector recall — shows retrieval *ranking* is not the
    bottleneck (the full-haystack ranking recovers the evidence), the Inspector's
    context-narrowing is. (2) An extractive ``max_windows`` sweep — grounding climbs as
    narrowing relaxes, but accuracy stays LM-bound. (3) The neural composition — a wider
    Inspector *plus* a real Reasoner converts recovered recall into accuracy.
    """
    if ranking_limit <= 0 or neural_limit <= 0 or recall_modes_limit <= 0:
        raise ValueError("ranking_limit, neural_limit, and recall_modes_limit must be positive")
    if not sweep_values or any(value <= 0 for value in sweep_values):
        raise ValueError("sweep_values must contain positive window counts")

    from ..compiler.metrics import answer_score, grounding_score
    from ..config import default_config
    from ..harness import AutoHarness, build_run_fn
    from ..llm import OllamaLM
    from ..dspy_runtime import ollama_model_metadata
    from ..retrieval.learned import embed_model_metadata
    from ..retrieval.lexical import BM25Index
    from ..stages.inspector import Inspector

    benchmark_meta = file_provenance(DEFAULT_PATH)
    ranking_loaded = load_longmemeval(limit=ranking_limit)
    examples = [e for e in ranking_loaded if _gold_lines(e)]
    ranking_excluded = len(ranking_loaded) - len(examples)
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
    mode_loaded = ranking_loaded[:recall_modes_limit]
    mode_examples = [e for e in mode_loaded if _gold_lines(e)]
    ranking_modes = _ranking_recall_by_mode(mode_examples, neural_model=embed_model_for_modes)
    mode_excluded = len(mode_loaded) - len(mode_examples)

    sweep_loaded = load_longmemeval(limit=60)
    sweep_examples = [e for e in sweep_loaded if _gold_lines(e)]
    sweep_excluded = len(sweep_loaded) - len(sweep_examples)
    if not sweep_examples:
        raise ValueError("LongMemEval sweep retained no records with gold evidence")
    extractive_sweep = {}
    for mw in sweep_values:
        run = build_run_fn(cfg.with_(max_windows=mw))
        grs = [grounding_score(run(e), e) for e in sweep_examples]
        extractive_sweep[mw] = sum(grs) / len(grs)

    neural_loaded = load_longmemeval(limit=neural_limit)
    neural_examples = [e for e in neural_loaded if _gold_lines(e)]
    neural_excluded = len(neural_loaded) - len(neural_examples)
    if not neural_examples:
        raise ValueError("LongMemEval neural run retained no records with gold evidence")
    lm = OllamaLM(model=neural_model, timeout=120.0)

    def _neural_run(config):
        accs, grs = [], []
        with AutoHarness(config=config, lm=lm) as harness:
            for ex in neural_examples:
                out = harness.forward(ex.query, ex.session_history)
                accs.append(answer_score(out, ex))
                grs.append(grounding_score(out, ex))
        return {"accuracy": sum(accs) / len(accs), "grounding": sum(grs) / len(grs)}

    neural = {mw: _neural_run(cfg.with_(max_windows=mw)) for mw in (min(sweep_values), max(sweep_values))}
    # The shipped fix: the adaptive Inspector recovers accuracy with no manual tuning.
    neural_adaptive = _neural_run(cfg.with_(adaptive_windows=True))

    neural_metadata = ollama_model_metadata(neural_model)
    embed_metadata = embed_model_metadata(embed_model_for_modes)
    return {
        "benchmark_provenance": benchmark_meta,
        "n_ranking": n_rank,
        "ranking_recall_at_10": rank_hits / n_rank,
        "ranking_recall_by_mode": ranking_modes,
        "inspector_recall": insp_hits / n_rank,
        "default_max_windows": cfg.max_windows,
        "sweep_values": list(sweep_values),
        "extractive_grounding_by_maxwindows": extractive_sweep,
        "n_neural": len(neural_examples),
        "neural_model": neural_model,
        "neural_model_metadata": neural_metadata,
        "neural_generation_options": {"temperature": 0.0},
        "embed_model_for_modes": embed_model_for_modes,
        "embed_model_metadata": embed_metadata,
        "neural_by_maxwindows": neural,
        "neural_adaptive": neural_adaptive,
        "sample_accounting": {
            "benchmark": "LongMemEval_S",
            "ranking": {
                "n_requested": ranking_limit,
                "n_loaded": len(ranking_loaded),
                "n_retained": n_rank,
                "n_excluded_no_gold": ranking_excluded,
                "n_evaluated": n_rank,
                "n_failed": 0,
                "status": "filtered" if ranking_excluded else ("capacity_limited" if len(ranking_loaded) < ranking_limit else "complete"),
            },
            "ranking_modes": {
                "n_requested": len(mode_loaded),
                "n_loaded": len(mode_loaded),
                "n_retained": ranking_modes.get("n", 0),
                "n_excluded_no_gold": mode_excluded,
                "n_evaluated": ranking_modes.get("n", 0),
                "n_failed": 0,
                "status": "capacity_limited" if not ranking_modes.get("available") else ("filtered" if mode_excluded else "complete"),
            },
            "extractive_sweep": {
                "n_requested": len(sweep_loaded) * len(sweep_values),
                "n_loaded": len(sweep_loaded),
                "n_retained": len(sweep_examples),
                "n_excluded_no_gold": sweep_excluded,
                "n_evaluated": len(sweep_examples) * len(sweep_values),
                "n_failed": 0,
                "status": "filtered" if sweep_excluded else ("capacity_limited" if len(sweep_loaded) < 60 else "complete"),
            },
            "neural": {
                "n_requested": len(neural_loaded) * 3,
                "n_loaded": len(neural_loaded),
                "n_retained": len(neural_examples),
                "n_excluded_no_gold": neural_excluded,
                "n_evaluated": len(neural_examples) * 3,
                "n_failed": 0,
                "status": "filtered" if neural_excluded else ("capacity_limited" if len(neural_loaded) < neural_limit else "complete"),
            },
            "unit": "longmemeval_question_or_configuration",
        },
        "runtime_provenance": runtime_provenance(
            models={
                "neural_model": neural_model,
                "neural_model_metadata": neural_metadata,
                "embedding_model": embed_model_for_modes,
                "embedding_model_metadata": embed_metadata,
            },
            benchmark=benchmark_meta,
        ),
    }


__all__ = [
    "load_longmemeval",
    "longmemeval_available",
    "validate_longmemeval_payload",
    "longmemeval_eval",
    "bottleneck_analysis",
    "ranking_diagnostics",
    "DEFAULT_PATH",
]
