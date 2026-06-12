"""Lexical retrieval: BM25 (Okapi) scoring and grep/regex anchoring.

The agentic-search study (Sen et al., 2026) found grep generally higher than
vector retrieval in its inline comparisons, with outcomes still conditioned by
harness and tool-calling style. This module is the harness's primary retrieval
lane: it is exact when a discriminative pattern exists and fully deterministic.
"""

from __future__ import annotations

from collections import Counter
import math
import re

from ..module import tokenize

# BM25 defaults (Robertson's canonical values); named so the manuscript can source
# them as tokens rather than hard-coding 1.5 / 0.75 in the prose.
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75

# Common English stop-words removed when deriving grep patterns from a query.
# Kept small and explicit (no NLTK dependency) for determinism.
_STOPWORDS: frozenset[str] = frozenset(
    """a an and the of to in on at for with is are was were be been being do does
    did has have had this that these those it its as by or if then than from what
    when where which who whom how why i you he she they we my your our their""".split()
)


class BM25Index:
    """Okapi BM25 index over a fixed document corpus.

    Args:
        documents: Corpus of document strings.
        k1: Term-frequency saturation parameter (default 1.5).
        b: Length-normalization parameter (default 0.75).

    Raises:
        ValueError: If ``documents`` is empty or k1/b are out of range.
    """

    def __init__(self, documents: list[str], k1: float = DEFAULT_K1, b: float = DEFAULT_B) -> None:
        if not documents:
            raise ValueError("BM25Index requires at least one document")
        if k1 < 0:
            raise ValueError(f"k1 must be non-negative, got {k1}")
        if not 0.0 <= b <= 1.0:
            raise ValueError(f"b must be in [0, 1], got {b}")

        self.documents = documents
        self.k1 = k1
        self.b = b
        self._doc_tokens = [tokenize(doc) for doc in documents]
        self._doc_len = [len(toks) for toks in self._doc_tokens]
        self.avgdl = sum(self._doc_len) / len(documents)
        self._doc_freqs: list[Counter[str]] = [Counter(toks) for toks in self._doc_tokens]
        self._idf = self._compute_idf()

    def _compute_idf(self) -> dict[str, float]:
        """Compute smoothed inverse document frequency for every term."""
        n_docs = len(self.documents)
        df: Counter[str] = Counter()
        for freqs in self._doc_freqs:
            df.update(freqs.keys())
        idf: dict[str, float] = {}
        for term, n_q in df.items():
            # BM25 idf with +1 inside the log to keep values non-negative.
            idf[term] = math.log(1 + (n_docs - n_q + 0.5) / (n_q + 0.5))
        return idf

    def score(self, query: str) -> list[float]:
        """Return the BM25 score of every document against ``query``."""
        q_terms = tokenize(query)
        scores = [0.0] * len(self.documents)
        for idx, freqs in enumerate(self._doc_freqs):
            dl = self._doc_len[idx]
            denom_norm = self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl else self.k1
            doc_score = 0.0
            for term in q_terms:
                if term not in freqs:
                    continue
                tf = freqs[term]
                idf = self._idf.get(term, 0.0)
                doc_score += idf * (tf * (self.k1 + 1)) / (tf + denom_norm)
            scores[idx] = doc_score
        return scores

    def top_k(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        """Return the top-k (doc_index, score) pairs, descending by score.

        Ties break on ascending document index for determinism. Documents with a
        zero score are excluded (no lexical signal).
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        scored = [(idx, s) for idx, s in enumerate(self.score(query)) if s > 0.0]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:k]


def extract_key_phrases(query: str, max_phrases: int = 8) -> list[str]:
    """Extract grep-able key terms from a query (stop-words removed).

    Args:
        query: The query to derive patterns from.
        max_phrases: Maximum number of patterns to return.

    Returns:
        Distinct content tokens in first-seen order, capped at ``max_phrases``.
    """
    seen: list[str] = []
    for token in tokenize(query):
        if token in _STOPWORDS or len(token) <= 1:
            continue
        if token not in seen:
            seen.append(token)
        if len(seen) >= max_phrases:
            break
    return seen


def grep(
    documents: list[str],
    patterns: list[str],
    ignore_case: bool = True,
) -> list[int]:
    """Return indices of documents matching ANY of ``patterns`` (regex).

    This is the literal "grep over the stored context variable" operation the
    Recursive Language Model uses to narrow evidence before a neural call.

    Args:
        documents: Documents to scan.
        patterns: Regex patterns; each is compiled independently.
        ignore_case: Case-insensitive matching (default True).

    Returns:
        Sorted, de-duplicated list of matching document indices.

    Raises:
        re.error: If a pattern is not a valid regular expression.
    """
    flags = re.IGNORECASE if ignore_case else 0
    compiled = [re.compile(p, flags) for p in patterns if p]
    if not compiled:
        return []
    hits: set[int] = set()
    for idx, doc in enumerate(documents):
        if any(rx.search(doc) for rx in compiled):
            hits.add(idx)
    return sorted(hits)


# Public alias so other retrieval modules (e.g. query expansion) can share the
# same stop-word set without re-declaring it.
STOPWORDS = _STOPWORDS

__all__ = ["BM25Index", "extract_key_phrases", "grep", "STOPWORDS"]
