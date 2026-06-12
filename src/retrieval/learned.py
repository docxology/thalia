"""Optional real learned-embedding semantic lane via Ollama.

The deterministic hashing surrogate in :mod:`src.retrieval.semantic` is the offline
default. This module realises the documented extension point — a *real* neural
sentence embedder — behind the same ``score`` / ``top_k`` interface, so it drops into
the Retriever unchanged. It is gated on a live Ollama embedding model and never
required by the deterministic core.

It exists to measure, not assert, the manuscript's second scope boundary: a learned
embedder captures paraphrase meaning the sub-word surrogate cannot. The pure probe
set and the deterministic surrogate side are unit-tested directly; the Ollama glue is
exercised by model-gated tests and recorded to ``data/learned_retrieval.json``.
"""

from __future__ import annotations

import json
import urllib.request

import numpy as np

from .semantic import SemanticIndex

DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_BASE = "http://localhost:11434"
DEFAULT_DOCUMENT_PREFIX = "search_document: "
DEFAULT_QUERY_PREFIX = "search_query: "

# Paraphrase probes: each query shares *meaning* with the gold document but little or
# no surface morphology, so the char-trigram surrogate cannot bridge the gap. Index 0
# is always the gold document.
PARAPHRASE_PROBES: list[tuple[str, list[str], int]] = [
    ("What is the access code for the network?", ["The wifi password is bluefish42.", "The cat is grey.", "Lunch is at noon."], 0),
    ("When does the automobile maintenance happen?", ["The car service is booked for April 12th.", "The sky is blue.", "I like tea."], 0),
    ("Where is the person residing now?", ["I now live in Lisbon.", "The report is due Friday.", "Pizza for dinner."], 0),
    ("Which beverage is preferred?", ["My favourite drink is black coffee.", "The meeting moved to room 4.", "It rained yesterday."], 0),
]


def surrogate_recall_at_1(probes: list[tuple[str, list[str], int]] | None = None) -> float:
    """Deterministic surrogate (hashing-trigram) recall@1 over the paraphrase probes."""
    probes = probes or PARAPHRASE_PROBES
    hits = 0
    for query, docs, gold in probes:
        top = SemanticIndex(docs).top_k(query, k=1)
        if top and top[0][0] == gold:
            hits += 1
    return hits / len(probes)


def _normalise_model_names(model: str) -> set[str]:
    """Return Ollama tag names that should count as ``model``."""
    return {model, f"{model}:latest"} if ":" not in model else {model}


def model_metadata_from_tags(tags: dict, model: str) -> dict:
    """Pure Ollama tag parser used by recorder scripts and tests."""
    wanted = _normalise_model_names(model)
    for entry in tags.get("models", []):
        if entry.get("name") in wanted or entry.get("model") in wanted:
            return {
                "requested_model": model,
                "model": entry.get("name") or entry.get("model") or model,
                "digest": entry.get("digest"),
                "modified_at": entry.get("modified_at"),
                "size": entry.get("size"),
                "details": entry.get("details", {}),
                "available": True,
            }
    return {
        "requested_model": model,
        "model": model,
        "digest": None,
        "modified_at": None,
        "size": None,
        "details": {},
        "available": False,
    }


def embed_model_metadata(model: str = DEFAULT_EMBED_MODEL, api_base: str = DEFAULT_OLLAMA_BASE) -> dict:  # pragma: no cover - real network probe
    """Return best-effort Ollama metadata for the embedding model."""
    try:
        with urllib.request.urlopen(f"{api_base}/api/tags", timeout=3) as resp:
            metadata = model_metadata_from_tags(json.load(resp), model)
    except Exception as exc:
        metadata = model_metadata_from_tags({}, model)
        metadata["error"] = f"{type(exc).__name__}: {exc}"
    metadata["api_base"] = api_base
    try:
        with urllib.request.urlopen(f"{api_base}/api/version", timeout=3) as resp:
            version = json.load(resp)
        metadata["ollama_version"] = version.get("version")
    except Exception:
        metadata["ollama_version"] = None
    return metadata


def _with_prefix(text: str, prefix: str | None) -> str:
    """Apply a nomic-style task prefix without double-prefixing."""
    if not prefix:
        return text
    return text if text.startswith(prefix) else f"{prefix}{text}"


def embed_model_available(model: str = DEFAULT_EMBED_MODEL, api_base: str = DEFAULT_OLLAMA_BASE) -> bool:  # pragma: no cover - real network probe
    """True when Ollama lists ``model`` and a tiny embedding call succeeds."""
    if not embed_model_metadata(model=model, api_base=api_base).get("available"):
        return False
    try:
        embed_ollama("availability probe", model=model, api_base=api_base, prefix=DEFAULT_QUERY_PREFIX)
    except Exception:
        return False
    return True


def embed_ollama(
    text: str,
    model: str = DEFAULT_EMBED_MODEL,
    api_base: str = DEFAULT_OLLAMA_BASE,
    prefix: str | None = None,
) -> np.ndarray:  # pragma: no cover - requires a live ollama model
    """Embed ``text`` to a unit-norm vector via a real Ollama embedding model."""
    payload = json.dumps({"model": model, "input": _with_prefix(text, prefix)}).encode("utf-8")
    request = urllib.request.Request(f"{api_base}/api/embed", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        vec = np.array(json.load(resp)["embeddings"][0], dtype=float)
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


class LearnedSemanticIndex:  # pragma: no cover - requires a live ollama model
    """Cosine index over real neural embeddings; same contract as SemanticIndex."""

    def __init__(
        self,
        documents: list[str],
        model: str = DEFAULT_EMBED_MODEL,
        api_base: str = DEFAULT_OLLAMA_BASE,
        document_prefix: str = DEFAULT_DOCUMENT_PREFIX,
        query_prefix: str = DEFAULT_QUERY_PREFIX,
    ) -> None:
        if not documents:
            raise ValueError("LearnedSemanticIndex requires at least one document")
        self.documents = documents
        self.model = model
        self.api_base = api_base
        self.document_prefix = document_prefix
        self.query_prefix = query_prefix
        self._matrix = np.vstack([embed_ollama(doc, model, api_base, prefix=document_prefix) for doc in documents])

    def score(self, query: str) -> list[float]:
        q_vec = embed_ollama(query, self.model, self.api_base, prefix=self.query_prefix)
        return [float(np.dot(q_vec, row)) for row in self._matrix]

    def top_k(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        scored = [(idx, s) for idx, s in enumerate(self.score(query)) if s > 0.0]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:k]


def learned_recall_at_1(probes: list[tuple[str, list[str], int]] | None = None, model: str = DEFAULT_EMBED_MODEL) -> float:  # pragma: no cover - requires a live ollama model
    """Learned-embedder recall@1 over the paraphrase probes (needs a live model)."""
    probes = probes or PARAPHRASE_PROBES
    hits = 0
    for query, docs, gold in probes:
        top = LearnedSemanticIndex(docs, model=model).top_k(query, k=1)
        if top and top[0][0] == gold:
            hits += 1
    return hits / len(probes)


def dense_rag_answer(session_history: str, query: str, k: int = 3, model: str = DEFAULT_EMBED_MODEL, api_base: str = DEFAULT_OLLAMA_BASE) -> str:  # pragma: no cover - requires a live ollama model
    """External baseline: pure neural-embedding retrieval then extractive answer.

    No Inspector, no lexical lane, no citations — retrieve the top-``k`` session lines
    by real embedding cosine to the query and answer over them. Used to check whether
    the harness's lexical-anchored hybrid beats an off-the-shelf dense RAG (it ties on
    accuracy on the synthetic set: the harness's value is provenance, not retrieval).
    """
    from ..module import ExtractiveLM

    lines = [line for line in session_history.split("\n") if line.strip()]
    if not lines:
        return ""
    q_vec = embed_ollama(query, model, api_base, prefix=DEFAULT_QUERY_PREFIX)
    matrix = np.vstack([embed_ollama(line, model, api_base, prefix=DEFAULT_DOCUMENT_PREFIX) for line in lines])
    order = list(np.argsort(-(matrix @ q_vec)))[:k]
    evidence = "\n".join(lines[i] for i in order)
    return ExtractiveLM().complete(f"### EVIDENCE\n{evidence}\n\n### QUESTION\n{query}")


def paraphrase_retrieval_probe(model: str = DEFAULT_EMBED_MODEL) -> dict:  # pragma: no cover - requires a live ollama model
    """Real surrogate-vs-learned recall@1 measurement on the paraphrase probes."""
    return {
        "model": model,
        "model_metadata": embed_model_metadata(model=model),
        "metric": "recall@1",
        "n_probes": len(PARAPHRASE_PROBES),
        "embedding_document_prefix": DEFAULT_DOCUMENT_PREFIX.strip(),
        "embedding_query_prefix": DEFAULT_QUERY_PREFIX.strip(),
        "surrogate_recall_at_1": surrogate_recall_at_1(),
        "learned_recall_at_1": learned_recall_at_1(model=model),
    }


__all__ = [
    "DEFAULT_EMBED_MODEL",
    "DEFAULT_OLLAMA_BASE",
    "DEFAULT_DOCUMENT_PREFIX",
    "DEFAULT_QUERY_PREFIX",
    "PARAPHRASE_PROBES",
    "surrogate_recall_at_1",
    "model_metadata_from_tags",
    "embed_model_metadata",
    "embed_model_available",
    "embed_ollama",
    "LearnedSemanticIndex",
    "learned_recall_at_1",
    "dense_rag_answer",
    "paraphrase_retrieval_probe",
]
