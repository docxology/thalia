"""Tests for Stage 3 — the episodic-first Memory Gate (Zero-Mock)."""

from src.memory.episodic_store import EpisodicStore
from src.signatures import EpisodicEntry, EvidenceCitation, TaskCategory
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

    def test_auto_turn_id_never_collides_with_explicit(self):
        """Mixing an explicit turn_id with later auto-assigned ones must not collide.

        With the old ``count()`` default this raised ``ValueError``: an explicit
        ``turn_id=1`` into an empty store makes ``count() == 1``, so the next
        auto-assign would reuse id 1 (which ``EpisodicStore.append`` rejects). The
        ``max_turn_id() + 1`` default is collision-proof.
        """
        gate = MemoryGate()
        # Explicit turn_id=1 into an empty store (count() is now 1, not 2).
        gate(
            query="q-explicit",
            answer="a",
            evidence_citations=[],
            requires_consolidation=False,
            turn_id=1,
        )
        # Auto-assign: must skip past the explicit id 1, not reuse it.
        pred_auto1 = gate(
            query="q-auto-1",
            answer="a",
            evidence_citations=[],
            requires_consolidation=False,
        )
        assert pred_auto1["episodic_entry"].turn_id == 2
        # A second auto-assign keeps incrementing collision-free.
        pred_auto2 = gate(
            query="q-auto-2",
            answer="a",
            evidence_citations=[],
            requires_consolidation=False,
        )
        assert pred_auto2["episodic_entry"].turn_id == 3
        stored_ids = [entry.turn_id for entry in gate.store.all()]
        assert stored_ids == [1, 2, 3]
        assert len(stored_ids) == len(set(stored_ids))


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

    def test_existing_store_categories_are_not_novel_after_reopen(self):
        store = EpisodicStore()
        store.append(
            EpisodicEntry(
                turn_id=0,
                query="previous temporal query",
                answer="previous answer",
                evidence_indices=(),
                task_category=TaskCategory.TEMPORAL.value,
            )
        )
        gate = MemoryGate(episodic_store=store)

        pred = gate(
            query="another temporal query",
            answer="another answer",
            evidence_citations=[],
            requires_consolidation=True,
            task_category=TaskCategory.TEMPORAL,
            explicit_request=False,
            session_ending=False,
        )

        assert pred["consolidation_action"] == "none"
        assert store.count() == 2

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
