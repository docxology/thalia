"""Pseudo-relevance-feedback (PRF) query expansion.

A lightweight, deterministic RM3-style expansion: run an initial BM25 pass, take
the most frequent content terms from the top-ranked windows, and append them to
the query. This broadens recall for under-specified queries without an external
model. Expansion is off by default (`query_expansion`); when on, both retrieval
lanes use the expanded query.
"""

from __future__ import annotations

from collections import Counter

from ..module import tokenize
from .lexical import STOPWORDS, BM25Index


def expand_query(
    query: str,
    documents: list[str],
    top_docs: int = 3,
    top_terms: int = 5,
) -> str:
    """Return ``query`` augmented with feedback terms from its top documents.

    Args:
        query: The original query.
        documents: Candidate documents (the Inspector's window texts).
        top_docs: Number of top BM25 documents to mine for feedback terms.
        top_terms: Maximum number of new terms to append.

    Returns:
        The expanded query (original query plus distinct feedback terms, in
        descending frequency then alphabetical order). Returns the original query
        unchanged when there are no documents or no useful feedback terms.

    Raises:
        ValueError: If ``top_docs`` or ``top_terms`` is non-positive.
    """
    if top_docs <= 0:
        raise ValueError(f"top_docs must be positive, got {top_docs}")
    if top_terms <= 0:
        raise ValueError(f"top_terms must be positive, got {top_terms}")
    if not documents:
        return query

    index = BM25Index(documents)
    ranked = index.top_k(query, min(top_docs, len(documents)))
    if not ranked:
        return query

    query_terms = set(tokenize(query))
    counts: Counter[str] = Counter()
    for doc_idx, _ in ranked:
        for term in tokenize(documents[doc_idx]):
            if term in STOPWORDS or term in query_terms or len(term) <= 2:
                continue
            counts[term] += 1

    # Deterministic ordering: descending count, then alphabetical.
    feedback = [t for t, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    feedback = feedback[:top_terms]
    if not feedback:
        return query
    return query + " " + " ".join(feedback)


__all__ = ["expand_query"]
