"""Append-only episodic store backed by SQLite (+ FTS5 when available).

Raw episodes are first-class evidence (Zhang et al., 2026): the store exposes
``append`` / ``get`` / ``all`` / ``search`` / ``count`` but deliberately offers no
update or delete of existing episodes. Full-text search uses SQLite's FTS5 module
when the local build provides it, falling back to a ``LIKE`` scan otherwise —
either way the API and results ordering are deterministic.
"""

from __future__ import annotations

import re
import sqlite3

from ..signatures import EpisodicEntry


def _fts5_available(connection: sqlite3.Connection) -> bool:
    """Probe whether this SQLite build supports the FTS5 extension."""
    try:
        connection.execute("CREATE VIRTUAL TABLE temp._fts5_probe USING fts5(x)")
        connection.execute("DROP TABLE temp._fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _encode_indices(indices: tuple[int, ...]) -> str:
    """Serialize evidence indices to a comma-joined string."""
    return ",".join(str(i) for i in indices)


def _decode_indices(blob: str) -> tuple[int, ...]:
    """Parse a comma-joined string back to a tuple of ints."""
    if not blob:
        return ()
    return tuple(int(part) for part in blob.split(",") if part)


def _search_terms(query: str) -> list[str]:
    """Tokenize a natural-language query into FTS/LIKE-safe terms."""
    return re.findall(r"[0-9a-z]+", query.lower())


def _fts_match_expression(query: str, operator: str = "OR") -> str:
    """Build a safe FTS5 MATCH expression from natural text.

    FTS5 treats punctuation such as ``?``, ``-``, and quotes as query syntax. THALIA
    search accepts natural-language questions, so it strips to bare alphanumeric
    tokens and joins them with an explicit operator. The default ``OR`` preserves the
    existing broad-recall behavior.
    """
    op = operator.upper()
    if op not in {"OR", "AND"}:
        raise ValueError(f"operator must be OR or AND, got {operator!r}")
    return f" {op} ".join(_search_terms(query))


class EpisodicStore:
    """SQLite-backed, append-only store of raw conversational episodes.

    Args:
        db_path: Path to the SQLite database file, or ``":memory:"`` (default) for
            an ephemeral in-memory store.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self.fts_available = _fts5_available(self._conn)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create the episodes table (and FTS5 mirror if available)."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                turn_id INTEGER PRIMARY KEY,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                evidence_indices TEXT NOT NULL DEFAULT '',
                task_category TEXT NOT NULL DEFAULT 'single_session'
            )
            """
        )
        if self.fts_available:
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts "
                "USING fts5(query, answer, content='episodes', content_rowid='turn_id')"
            )
        self._conn.commit()

    def append(self, entry: EpisodicEntry) -> None:
        """Append a raw episode. Raises on duplicate ``turn_id`` (no overwrite).

        Args:
            entry: The episode to persist.

        Raises:
            ValueError: If an episode with the same ``turn_id`` already exists.
        """
        try:
            self._conn.execute(
                "INSERT INTO episodes (turn_id, query, answer, evidence_indices, task_category) VALUES (?, ?, ?, ?, ?)",
                (
                    entry.turn_id,
                    entry.query,
                    entry.answer,
                    _encode_indices(entry.evidence_indices),
                    entry.task_category,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"episode turn_id={entry.turn_id} already exists; episodes are append-only and never overwritten"
            ) from exc
        if self.fts_available:
            self._conn.execute(
                "INSERT INTO episodes_fts (rowid, query, answer) VALUES (?, ?, ?)",
                (entry.turn_id, entry.query, entry.answer),
            )
        self._conn.commit()

    def get(self, turn_id: int) -> EpisodicEntry | None:
        """Return the episode with ``turn_id`` or None if absent."""
        row = self._conn.execute("SELECT * FROM episodes WHERE turn_id = ?", (turn_id,)).fetchone()
        return self._row_to_entry(row) if row else None

    def all(self) -> list[EpisodicEntry]:
        """Return every episode ordered by ascending ``turn_id``."""
        rows = self._conn.execute("SELECT * FROM episodes ORDER BY turn_id").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count(self) -> int:
        """Return the number of stored episodes."""
        row = self._conn.execute("SELECT COUNT(*) AS n FROM episodes").fetchone()
        return int(row["n"])

    def max_turn_id(self) -> int:
        """Return the largest stored ``turn_id``, or ``-1`` when the store is empty.

        Used to derive a collision-proof next turn id (``max_turn_id() + 1``). Unlike
        ``count()``, this never reuses an id already taken by an explicitly-assigned
        episode, so explicit and auto-assigned turn ids can be mixed safely.
        """
        row = self._conn.execute("SELECT MAX(turn_id) AS m FROM episodes").fetchone()
        return int(row["m"]) if row["m"] is not None else -1

    def search(self, query: str, limit: int = 10) -> list[EpisodicEntry]:
        """Full-text search over stored episodes.

        Uses FTS5 ``MATCH`` when available, else a case-insensitive ``LIKE`` scan
        over query+answer. Results order by relevance (FTS) or ascending turn_id
        (LIKE) for determinism.

        Args:
            query: Free-text search string.
            limit: Maximum number of episodes to return.

        Returns:
            Matching episodes (possibly empty).
        """
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        # Reduce the query to bare alphanumeric tokens. This mirrors FTS5's own
        # tokenizer and, critically, strips characters FTS5 treats as MATCH syntax
        # (``.``, ``?``, ``-``, ``"``, ...) — a raw natural-language query such as
        # "What is the wifi password?" otherwise raises an fts5 syntax error.
        terms = _search_terms(query)
        if not terms:
            return []

        if self.fts_available:
            match_expr = _fts_match_expression(query)
            rows = self._conn.execute(
                "SELECT e.* FROM episodes_fts f JOIN episodes e ON e.turn_id = f.rowid "
                "WHERE episodes_fts MATCH ? ORDER BY rank LIMIT ?",
                (match_expr, limit),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]

        like_clauses = " OR ".join(["query LIKE ? OR answer LIKE ?"] * len(terms))
        params: list[str] = []
        for term in terms:
            params.extend([f"%{term}%", f"%{term}%"])
        rows = self._conn.execute(
            f"SELECT * FROM episodes WHERE {like_clauses} ORDER BY turn_id LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    # -- Context manager protocol --------------------------------------------------
    # Enables ``with EpisodicStore(...) as store:`` so the connection is always
    # closed even when an exception propagates mid-turn.
    def __enter__(self) -> "EpisodicStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> EpisodicEntry:
        return EpisodicEntry(
            turn_id=int(row["turn_id"]),
            query=row["query"],
            answer=row["answer"],
            evidence_indices=_decode_indices(row["evidence_indices"]),
            task_category=row["task_category"],
        )


__all__ = ["EpisodicStore"]
