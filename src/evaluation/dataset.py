"""Synthetic LongMemEval-style evaluation dataset."""

from __future__ import annotations

import random
from dataclasses import replace
from collections import Counter

from ..compiler.metrics import EvalExample
from ..module import tokenize
from ..signatures import TaskCategory


def build_demo_dataset() -> list[EvalExample]:
    """Return a deterministic LongMemEval-style dataset across task categories."""
    return [
        EvalExample(
            session_history=(
                "User: I booked the dentist for March 3rd.\n"
                "Assistant: Noted, dentist on March 3rd.\n"
                "User: Also the car service is on April 12th.\n"
                "Assistant: Got it, car service April 12th."
            ),
            query="When is the car service scheduled?",
            expected_answer="car service April 12th",
            expected_source_indices=(3,),
            task_category=TaskCategory.TEMPORAL,
        ),
        EvalExample(
            session_history=(
                "User: My favorite programming language is Rust.\n"
                "Assistant: Rust is a great choice.\n"
                "User: I usually drink green tea in the morning.\n"
                "Assistant: Green tea, noted."
            ),
            query="What is my favorite programming language?",
            expected_answer="favorite programming language is Rust",
            expected_source_indices=(0,),
            task_category=TaskCategory.PREFERENCE,
        ),
        EvalExample(
            session_history=(
                "User: The deploy script lives in scripts/deploy.py.\n"
                "Assistant: Understood.\n"
                "User: It raises a KeyError when CONFIG is missing.\n"
                "Assistant: That KeyError comes from an unset CONFIG env var."
            ),
            query="What error does the deploy code raise without CONFIG?",
            expected_answer="KeyError when CONFIG is missing",
            expected_source_indices=(2,),
            task_category=TaskCategory.CODE,
        ),
        EvalExample(
            session_history=(
                "User: Earlier I said my budget was 5000 dollars.\n"
                "Assistant: Budget 5000 recorded.\n"
                "User: We discussed the vendor shortlist last session.\n"
                "Assistant: Yes, three vendors across our sessions."
            ),
            query="What budget did I mention across our sessions?",
            expected_answer="budget was 5000 dollars",
            expected_source_indices=(0,),
            task_category=TaskCategory.MULTI_SESSION,
        ),
        EvalExample(
            session_history=(
                "User: I used to live in Berlin.\n"
                "Assistant: Berlin, noted.\n"
                "User: I no longer live there; I now live in Lisbon.\n"
                "Assistant: Updated: you now live in Lisbon."
            ),
            query="Where do I now live? Please remember this.",
            expected_answer="now live in Lisbon",
            expected_source_indices=(2, 3),
            task_category=TaskCategory.KNOWLEDGE_UPDATE,
        ),
        EvalExample(
            session_history=(
                "User: The wifi password is bluefish42.\n"
                "Assistant: Stored the wifi password.\n"
                "User: The guest code is 7781.\n"
                "Assistant: Guest code 7781 noted."
            ),
            query="What is the wifi password?",
            expected_answer="wifi password is bluefish42",
            expected_source_indices=(0,),
            task_category=TaskCategory.SINGLE_SESSION,
        ),
    ]


# Entity pools for the seeded large-dataset generator. A fixed seed makes the whole
# dataset bit-reproducible, so "larger" does not cost determinism.
_POOLS = {
    "event": ["car service", "dentist appointment", "team offsite", "flight", "product launch", "tax filing", "house move", "conference talk"],
    "date": ["April 12th", "March 3rd", "June 9th", "next Tuesday", "the 21st", "July 4th", "October 30th", "May 1st"],
    "thing": ["programming language", "morning drink", "editor", "keyboard", "season", "city", "framework", "cuisine"],
    "value": ["Rust", "green tea", "Vim", "the Model M", "autumn", "Lisbon", "DSPy", "Thai food"],
    "script": ["the deploy script", "the migration job", "the importer", "the auth module", "the billing worker"],
    "error": ["a KeyError", "a TimeoutError", "a ValueError", "a NullPointer", "a 500"],
    "cond": ["CONFIG is missing", "the token expires", "the input is empty", "the DB is down", "the cache is cold"],
    "attr": ["budget", "headcount", "deadline", "vendor", "scope"],
    "amount": ["5000 dollars", "twelve people", "the 30th", "three suppliers", "two milestones"],
    "place_verb": ["live in", "work at", "bank with", "commute to"],
    "old_place": ["Berlin", "the old office", "First National", "the north route"],
    "new_place": ["Lisbon", "the river campus", "Credit Union", "the bridge route"],
    "secret": ["wifi password", "guest code", "vault code", "API key", "door pin"],
    "secret_val": ["bluefish42", "7781", "alpha-seven-nine", "sk-9920", "4417"],
}

_PREFERENCE_PAIRS = tuple(zip(_POOLS["thing"], _POOLS["value"]))
_ATTRIBUTE_PAIRS = (
    ("budget", "5000 dollars"),
    ("headcount", "twelve people"),
    ("deadline", "the 30th"),
    ("vendor", "three suppliers"),
    ("scope", "two milestones"),
)
_PLACE_PAIRS = (
    ("live in", "Berlin", "Lisbon"),
    ("work at", "the old office", "the river campus"),
    ("bank with", "First National", "Credit Union"),
    ("commute to", "the north route", "the bridge route"),
)


def _generated_example(category: TaskCategory, rng: random.Random) -> EvalExample:
    """Build one realistic-but-synthetic example for ``category`` from seeded pools.

    The gold fact is placed at a known user-turn index with a distractor turn, so the
    structure (discriminative line + distractor, annotated gold index) matches
    :func:`build_demo_dataset` and every downstream stage scores it the same way.
    """
    pick = lambda key: rng.choice(_POOLS[key])  # noqa: E731
    if category is TaskCategory.TEMPORAL:
        e, d = pick("event"), pick("date")
        gold, query, answer = f"the {e} is on {d}", f"When is the {e}?", f"{e} {d}"
    elif category is TaskCategory.PREFERENCE:
        t, v = rng.choice(_PREFERENCE_PAIRS)
        gold, query, answer = f"my favorite {t} is {v}", f"What is my favorite {t}?", f"favorite {t} is {v}"
    elif category is TaskCategory.CODE:
        s, er, c = pick("script"), pick("error"), pick("cond")
        gold, query, answer = f"{s} raises {er} when {c}", f"What error does {s} raise?", f"{er} when {c}"
    elif category is TaskCategory.MULTI_SESSION:
        a, m = rng.choice(_ATTRIBUTE_PAIRS)
        gold, query, answer = f"earlier I said my {a} was {m}", f"What {a} did I mention across our sessions?", f"{a} was {m}"
    elif category is TaskCategory.KNOWLEDGE_UPDATE:
        pv, old, new = rng.choice(_PLACE_PAIRS)
        question_word = {"live in": "live", "work at": "work", "bank with": "bank", "commute to": "commute"}[pv]
        gold, query, answer = f"I used to {pv} {old}; I now {pv} {new}", f"Where do I now {question_word}?", f"now {pv} {new}"
    else:  # SINGLE_SESSION
        s, v = pick("secret"), pick("secret_val")
        gold, query, answer = f"the {s} is {v}", f"What is the {s}?", f"{s} is {v}"

    distractor_secret, distractor_val = pick("secret"), pick("secret_val")
    history = (
        f"User: {gold}.\n"
        f"Assistant: Noted.\n"
        f"User: Unrelated, the {distractor_secret} is {distractor_val}.\n"
        f"Assistant: Got it."
    )
    return EvalExample(
        session_history=history,
        query=query,
        expected_answer=answer,
        expected_source_indices=(0,),
        task_category=category,
    )


def build_large_dataset(per_category: int = 10, seed: int = 0) -> list[EvalExample]:
    """A seeded, balanced, deterministic dataset (``per_category`` per class).

    Realistic-but-synthetic: it is larger and varied enough for per-category means and
    bootstrap CIs, while a fixed ``seed`` keeps it bit-reproducible. It is *not* human
    data, so it tests the machinery's scaling and variance, not real-world accuracy.
    """
    rng = random.Random(seed)
    examples: list[EvalExample] = []
    for category in TaskCategory:
        for _ in range(per_category):
            examples.append(_generated_example(category, rng))
    return [
        replace(
            example,
            example_id=f"large-s{seed}-{(example.task_category or TaskCategory.SINGLE_SESSION).value}-{index:04d}",
            stratum="literal_lexical",
            seed=seed,
        )
        for index, example in enumerate(examples)
    ]


_RESEARCH_STRATA = {
    TaskCategory.SINGLE_SESSION: "literal_lexical",
    TaskCategory.TEMPORAL: "literal_lexical",
    TaskCategory.PREFERENCE: "semantic_paraphrase",
    TaskCategory.CODE: "noisy_long_context",
    TaskCategory.MULTI_SESSION: "multi_hop_update",
    TaskCategory.KNOWLEDGE_UPDATE: "multi_hop_update",
}


def _research_variant(example: EvalExample, category: TaskCategory, index: int, seed: int) -> EvalExample:
    """Build a construct-labelled research variant without changing the demo."""
    stratum = _RESEARCH_STRATA[category]
    metadata: dict[str, str] = {"construct": stratum, "synthetic": "true"}
    if stratum == "semantic_paraphrase":
        # Keep one content anchor so the Inspector can expose a candidate, while
        # replacing the lexical relation that directly states the preference.
        # This tests retrieval under controlled surface divergence, not language
        # understanding in the population.
        thing = example.query.removeprefix("What is my favorite ").rstrip("?")
        query = f"Which option do I tend to favor as my {thing}?"
        metadata.update({"surface_relation": "paraphrase", "anchor": thing})
        example = replace(example, query=query)
    elif stratum == "noisy_long_context":
        # Place deterministic false friends before and after the gold transcript;
        # the exact count varies by index so the stratum has measurable dispersion.
        n_distractors = 8 + (index % 5) * 4
        example = with_noise(example, n_distractors)
        # The base generator always has four lines before the appended negative
        # block. Persist the exact flattened line identities so a ledger reader
        # can audit which observations were intended as false friends.
        negative_indices = tuple(range(4, 4 + n_distractors))
        metadata.update(
            {
                "negative_lines": str(n_distractors),
                "negative_line_indices": ",".join(str(value) for value in negative_indices),
                "negative_pattern": "query_token_false_friend",
            }
        )
    elif stratum == "multi_hop_update":
        if category is TaskCategory.MULTI_SESSION:
            # The answer value is in the earlier line; the later line supplies the
            # cross-session confirmation. Both source records are required by the
            # research construct and are retained in the gold source set.
            first = example.session_history.splitlines()[0]
            attribute = example.expected_answer.split(" was ", 1)[0]
            history = (
                f"{first}\n"
                "Assistant: Earlier note recorded.\n"
                f"User: Across sessions, I confirmed the same {attribute}.\n"
                f"Assistant: Cross-session {attribute} confirmation recorded."
            )
        else:
            # Separate the old and new state into two source records.  A single
            # combined line would be a literal extraction task, not an update.
            gold = example.session_history.splitlines()[0].removeprefix("User: ").rstrip(".")
            old, new = (gold.split("; ", 1) + [gold])[:2]
            history = (
                f"User: {old}.\n"
                "Assistant: Earlier state recorded.\n"
                f"User: {new}; this supersedes the earlier state.\n"
                "Assistant: Current state updated."
            )
        metadata.update({"source_requirement": "multiple_records", "supersession": "explicit"})
        example = replace(example, session_history=history, expected_source_indices=(0, 2))
    return replace(
        example,
        example_id=f"research-s{seed}-{category.value}-{stratum}-{index:04d}",
        stratum=stratum,
        seed=seed,
        metadata=tuple(sorted(metadata.items())),
    )


def validate_dataset(examples: list[EvalExample]) -> list[EvalExample]:
    """Validate stable research identifiers and return the input unchanged."""
    if not examples:
        raise ValueError("examples must be non-empty")
    ids = [example.example_id for example in examples]
    if any(not value for value in ids):
        raise ValueError("every research example must have a stable example_id")
    duplicates = [key for key, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate example_id values: {duplicates[:3]}")
    return examples


def build_research_dataset(per_category: int = 10, seed: int = 0) -> list[EvalExample]:
    """Build the seeded, stratified research dataset used by the audit.

    The six task categories remain balanced.  Four deterministic difficulty strata
    make the audit capable of exposing method-specific failures; all examples are
    synthetic and should not be read as population estimates.
    """
    if per_category <= 0:
        raise ValueError("per_category must be positive")
    rng = random.Random(seed)
    examples: list[EvalExample] = []
    for category in TaskCategory:
        for index in range(per_category):
            examples.append(_research_variant(_generated_example(category, rng), category, index, seed))
    return validate_dataset(examples)


def _distractor_lines(query: str, n: int) -> str:
    """Build lexical false-friend lines (Sen et al. 2026 Experiment 2 noise)."""
    # Preserve the established demo-noise construction: the six-example
    # regression set intentionally includes the query's first content-like tokens
    # (including function words) so its published noise trajectory remains stable.
    # Research-only construct metadata records the exact false-friend lines.
    content = [t for t in tokenize(query) if len(t) > 2][:3] or ["topic"]
    lines = []
    for i in range(n):
        token = content[i % len(content)]
        lines.append(f"User: As an aside about {token}, unrelated remark {i} also says {token}.")
    return "\n".join(lines)


def with_noise(example: EvalExample, n_distractors: int) -> EvalExample:
    """Return a copy with distractors appended (gold indices unchanged)."""
    if n_distractors <= 0:
        return example
    noisy_history = example.session_history + "\n" + _distractor_lines(example.query, n_distractors)
    return EvalExample(
        session_history=noisy_history,
        query=example.query,
        expected_answer=example.expected_answer,
        expected_source_indices=example.expected_source_indices,
        task_category=example.task_category,
        example_id=example.example_id,
        stratum=example.stratum,
        seed=example.seed,
        metadata=example.metadata,
    )


__all__ = [
    "build_demo_dataset",
    "build_large_dataset",
    "build_research_dataset",
    "validate_dataset",
    "with_noise",
]
