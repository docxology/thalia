"""Stage 0 — Inspector: RLM-style context narrowing.

Following Zhang, Kraska & Khattab (2025/26), the Inspector treats the (possibly
very long) session history as *external state*, not as direct neural input. It
loads the history into a small REPL environment, peeks at structure, greps for
query-anchored patterns, and emits only compact :class:`EvidenceWindow` objects
plus auditable :class:`InspectorMetadata`. The full context is never forwarded to
a neural call — this is the harness's defence against context rot.
"""

from __future__ import annotations

from ..module import Module, Prediction, tokenize
from ..retrieval.lexical import extract_key_phrases, grep
from ..signatures import EvidenceWindow, InspectorMetadata, InspectorSignature

DEFAULT_MAX_WINDOWS = 15


def adaptive_max_windows(n_lines: int, base: int = DEFAULT_MAX_WINDOWS, ratio: int = 5) -> int:
    """Scale the narrowing budget with context size: ``max(base, n_lines // ratio)``.

    The fixed ``base`` window cap is tuned for compact contexts and is the dominant
    recall bottleneck on real long-context haystacks (it discards evidence before
    ranking, [@sec:eval-bottleneck]). This keeps ~one window per ``ratio`` lines so the
    budget grows with the haystack, while a compact context (``n_lines <= base*ratio``)
    is left exactly at ``base`` — the deterministic default is unchanged.
    """
    return max(base, n_lines // max(1, ratio))


class REPLEnvironment:
    """A minimal Read-Eval-Print environment holding context as a variable.

    The context is split into line-addressable records once; every operation
    (peek / grep / partition) reads from that immutable view, mirroring the way an
    RLM manipulates a stored ``context`` variable without re-loading it.

    Args:
        context: The raw session history.
    """

    def __init__(self, context: str) -> None:
        self.context = context
        self._lines: list[str] = []
        self._offsets: list[tuple[int, int]] = []
        cursor = 0
        for raw_line in context.splitlines(keepends=True):
            stripped = raw_line.strip()
            start = cursor
            cursor += len(raw_line)
            if stripped:
                self._lines.append(stripped)
                self._offsets.append((start, start + len(stripped)))

    def peek(self, n_chars: int = 500) -> str:
        """Return the first ``n_chars`` characters of the context."""
        return self.context[:n_chars]

    def line_count(self) -> int:
        """Return the number of non-empty records in the context."""
        return len(self._lines)

    def lines(self) -> list[str]:
        """Return the non-empty records (turns) in order."""
        return list(self._lines)

    def grep(self, patterns: list[str]) -> list[int]:
        """Return record indices matching ANY of the regex ``patterns``."""
        return grep(self._lines, patterns)

    def window(self, index: int) -> EvidenceWindow:
        """Build an :class:`EvidenceWindow` for record ``index``."""
        start, end = self._offsets[index]
        return EvidenceWindow(
            text=self._lines[index],
            source_index=index,
            start=start,
            end=end,
        )

    def partition(self, block_size: int) -> list[list[int]]:
        """Partition record indices into consecutive blocks of ``block_size``.

        The RLM "partition + map" primitive: a long context is chunked so a coarse
        pass can discard whole blocks before fine-grained windowing.

        Raises:
            ValueError: If ``block_size`` is not positive.
        """
        if block_size <= 0:
            raise ValueError(f"block_size must be positive, got {block_size}")
        n = len(self._lines)
        return [list(range(i, min(i + block_size, n))) for i in range(0, n, block_size)]


def _relevance(line: str, query_tokens: set[str]) -> float:
    """Fraction of query tokens present in ``line`` (0..1)."""
    if not query_tokens:
        return 0.0
    line_tokens = set(tokenize(line))
    return len(query_tokens & line_tokens) / len(query_tokens)


class Inspector(Module):
    """Stage 0 — narrow session history to compact, query-anchored windows."""

    signature = InspectorSignature

    def __init__(
        self,
        max_windows: int = DEFAULT_MAX_WINDOWS,
        partition_threshold: int = 40,
        partition_size: int = 10,
    ) -> None:
        if max_windows <= 0:
            raise ValueError(f"max_windows must be positive, got {max_windows}")
        if partition_threshold <= 0:
            raise ValueError(f"partition_threshold must be positive, got {partition_threshold}")
        if partition_size <= 0:
            raise ValueError(f"partition_size must be positive, got {partition_size}")
        self.max_windows = max_windows
        self.partition_threshold = partition_threshold
        self.partition_size = partition_size
        self.adaptive_windows = False

    def _coarse_block_filter(self, repl: REPLEnvironment, query_tokens: set[str]) -> set[int]:
        """RLM coarse pass: keep only records in the highest-scoring blocks.

        Scores each partition block by summed per-record query overlap and keeps
        enough top blocks to supply ``max_windows`` candidates. Returns the set of
        allowed record indices.
        """
        blocks = repl.partition(self.partition_size)
        scored_blocks = [(sum(_relevance(repl.lines()[i], query_tokens) for i in block), block) for block in blocks]
        scored_blocks.sort(key=lambda pair: -pair[0])
        n_keep = max(1, self.max_windows // self.partition_size + 1)
        allowed: set[int] = set()
        for _, block in scored_blocks[:n_keep]:
            allowed.update(block)
        return allowed

    def forward(self, session_history: str, query: str) -> Prediction:  # type: ignore[override]
        """Emit evidence windows + metadata for ``query`` over ``session_history``.

        Args:
            session_history: The raw transcript (arbitrarily long).
            query: The current question.

        Returns:
            A :class:`Prediction` with ``evidence_windows`` (list[EvidenceWindow])
            and ``metadata`` (InspectorMetadata).
        """
        self.signature.validate_inputs(session_history=session_history, query=query)
        repl = REPLEnvironment(session_history)
        query_tokens = set(tokenize(query))
        patterns = extract_key_phrases(query)

        # RLM-style recursion: for long contexts, coarse-filter to the best blocks
        # before fine-grained windowing (depth-1 partition + map).
        allowed: set[int] | None = None
        partition_blocks_considered = 0
        if repl.line_count() > self.partition_threshold:
            allowed = self._coarse_block_filter(repl, query_tokens)
            partition_blocks_considered = len(repl.partition(self.partition_size))

        # Lexical anchoring: grep first (RLM pattern). If grep is empty (e.g. only
        # paraphrase overlap), fall back to ranking every record by token overlap.
        candidate_indices = repl.grep(patterns)
        if allowed is not None:
            candidate_indices = [i for i in candidate_indices if i in allowed]
        if not candidate_indices:
            candidate_indices = sorted(allowed) if allowed is not None else list(range(repl.line_count()))

        scored: list[tuple[int, float]] = []
        for idx in candidate_indices:
            rel = _relevance(repl.lines()[idx], query_tokens)
            if rel > 0.0 or patterns == []:
                scored.append((idx, rel))
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        selected = scored[: self.max_windows]

        windows = [
            EvidenceWindow(
                text=repl.window(idx).text,
                source_index=idx,
                relevance=round(rel, 6),
                start=repl.window(idx).start,
                end=repl.window(idx).end,
            )
            for idx, rel in selected
        ]

        covered: set[str] = set()
        for win in windows:
            covered |= query_tokens & set(tokenize(win.text))
        confidence = len(covered) / len(query_tokens) if query_tokens else 0.0

        metadata = InspectorMetadata(
            grep_patterns=tuple(patterns),
            window_indices=tuple(w.source_index for w in windows),
            confidence=round(confidence, 6),
            session_length=len(session_history),
            line_count=repl.line_count(),
            effective_max_windows=self.max_windows,
            partition_threshold=self.partition_threshold,
            partition_size=self.partition_size,
            partition_blocks_considered=partition_blocks_considered,
            adaptive_windows=self.adaptive_windows,
        )
        return Prediction({"evidence_windows": windows, "metadata": metadata})


__all__ = ["Inspector", "REPLEnvironment", "DEFAULT_MAX_WINDOWS"]
