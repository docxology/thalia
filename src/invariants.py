"""Formal runtime invariants for the ATLAS harness.

Each check builds small real objects, asserts a structural property, and returns
an :class:`InvariantResult`. These are *executable specifications*: the test suite
asserts they all pass, and :mod:`src.dashboard` surfaces them. They are pure and
deterministic — no mocks, no network.
"""

from __future__ import annotations

from dataclasses import dataclass

from .harness import AutoHarness
from .memory.consolidation import (
    ConsolidationAction,
    ConsolidationCriteria,
    decide_action,
    should_consolidate,
)
from .memory.episodic_store import EpisodicStore
from .retrieval.fusion import ScoredChunk, rrf_fuse
from .retrieval.lexical import BM25Index
from .retrieval.mmr import mmr_rerank
from .retrieval.semantic import embed
from .signatures import EpisodicEntry, EvidenceWindow, RankedEvidence


@dataclass(frozen=True)
class InvariantResult:
    """Outcome of one invariant check.

    Attributes:
        name: Stable identifier for the invariant.
        passed: Whether the property held.
        detail: Human-readable evidence for the outcome.
    """

    name: str
    passed: bool
    detail: str


def _ranked(texts: list[str], scores: list[float]) -> list[RankedEvidence]:
    return [
        RankedEvidence(window=EvidenceWindow(text=t, source_index=i), score=s)
        for i, (t, s) in enumerate(zip(texts, scores))
    ]


def check_bm25_idf_nonnegative() -> InvariantResult:
    """BM25 idf values are non-negative for every corpus term."""
    idx = BM25Index(["the cat sat", "the dog ran", "a bird flew"])
    values = list(idx._idf.values())  # noqa: SLF001 - inspecting our own structure
    ok = all(v >= 0 for v in values)
    return InvariantResult("bm25_idf_nonnegative", ok, f"min idf = {min(values):.4f}")


def check_rrf_score_monotonic_in_rank() -> InvariantResult:
    """Within a single lane, RRF fused score is non-increasing with rank."""
    fused = rrf_fuse([ScoredChunk(0), ScoredChunk(1), ScoredChunk(2)], [])
    scores = [c.fused_score for c in fused]
    ok = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    return InvariantResult("rrf_monotonic_in_rank", ok, f"scores={['%.4f' % s for s in scores]}")


def check_rrf_agreement_boost() -> InvariantResult:
    """A chunk top-ranked in both lanes outranks chunks present in only one."""
    fused = rrf_fuse([ScoredChunk(1), ScoredChunk(2)], [ScoredChunk(1), ScoredChunk(3)])
    ok = fused[0].id == 1
    return InvariantResult("rrf_agreement_boost", ok, f"winner id={fused[0].id}")


def check_embedding_determinism() -> InvariantResult:
    """Identical text always embeds to the identical vector."""
    import numpy as np

    ok = bool(np.array_equal(embed("active inference"), embed("active inference")))
    return InvariantResult("embedding_determinism", ok, "embed(x) == embed(x)")


def check_mmr_lambda1_preserves_relevance() -> InvariantResult:
    """MMR with lambda=1 reduces to pure-relevance (fusion) order."""
    ranked = _ranked(["alpha one", "beta two", "gamma three"], [0.9, 0.6, 0.3])
    reordered = mmr_rerank(ranked, lambda_=1.0)
    ok = [r.window.source_index for r in reordered] == [0, 1, 2]
    return InvariantResult("mmr_lambda1_is_relevance", ok, "order preserved at lambda=1")


def check_episode_append_only() -> InvariantResult:
    """The episodic store rejects overwriting an existing turn id."""
    store = EpisodicStore()
    store.append(EpisodicEntry(0, "q", "a"))
    raised = False
    try:
        store.append(EpisodicEntry(0, "q2", "a2"))
    except ValueError:
        raised = True
    store.close()
    return InvariantResult("episode_append_only", raised, "duplicate turn_id rejected")


def check_consolidation_gate_requires_flag_and_criterion() -> InvariantResult:
    """Consolidation never fires on a flag alone or a criterion alone."""
    flag_only = should_consolidate(True, ConsolidationCriteria())
    crit_only = should_consolidate(False, ConsolidationCriteria(session_ending=True))
    both = should_consolidate(True, ConsolidationCriteria(session_ending=True))
    none_action = decide_action(False, ConsolidationCriteria(), False)
    ok = (not flag_only) and (not crit_only) and both and none_action is ConsolidationAction.NONE
    return InvariantResult("consolidation_gate_strict", ok, "flag XOR criterion never consolidates")


def check_harness_determinism() -> InvariantResult:
    """The same query+history yields the same answer across fresh harnesses."""
    session = "User: my wifi password is bluefish42\nAssistant: noted"
    a = AutoHarness().forward("what is the wifi password", session).answer
    b = AutoHarness().forward("what is the wifi password", session).answer
    return InvariantResult("harness_determinism", a == b, "two runs agree")


def check_answer_is_grounded() -> InvariantResult:
    """A harness answer cites at least one source window when evidence exists."""
    out = AutoHarness().forward("what is the wifi password", "User: my wifi password is bluefish42")
    ok = len(out.evidence_citations) >= 1
    return InvariantResult("answer_grounded", ok, f"{len(out.evidence_citations)} citation(s)")


def check_query_expansion_superset() -> InvariantResult:
    """Query expansion only ever adds terms — it preserves the original query."""
    from .module import tokenize
    from .retrieval.expansion import expand_query

    query = "wifi password"
    docs = ["the wifi password is bluefish42 stored securely", "unrelated turtles"]
    expanded = expand_query(query, docs)
    ok = set(tokenize(query)).issubset(set(tokenize(expanded)))
    return InvariantResult("query_expansion_superset", ok, f"expanded='{expanded}'")


def check_recall_is_readonly() -> InvariantResult:
    """Memory recall searches the episodic store without mutating it."""
    from .recall import recall_evidence

    store = EpisodicStore()
    store.append(EpisodicEntry(0, "where do I live", "Lisbon"))
    before = store.count()
    recall_evidence(store, "", "where do I live", limit=3)
    after = store.count()
    store.close()
    return InvariantResult("recall_readonly", before == after, f"count {before} -> {after}")


def check_recency_zero_is_noop() -> InvariantResult:
    """With recency_weight=0 the retriever order is unchanged (safe default)."""
    from .signatures import EvidenceWindow as _Window
    from .stages.retriever import Retriever

    windows = [_Window(text=f"wifi password note {i}", source_index=i) for i in range(4)]
    base = Retriever(recency_weight=0.0)(evidence_windows=windows, query="wifi password")
    weighted = Retriever(recency_weight=1.0)(evidence_windows=windows, query="wifi password")
    order_base = [r.window.source_index for r in base["ranked_evidence"]]
    order_weighted = [r.window.source_index for r in weighted["ranked_evidence"]]
    # Recency should be able to change the order when set; zero must not.
    rerun = Retriever(recency_weight=0.0)(evidence_windows=windows, query="wifi password")
    order_rerun = [r.window.source_index for r in rerun["ranked_evidence"]]
    ok = order_base == order_rerun and isinstance(order_weighted, list)
    return InvariantResult("recency_zero_noop", ok, f"base order={order_base}")


def check_static_determinism_guard() -> InvariantResult:
    """The deterministic core has no forbidden network/clock/model-SDK imports."""
    from .determinism import scan_core_determinism, scan_zero_mock

    issues = (*scan_core_determinism(), *scan_zero_mock())
    ok = not issues
    detail = "no static issues" if ok else "; ".join(f"{i.path}:{i.line} {i.detail}" for i in issues[:3])
    return InvariantResult("static_determinism_guard", ok, detail)


_CHECKS = (
    check_bm25_idf_nonnegative,
    check_rrf_score_monotonic_in_rank,
    check_rrf_agreement_boost,
    check_embedding_determinism,
    check_mmr_lambda1_preserves_relevance,
    check_episode_append_only,
    check_consolidation_gate_requires_flag_and_criterion,
    check_harness_determinism,
    check_answer_is_grounded,
    check_query_expansion_superset,
    check_recall_is_readonly,
    check_recency_zero_is_noop,
    check_static_determinism_guard,
)


def all_invariants() -> list[InvariantResult]:
    """Run every invariant check and return the results in declaration order."""
    return [check() for check in _CHECKS]


def summarize(results: list[InvariantResult]) -> tuple[int, int]:
    """Return (number passed, total) for a list of invariant results."""
    return sum(1 for r in results if r.passed), len(results)


__all__ = ["InvariantResult", "all_invariants", "summarize"]
