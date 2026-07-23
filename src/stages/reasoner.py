"""Stage 2 — Reasoner: typed declarative reasoning over ranked evidence.

Deterministic code handles evidence selection, task routing, and citation
construction; the (swappable) language model handles only judgment over
pre-filtered evidence. The Reasoner routes multi-hop / code / knowledge-update
tasks through a deterministic ReAct-style read->integrate selection path and
everything else through one model completion. It does not expose or claim hidden
chain-of-thought; it returns typed outputs including the raw windows it cited,
which lets the Memory Gate audit answer-vs-evidence support.
"""

from __future__ import annotations

from ..memory.consolidation import has_explicit_memory_cue
from ..module import ExtractiveLM, LMClient, Module, Prediction, render_signature_prompt, tokenize
from ..routing import classify_task
from ..signatures import (
    REACT_CATEGORIES,
    EvidenceCitation,
    MemorySnapshot,
    RankedEvidence,
    ReasonerSignature,
    TaskCategory,
)

DEFAULT_MAX_EVIDENCE = 5


class Reasoner(Module):
    """Stage 2 — produce a grounded, typed answer from ranked evidence."""

    signature = ReasonerSignature

    def __init__(
        self,
        lm: LMClient | None = None,
        max_evidence: int = DEFAULT_MAX_EVIDENCE,
        verify: bool = False,
        grounding_threshold: float = 0.3,
    ) -> None:
        if max_evidence <= 0:
            raise ValueError(f"max_evidence must be positive, got {max_evidence}")
        if not 0.0 <= grounding_threshold <= 1.0:
            raise ValueError("grounding_threshold must be in [0, 1]")
        self.lm: LMClient = lm or ExtractiveLM()
        self.max_evidence = max_evidence
        self.verify = verify
        self.grounding_threshold = grounding_threshold

    def forward(  # type: ignore[override]
        self,
        query: str,
        ranked_evidence: list[RankedEvidence],
        task_category: TaskCategory = TaskCategory.SINGLE_SESSION,
        memory_context: MemorySnapshot | None = None,
    ) -> Prediction:
        """Reason over ``ranked_evidence`` to answer ``query``.

        Args:
            query: The current question.
            ranked_evidence: Ranked evidence from the Retriever.
            task_category: Detected task category (selects strategy).
            memory_context: Frozen MEMORY/USER snapshot (read-only).

        Returns:
            A :class:`Prediction` with ``reasoning_trace``, ``answer``,
            ``evidence_citations`` (list[EvidenceCitation]) and
            ``requires_consolidation`` (bool).
        """
        memory_context = memory_context or MemorySnapshot()
        explicit_request = has_explicit_memory_cue(query)
        self.signature.validate_inputs(
            query=query,
            ranked_evidence=ranked_evidence,
            task_category=task_category,
            memory_context=memory_context,
        )
        top = ranked_evidence[: self.max_evidence]
        evidence_texts = [r.window.text for r in top]
        strategy = "react_style" if task_category in REACT_CATEGORIES else "single_pass"

        if not evidence_texts:
            trace = f"[{strategy}] no evidence available; answering from query alone"
            answer = self.lm.complete(render_signature_prompt(self.signature, [], query=query))
            return Prediction(
                {
                    "reasoning_trace": trace,
                    "answer": answer,
                    "evidence_citations": [],
                    "requires_consolidation": self._needs_consolidation(
                        task_category, explicit_request
                    ),
                    "explicit_request": explicit_request,
                }
            )

        if strategy == "react_style":
            answer, trace = self._react(query, top)
        else:
            answer, trace = self._single_pass(query, evidence_texts)

        citations = self._build_citations(answer, top)

        if self.verify:
            answer, citations, trace = self._verify(query, top, evidence_texts, answer, citations, trace)

        return Prediction(
            {
                "reasoning_trace": trace,
                "answer": answer,
                "evidence_citations": citations,
                "requires_consolidation": self._needs_consolidation(
                    task_category, explicit_request
                ),
                "explicit_request": explicit_request,
            }
        )

    def _verify(
        self,
        query: str,
        top: list[RankedEvidence],
        evidence_texts: list[str],
        answer: str,
        citations: list[EvidenceCitation],
        trace: str,
    ) -> tuple[str, list[EvidenceCitation], str]:
        """Verification pass: re-answer over the full evidence if grounding is weak.

        Computes a set-based token-support proxy over the cited excerpts. If it
        falls below ``grounding_threshold``, the Reasoner re-answers over the
        current ranked evidence set and rebuilds citations. This is an operational
        support check, not semantic entailment or a factuality guarantee.
        """
        support = self._grounding_support(answer, citations)
        if support >= self.grounding_threshold:
            return answer, citations, f"{trace}; [verify ok grounding={support:.2f}]"
        prompt = render_signature_prompt(self.signature, evidence_texts, query=query)
        new_answer = self.lm.complete(prompt)
        new_citations = self._build_citations(new_answer, top)
        new_support = self._grounding_support(new_answer, new_citations)
        return (
            new_answer,
            new_citations,
            f"{trace}; [verify reanswer grounding={support:.2f}->{new_support:.2f}]",
        )

    @staticmethod
    def _grounding_support(answer: str, citations: list[EvidenceCitation]) -> float:
        """Fraction of answer tokens present in the cited excerpts (0..1)."""
        answer_tokens = set(tokenize(answer))
        if not answer_tokens:
            return 0.0
        cited_tokens = set(tokenize(" ".join(c.excerpt for c in citations)))
        return len(answer_tokens & cited_tokens) / len(answer_tokens)

    def _single_pass(self, query: str, evidence_texts: list[str]) -> tuple[str, str]:
        """Make one model completion over the ranked evidence."""
        prompt = render_signature_prompt(self.signature, evidence_texts, query=query)
        answer = self.lm.complete(prompt)
        trace = f"[single_pass] completed one model call over {len(evidence_texts)} evidence window(s)"
        return answer, trace

    def _react(
        self,
        query: str,
        top: list[RankedEvidence],
    ) -> tuple[str, str]:
        """Deterministic read->integrate selection for multi-hop/code/update tasks.

        Hop 1 narrows to windows that share a query token (the "read" step); if
        the narrowing keeps at least one window one model completion is produced
        over that subset, otherwise the full ranked set is used.
        """
        q_tokens = set(tokenize(query))
        narrowed = [r for r in top if q_tokens & set(tokenize(r.window.text))]
        used = narrowed if narrowed else top
        used_texts = [r.window.text for r in used]
        prompt = render_signature_prompt(self.signature, used_texts, query=query)
        answer = self.lm.complete(prompt)
        trace = f"[react_style] deterministic hop1 token filter -> {len(used)}/{len(top)} window(s); one model synthesis call"
        return answer, trace

    @staticmethod
    def _build_citations(answer: str, top: list[RankedEvidence]) -> list[EvidenceCitation]:
        """Cite windows overlapping the answer; fall back to the top window."""
        answer_tokens = set(tokenize(answer))
        citations: list[EvidenceCitation] = []
        for r in top:
            if answer_tokens & set(tokenize(r.window.text)):
                citations.append(EvidenceCitation(source_index=r.window.source_index, excerpt=r.window.text))
        if not citations and top:
            win = top[0].window
            citations.append(EvidenceCitation(source_index=win.source_index, excerpt=win.text))
        return citations

    @staticmethod
    def _needs_consolidation(task_category: TaskCategory, explicit_request: bool) -> bool:
        """Flag consolidation for knowledge updates or explicit remember cues."""
        if task_category is TaskCategory.KNOWLEDGE_UPDATE:
            return True
        return explicit_request


__all__ = ["Reasoner", "classify_task", "DEFAULT_MAX_EVIDENCE"]
