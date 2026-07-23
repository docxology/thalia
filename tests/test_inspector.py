"""Tests for Stage 0 — the RLM-style Inspector (Zero-Mock)."""

import pytest
from src.signatures import InspectorMetadata
from src.stages.inspector import REPLEnvironment, Inspector

SESSION = "User: my wifi password is bluefish42\nAssistant: noted\nUser: the cat sat on the mat"


class TestREPLEnvironment:
    def test_skips_blank_lines(self):
        repl = REPLEnvironment("a\n\n\nb\n")
        assert repl.line_count() == 2
        assert repl.lines() == ["a", "b"]

    def test_peek(self):
        repl = REPLEnvironment("abcdef")
        assert repl.peek(3) == "abc"

    def test_grep(self):
        repl = REPLEnvironment(SESSION)
        assert repl.grep(["wifi"]) == [0]

    def test_window_offsets_point_into_context(self):
        repl = REPLEnvironment(SESSION)
        win = repl.window(2)
        assert SESSION[win.start : win.end] == "User: the cat sat on the mat"
        assert win.source_index == 2

    def test_window_offsets_skip_trimmed_indentation(self):
        repl = REPLEnvironment("  indented evidence  \n")
        win = repl.window(0)
        assert repl.context[win.start : win.end] == "indented evidence"


class TestInspectorInit:
    def test_non_positive_max_windows_raises(self):
        with pytest.raises(ValueError, match="max_windows must be positive"):
            Inspector(max_windows=0)


class TestInspectorForward:
    def test_grep_anchored_window(self):
        insp = Inspector()
        pred = insp(session_history=SESSION, query="what is the wifi password")
        windows = pred["evidence_windows"]
        assert [w.source_index for w in windows] == [0]
        assert windows[0].relevance > 0.5

    def test_metadata_populated(self):
        insp = Inspector()
        pred = insp(session_history=SESSION, query="what is the wifi password")
        meta = pred["metadata"]
        assert isinstance(meta, InspectorMetadata)
        assert "wifi" in meta.grep_patterns
        assert meta.window_indices == (0,)
        assert meta.session_length == len(SESSION)
        assert meta.confidence > 0.0
        assert meta.line_count == 3
        assert meta.effective_max_windows == insp.max_windows
        assert meta.partition_threshold == insp.partition_threshold
        assert meta.partition_size == insp.partition_size
        assert meta.partition_blocks_considered == 0

    def test_no_lexical_match_yields_no_windows(self):
        insp = Inspector()
        pred = insp(session_history=SESSION, query="quantum chromodynamics theory")
        assert pred["evidence_windows"] == []
        assert pred["metadata"].confidence == 0.0

    def test_stopword_only_query_falls_back_to_all_lines(self):
        insp = Inspector()
        # All query tokens are stop-words -> no grep patterns -> every line kept.
        pred = insp(session_history=SESSION, query="the is a")
        assert len(pred["evidence_windows"]) == 3

    def test_max_windows_cap(self):
        many = "\n".join(f"line about wifi number {i}" for i in range(40))
        insp = Inspector(max_windows=5)
        pred = insp(session_history=many, query="wifi")
        assert len(pred["evidence_windows"]) == 5

    def test_missing_query_arg_raises_type_error(self):
        insp = Inspector()
        with pytest.raises(TypeError):
            insp.forward(session_history=SESSION)


class TestREPLPartition:
    def test_partition_blocks(self):
        from src.stages.inspector import REPLEnvironment

        repl = REPLEnvironment("\n".join(f"line {i}" for i in range(25)))
        blocks = repl.partition(10)
        assert [len(b) for b in blocks] == [10, 10, 5]

    def test_partition_size_non_positive_raises(self):
        from src.stages.inspector import REPLEnvironment

        repl = REPLEnvironment("a\nb")
        with pytest.raises(ValueError, match="block_size must be positive"):
            repl.partition(0)


class TestInspectorRecursion:
    def test_partition_params_validated(self):
        with pytest.raises(ValueError, match="partition_threshold must be positive"):
            Inspector(partition_threshold=0)
        with pytest.raises(ValueError, match="partition_size must be positive"):
            Inspector(partition_size=0)

    def test_long_context_triggers_coarse_filter(self):
        lines = [f"filler content number {i}" for i in range(50)]
        lines[25] = "User: my wifi password is bluefish42"
        session = "\n".join(lines)
        insp = Inspector(partition_threshold=40, partition_size=10)
        pred = insp(session_history=session, query="what is the wifi password")
        indices = [w.source_index for w in pred["evidence_windows"]]
        assert 25 in indices
        assert pred["metadata"].partition_blocks_considered == 5

    def test_short_context_unaffected(self):
        session = "User: my wifi password is bluefish42\nAssistant: noted"
        insp = Inspector(partition_threshold=40)
        pred = insp(session_history=session, query="what is the wifi password")
        assert pred["evidence_windows"][0].source_index == 0


class TestAdaptiveMaxWindows:
    def test_compact_context_floors_at_base(self):
        from src.stages.inspector import adaptive_max_windows

        assert adaptive_max_windows(n_lines=4, base=15, ratio=5) == 15
        assert adaptive_max_windows(n_lines=75, base=15, ratio=5) == 15  # 75//5 == 15, floored

    def test_floor_to_scaling_transition_boundary(self):
        from src.stages.inspector import adaptive_max_windows

        # Pin the exact crossover so an off-by-one in the floor/scaling split fails.
        assert adaptive_max_windows(n_lines=79, base=15, ratio=5) == 15  # 79//5 == 15, still floored
        assert adaptive_max_windows(n_lines=80, base=15, ratio=5) == 16  # 80//5 == 16, scaling wins

    def test_long_context_scales_with_size(self):
        from src.stages.inspector import adaptive_max_windows

        assert adaptive_max_windows(n_lines=500, base=15, ratio=5) == 100
        assert adaptive_max_windows(n_lines=550, base=15, ratio=5) == 110

    def test_monotonic_and_ratio_guarded(self):
        from src.stages.inspector import adaptive_max_windows

        assert adaptive_max_windows(1000, 15, 5) >= adaptive_max_windows(500, 15, 5)
        assert adaptive_max_windows(500, 15, ratio=0) >= 15  # ratio<=0 guarded, no ZeroDivision
