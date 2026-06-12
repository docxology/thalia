"""Tests for the gated consolidation logic (Zero-Mock)."""

from src.memory.consolidation import (
    ConsolidationAction,
    ConsolidationCriteria,
    consolidate_snapshot,
    decide_action,
    derive_memory_delta,
    should_consolidate,
)
from src.signatures import EpisodicEntry


class TestCriteria:
    def test_any_met_false_when_all_false(self):
        assert ConsolidationCriteria().any_met() is False

    def test_any_met_true_on_session_ending(self):
        assert ConsolidationCriteria(session_ending=True).any_met() is True

    def test_any_met_true_on_novel(self):
        assert ConsolidationCriteria(novel_task_class=True).any_met() is True

    def test_any_met_true_on_explicit(self):
        assert ConsolidationCriteria(explicit_request=True).any_met() is True


class TestShouldConsolidate:
    def test_requires_both_flag_and_criterion(self):
        assert should_consolidate(True, ConsolidationCriteria(session_ending=True)) is True

    def test_flag_alone_insufficient(self):
        assert should_consolidate(True, ConsolidationCriteria()) is False

    def test_criterion_alone_insufficient(self):
        assert should_consolidate(False, ConsolidationCriteria(session_ending=True)) is False


class TestDecideAction:
    def test_none_when_gate_closed(self):
        assert decide_action(False, ConsolidationCriteria(), False) is ConsolidationAction.NONE

    def test_append_when_open_no_existing_memory(self):
        action = decide_action(True, ConsolidationCriteria(novel_task_class=True), False)
        assert action is ConsolidationAction.APPEND_MEMORY

    def test_update_when_explicit_and_memory_exists(self):
        action = decide_action(True, ConsolidationCriteria(explicit_request=True), True)
        assert action is ConsolidationAction.UPDATE_MEMORY

    def test_append_when_explicit_but_no_memory(self):
        action = decide_action(True, ConsolidationCriteria(explicit_request=True), False)
        assert action is ConsolidationAction.APPEND_MEMORY


class TestDeriveMemoryDelta:
    def test_delta_cites_source_turn(self):
        entry = EpisodicEntry(turn_id=7, query="where do I live", answer="Lisbon", task_category="knowledge_update")
        delta = derive_memory_delta(entry)
        assert "turn 7" in delta
        assert "knowledge_update" in delta
        assert "Lisbon" in delta

    def test_delta_flattens_newlines(self):
        entry = EpisodicEntry(turn_id=1, query="q", answer="line1\nline2")
        assert "\n" not in derive_memory_delta(entry).rstrip("\n")


class TestConsolidateSnapshot:
    def test_empty_deltas_returns_unchanged(self):
        assert consolidate_snapshot("existing", []) == "existing"

    def test_creates_heading_when_empty(self):
        out = consolidate_snapshot("", ["- fact"])
        assert "# MEMORY" in out
        assert "## Consolidated Memory" in out
        assert "- fact" in out

    def test_appends_to_existing_without_overwriting(self):
        base = "# MEMORY\n\n## Consolidated Memory\n- old fact\n"
        out = consolidate_snapshot(base, ["- new fact"])
        assert "- old fact" in out
        assert "- new fact" in out
        # Heading not duplicated.
        assert out.count("## Consolidated Memory") == 1

    def test_adds_heading_to_nonempty_without_section(self):
        out = consolidate_snapshot("# Some notes", ["- fact"])
        assert "## Consolidated Memory" in out
        assert "# Some notes" in out

    def test_blank_deltas_filtered(self):
        out = consolidate_snapshot("", ["- keep", "   "])
        assert "- keep" in out
