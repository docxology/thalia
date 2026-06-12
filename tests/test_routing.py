"""Tests for deterministic task routing (Zero-Mock)."""

import pytest
from src.routing import classify_task
from src.signatures import TaskCategory


@pytest.mark.parametrize(
    "query,expected",
    [
        ("what is the wifi password", TaskCategory.SINGLE_SESSION),
        ("when is the car service", TaskCategory.TEMPORAL),
        ("what is my favorite language", TaskCategory.PREFERENCE),
        ("what error does the code raise", TaskCategory.CODE),
        ("what did we discuss across sessions", TaskCategory.MULTI_SESSION),
        ("I no longer live there; where do I live now", TaskCategory.KNOWLEDGE_UPDATE),
    ],
)
def test_classify_task(query, expected):
    assert classify_task(query) is expected


@pytest.mark.parametrize(
    "query,expected",
    [
        # Neither mid-word substrings nor coincidental prefixes may trigger a
        # category (regression: suffix-controlled token matching). Previously
        # "therapist"/"rapid" hit "api" -> CODE and "dragon"/"agora" hit "ago"
        # -> TEMPORAL.
        ("I saw my therapist today", TaskCategory.SINGLE_SESSION),
        ("we had a rapid response", TaskCategory.SINGLE_SESSION),
        ("the dragon flew over the wall", TaskCategory.SINGLE_SESSION),
        ("agora is a nice word", TaskCategory.SINGLE_SESSION),
    ],
)
def test_classify_task_no_false_positive(query, expected):
    assert classify_task(query) is expected


@pytest.mark.parametrize(
    "query,expected",
    [
        # Inflected forms (keyword + allowed suffix) must still route.
        ("what errors did the build raise", TaskCategory.CODE),  # error + s
        ("when is the meeting scheduled", TaskCategory.TEMPORAL),  # schedule + d
        ("these are a few of my favorites", TaskCategory.PREFERENCE),  # favorite + s
    ],
)
def test_classify_task_inflection_recall(query, expected):
    assert classify_task(query) is expected
