"""Deterministic task-category routing for the harness pipeline."""

from __future__ import annotations

from .module import tokenize
from .signatures import TaskCategory

# Ordered (priority high -> low) keyword rules. Phrases (containing a space) match
# as substrings; single tokens match a whole token or a token plus a known
# inflectional suffix (see `_INFLECTIONS`), so "errors"/"scheduled"/"compiler"
# route while coincidental prefixes ("agora" vs "ago") and mid-word hits
# ("therapist" vs "api") do not. Unmatched queries fall back to SINGLE_SESSION.
_CATEGORY_RULES: list[tuple[TaskCategory, tuple[str, ...]]] = [
    (
        TaskCategory.CODE,
        (
            "def ",
            "function",
            "traceback",
            "exception",
            "stack trace",
            "compile",
            "regex",
            "bug",
            "error",
            "python",
            "api",
            "code",
        ),
    ),
    (
        TaskCategory.KNOWLEDGE_UPDATE,
        ("no longer", "changed to", "updated", "now use", "i now", "switched", "moved to", "instead of"),
    ),
    (
        TaskCategory.TEMPORAL,
        (
            "how long",
            "when",
            "what date",
            "before",
            "after",
            "yesterday",
            "ago",
            "earliest",
            "latest",
            "first time",
            "last time",
            "year",
            "month",
            "schedule",
        ),
    ),
    (
        TaskCategory.MULTI_SESSION,
        (
            "across",
            "earlier",
            "previously",
            "you said",
            "we discussed",
            "last session",
            "before we",
            "multiple sessions",
            "over time",
        ),
    ),
    (
        TaskCategory.PREFERENCE,
        ("prefer", "favorite", "favourite", "i like", "i love", "i hate", "i dislike", "usually", "enjoy"),
    ),
]


# Suffixes under which a single token still counts as a keyword match. Keeps
# light inflection recall ("error"->"errors", "schedule"->"scheduled",
# "compile"->"compiler") without the unbounded substring/prefix collisions that
# misrouted "therapist"->"api" or "agora"->"ago".
_INFLECTIONS: frozenset[str] = frozenset({"", "s", "es", "ed", "d", "ing", "r", "ly"})


def _token_matches(keyword: str, tokens: set[str]) -> bool:
    """True when some token is ``keyword`` plus an allowed inflectional suffix."""
    return any(tok.startswith(keyword) and tok[len(keyword) :] in _INFLECTIONS for tok in tokens)


def classify_task(query: str) -> TaskCategory:
    """Classify ``query`` into a :class:`TaskCategory` via deterministic rules.

    Returns the first category whose keyword set matches, scanning in priority
    order; defaults to ``SINGLE_SESSION`` when nothing matches.
    """
    lowered = query.lower()
    tokens = set(tokenize(query))
    for category, keywords in _CATEGORY_RULES:
        for kw in keywords:
            if " " in kw or kw.endswith(" "):
                if kw.strip() in lowered:
                    return category
            elif _token_matches(kw, tokens):
                return category
    return TaskCategory.SINGLE_SESSION


__all__ = ["classify_task", "_CATEGORY_RULES"]
