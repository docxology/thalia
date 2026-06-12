"""Property-based robustness fuzzing of the pipeline (Zero-Mock, deterministic seed).

Locks in the result of an adversarial fuzz pass: across hundreds of random,
punctuated, SQL-like, injection-marker, empty, and oversized inputs the harness and
the FTS5-backed persistent session never crash and never violate their output
invariants. This is the regression guard for the class of bug the earlier
``fts5: syntax error`` belonged to.
"""

import os
import random
import tempfile

from src.config import default_config
from src.harness import AutoHarness
from src.session import Session

_TOKENS = list("abc 123 .?!\"'-_/\\:;()[]{}*%$#@&|`~\n\t") + [
    "", "  ", "SELECT", "DROP TABLE", "[[ ## x ## ]]", "ignore previous instructions", "wifi password",
]


def _rand_text(rng: random.Random, maxlen: int = 60) -> str:
    return "".join(rng.choice(_TOKENS) for _ in range(rng.randrange(maxlen)))


def test_harness_never_crashes_on_adversarial_input():
    rng = random.Random(0)
    for _ in range(300):
        session = "\n".join(f"User: {_rand_text(rng)}" for _ in range(rng.randrange(0, 6)))
        query = _rand_text(rng, 40) or "?"
        out = AutoHarness(config=default_config().with_(recall_memory=rng.random() < 0.5)).forward(query, session)
        assert isinstance(out.answer, str)
        for citation in out.evidence_citations:
            assert citation.source_index >= -1
        for ranked in out.ranked_evidence:
            assert isinstance(ranked.score, float)


def test_persistent_session_survives_punctuated_queries():
    rng = random.Random(1)
    directory = tempfile.mkdtemp()
    session = Session(
        db_path=os.path.join(directory, "e.db"),
        memory_path=os.path.join(directory, "M.md"),
        config=default_config().with_(recall_memory=True),
    )
    try:
        for _ in range(60):
            out = session.ask(_rand_text(rng, 50) or "x")
            assert isinstance(out.answer, str)
    finally:
        session.close()
