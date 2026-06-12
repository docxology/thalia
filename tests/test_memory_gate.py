"""Tests for Stage 3 — the episodic-first Memory Gate (Zero-Mock)."""

from src.memory.episodic_store import EpisodicStore
from src.signatures import EvidenceCitation, TaskCategory
from src.stages.memory_gate import MemoryGate


def _citations(*indices):
    return [EvidenceCitation(source_index=i, excerpt=f"e{i}") for i in indices]


class TestAlwaysAppend:
    def test_episode_always_recorded_even_without_consolidation(self):
        gate = MemoryGate()
        gate(
            query="q",
            answer="a",
            evidence_citations=_citations(1, 2),
            requires_consolidation=False,
            task_category=TaskCategory.SINGLE_SESSION,
        )
        assert gate.store.count() == 1
        stored = gate.store.all()[0]
        assert stored.evidence_indices == (1, 2)

    def test_turn_id_defaults_to_count(self):
        gate = MemoryGate()
        pred = gate(
            query="q",
            answer="a",
            evidence_citations=[],
            requires_consolidation=False,
        )
        assert pred["episodic_entry"].turn_id == 0


class TestConsolidationGate:
    def test_no_consolidation_when_flag_false(self):
        gate = MemoryGate()
        pred = gate(
            query="remember this",  # explicit marker present...
            answer="a",
            evidence_citations=[],
            requires_consolidation=False,  # ...but flag is False -> gate closed
            session_ending=True,
        )
        assert pred["consolidation_action"] == "none"
        assert pred["memory_delta"] == ""

    def test_no_consolidation_when_no_criteria(self):
        gate = MemoryGate()
        # Second turn of same category: not novel, not ending, not explicit.
        gate(query="q1", answer="a1", evidence_citations=[], requires_consolidation=True)
        pred = gate(
            query="q2",
            answer="a2",
            evidence_citations=[],
            requires_consolidation=True,
            explicit_request=False,
        )
        assert pred["consolidation_action"] == "none"

    def test_append_memory_on_novel_class_with_flag(self):
        gate = MemoryGate()
        pred = gate(
            query="first temporal q",
            answer="a",
            evidence_citations=[],
            requires_consolidation=True,
            task_category=TaskCategory.TEMPORAL,  # novel this session
        )
        assert pred["consolidation_action"] == "append_memory"
        assert "temporal" in gate.memory_md

    def test_update_memory_on_explicit_request_with_existing_memory(self):
        gate = MemoryGate(memory_md="# MEMORY\n\nexisting content")
        pred = gate(
            query="please remember the code is 99",
            answer="code is 99",
            evidence_citations=[],
            requires_consolidation=True,
            explicit_request=True,
        )
        assert pred["consolidation_action"] == "update_memory"

    def test_explicit_request_autodetected_from_query(self):
        gate = MemoryGate()
        pred = gate(
            query="note that the meeting moved",
            answer="meeting moved",
            evidence_citations=[],
            requires_consolidation=True,
        )
        # Auto-detected explicit marker triggers append (no prior memory).
        assert pred["consolidation_action"] == "append_memory"

    def test_shared_episodic_store(self):
        store = EpisodicStore()
        gate = MemoryGate(episodic_store=store)
        gate(query="q", answer="a", evidence_citations=[], requires_consolidation=False)
        assert store.count() == 1

    def test_task_category_string_accepted(self):
        gate = MemoryGate()
        pred = gate(
            query="q",
            answer="a",
            evidence_citations=[],
            requires_consolidation=False,
            task_category="single_session",  # plain string instead of enum
        )
        assert pred["episodic_entry"].task_category == "single_session"
