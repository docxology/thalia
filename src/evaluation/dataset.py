"""Synthetic LongMemEval-style evaluation dataset."""

from __future__ import annotations

import random

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
    "thing": ["programming language", "coffee", "editor", "keyboard", "season", "city", "framework", "cuisine"],
    "value": ["Rust", "espresso", "Vim", "the Model M", "autumn", "Lisbon", "DSPy", "Thai food"],
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
        t, v = pick("thing"), pick("value")
        gold, query, answer = f"my favorite {t} is {v}", f"What is my favorite {t}?", f"favorite {t} is {v}"
    elif category is TaskCategory.CODE:
        s, er, c = pick("script"), pick("error"), pick("cond")
        gold, query, answer = f"{s} raises {er} when {c}", f"What error does {s} raise?", f"{er} when {c}"
    elif category is TaskCategory.MULTI_SESSION:
        a, m = pick("attr"), pick("amount")
        gold, query, answer = f"earlier I said my {a} was {m}", f"What {a} did I mention across our sessions?", f"{a} was {m}"
    elif category is TaskCategory.KNOWLEDGE_UPDATE:
        pv, old, new = pick("place_verb"), pick("old_place"), pick("new_place")
        gold, query, answer = f"I used to {pv} {old}; I now {pv} {new}", f"Where do I now {pv}?", f"now {pv} {new}"
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
    return examples


def _distractor_lines(query: str, n: int) -> str:
    """Build lexical false-friend lines (Sen et al. 2026 Experiment 2 noise)."""
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
    )


__all__ = ["build_demo_dataset", "build_large_dataset", "with_noise"]
