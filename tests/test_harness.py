"""Tests for the composed AutoHarness pipeline (Zero-Mock, full integration)."""

import pytest
from src.config import HarnessConfig, default_config
from src.evaluation import build_demo_dataset
from src.harness import AutoHarness, build_run_fn
from src.llm import CallableLM
from src.stages.reasoner import Reasoner
from src.stages.retriever import Retriever
from src.signatures import HarnessOutput, MemorySnapshot, TaskCategory

SESSION = "User: my wifi password is bluefish42\nAssistant: noted the wifi password\nUser: the guest code is 7781"


class TestConstruction:
    def test_negative_start_turn_raises(self):
        with pytest.raises(ValueError, match="start_turn must be non-negative"):
            AutoHarness(start_turn=-1)

    def test_start_turn_applied(self):
        h = AutoHarness(start_turn=5)
        out = h.forward("q about wifi", "User: wifi password is x")
        assert out.memory_written is not None
        assert out.memory_written.turn_id == 5


class TestForward:
    def test_returns_harness_output(self):
        out = AutoHarness().forward("what is the wifi password", SESSION)
        assert isinstance(out, HarnessOutput)
        # The deterministic extractive LM grounds in a wifi-password evidence line.
        assert "wifi" in out.answer.lower() and "password" in out.answer.lower()
        assert out.inspector_metadata is not None

    def test_classifies_task(self):
        out = AutoHarness().forward("when is the meeting", SESSION)
        assert out.task_category is TaskCategory.TEMPORAL

    def test_citations_present(self):
        out = AutoHarness().forward("what is the wifi password", SESSION)
        assert len(out.evidence_citations) >= 1

    def test_ranked_evidence_populated(self):
        out = AutoHarness().forward("what is the wifi password", SESSION)
        assert len(out.ranked_evidence) >= 1

    def test_episode_recorded(self):
        h = AutoHarness()
        h.forward("what is the wifi password", SESSION)
        assert h.memory_gate.store.count() == 1

    def test_turn_id_increments(self):
        h = AutoHarness()
        h.forward("q1 wifi", SESSION)
        out2 = h.forward("q2 guest", SESSION)
        assert out2.memory_written is not None
        assert out2.memory_written.turn_id == 1

    def test_exposed_stages_execute_across_turns(self):
        prompts = []
        history = "\n".join(f"User: wifi password bluefish42 entry {index}" for index in range(4))

        def complete(prompt):
            prompts.append(prompt)
            return "wifi password bluefish42"

        with AutoHarness(start_turn=7) as harness:
            inspector = harness.inspector
            retriever = harness.retriever
            reasoner = harness.reasoner
            gate = harness.memory_gate
            reasoner.lm = CallableLM(complete)
            retriever.top_k = 1
            first = harness.forward("what is the wifi password", history)
            assert len(first.ranked_evidence) == 1
            assert len(prompts) == 1
            assert first.answer == "wifi password bluefish42"
            assert first.memory_written.turn_id == 7

            retriever.top_k = 3
            reasoner.max_evidence = 1
            second = harness.forward("what is the wifi password", history)
            assert len(second.ranked_evidence) == 3
            assert len(second.evidence_citations) == 1
            assert len(prompts) == 2
            assert second.memory_written.turn_id == 8
            assert harness.inspector is inspector
            assert harness.retriever is retriever
            assert harness.reasoner is reasoner
            assert harness.memory_gate is gate
            assert [episode.turn_id for episode in gate.store.all()] == [7, 8]

    def test_replacing_exposed_stages_changes_execution(self):
        with AutoHarness() as harness:
            harness.retriever = Retriever(top_k=1)
            harness.reasoner = Reasoner(lm=CallableLM(lambda prompt: "replacement answer"))
            out = harness.forward("what is the wifi password", SESSION)
            assert out.answer == "replacement answer"
            assert len(out.ranked_evidence) == 1

    def test_config_replacement_updates_actual_stages_without_losing_effective_lm(self):
        calls: list[str] = []
        history = "\n".join(f"User: wifi password bluefish42 entry {index}" for index in range(4))

        def complete(prompt: str) -> str:
            calls.append(prompt)
            return "unrelated astronomy"

        with AutoHarness() as harness:
            harness.reasoner.lm = CallableLM(complete)
            initial = harness.forward("wifi password", history)
            assert len(initial.ranked_evidence) == 4
            assert len(calls) == 1
            reasoner = harness.reasoner
            retriever = harness.retriever
            harness.config = harness.config.with_(
                top_k=2, max_evidence=1, verify=True, grounding_threshold=0.9,
            )
            updated = harness.forward("wifi password", history)
            assert len(updated.ranked_evidence) == 2
            assert len(updated.evidence_citations) == 1
            assert len(calls) == 3
            assert harness.reasoner is reasoner
            assert harness.retriever is retriever
            assert updated.memory_written.turn_id == 1


class TestConsolidation:
    def test_knowledge_update_with_session_ending_consolidates(self):
        h = AutoHarness()
        session = "User: I now live in Lisbon\nAssistant: updated to Lisbon"
        out = h.forward("where do I now live", session, session_ending=True)
        assert out.consolidation_applied is True

    def test_plain_query_does_not_consolidate(self):
        h = AutoHarness()
        out = h.forward("what is the wifi password", SESSION, session_ending=True)
        assert out.consolidation_applied is False


class TestMemoryPersistence:
    def test_memory_persists_across_turns_same_instance(self):
        h = AutoHarness()
        s = "User: please remember the door code is 4321\nAssistant: door code 4321 noted"
        h.forward("please remember the door code is 4321", s, session_ending=True)
        assert "4321" in h.memory_gate.memory_md

    def test_memory_snapshot_injected(self):
        snap = MemorySnapshot(memory_md="# MEMORY\n\nprior")
        h = AutoHarness(memory_snapshot=snap)
        assert h.memory_gate.memory_md == "# MEMORY\n\nprior"


class TestRunAdapter:
    def test_run_uses_example_fields(self):
        ex = build_demo_dataset()[0]
        out = AutoHarness().run(ex)
        assert isinstance(out, HarnessOutput)


class TestBuildRunFn:
    def test_fresh_harness_per_call(self):
        run = build_run_fn(HarnessConfig())
        ex = build_demo_dataset()[0]
        out_a = run(ex)
        out_b = run(ex)
        # Deterministic and isolated: identical answers, fresh stores each time.
        assert out_a.answer == out_b.answer
        assert out_a.memory_written.turn_id == out_b.memory_written.turn_id == 0

    def test_interleaved_examples_do_not_share_episodes(self):
        run = build_run_fn(HarnessConfig(recall_memory=True))
        first, second = build_demo_dataset()[:2]
        before = run(first)
        between = run(second)
        after = run(first)
        assert before == after
        assert before.memory_written.turn_id == between.memory_written.turn_id == 0

    def test_config_applied(self):
        run = build_run_fn(HarnessConfig(top_k=1))
        out = run(build_demo_dataset()[0])
        assert len(out.ranked_evidence) <= 1


class TestHarnessRecall:
    def test_recall_surfaces_prior_fact(self):
        from src.memory.episodic_store import EpisodicStore
        from src.signatures import EpisodicEntry

        store = EpisodicStore()
        store.append(EpisodicEntry(0, "where do I live", "I live in Lisbon"))
        cfg = default_config().with_(recall_memory=True)
        h = AutoHarness(config=cfg, episodic_store=store, start_turn=store.count())
        out = h.forward("where do I live", "")
        # Recalled evidence is cited with a negative (synthetic) source index,
        # and the recalled fact must surface in the user-facing answer.
        assert any(c.source_index < 0 for c in out.evidence_citations)
        assert "Lisbon" in out.answer

    def test_recall_off_by_default(self):
        from src.memory.episodic_store import EpisodicStore
        from src.signatures import EpisodicEntry

        store = EpisodicStore()
        store.append(EpisodicEntry(0, "where do I live", "Lisbon"))
        h = AutoHarness(episodic_store=store, start_turn=store.count())
        out = h.forward("where do I live", "")
        assert out.evidence_citations == ()


class TestAdaptiveWindows:
    def test_no_op_on_compact_context(self):
        # On a short session, adaptive narrowing must reproduce the default exactly,
        # preserving determinism and all synthetic results.
        default = AutoHarness(config=default_config()).forward("what is the wifi password", SESSION)
        adaptive = AutoHarness(config=default_config().with_(adaptive_windows=True)).forward("what is the wifi password", SESSION)
        assert default.answer == adaptive.answer
        assert [c.source_index for c in default.evidence_citations] == [c.source_index for c in adaptive.evidence_citations]

    def test_scales_window_budget_on_long_context(self):
        # On a long haystack the adaptive harness raises the Inspector's window budget
        # to EXACTLY the formula value (not merely "bigger"), and surfaces at least as
        # many windows as the fixed default would.
        from src.stages.inspector import Inspector, adaptive_max_windows

        long_session = "\n".join(f"User: filler remark number {i} about things" for i in range(300))
        cfg = default_config().with_(adaptive_windows=True)
        h = AutoHarness(config=cfg)
        h.forward("filler", long_session)
        expected = adaptive_max_windows(300, cfg.max_windows, cfg.adaptive_window_ratio)
        assert expected == 60  # max(15, 300 // 5)
        assert h.inspector.max_windows == expected  # exact budget, kills an off-by-one or wrong formula
        # the bigger budget actually surfaces more evidence windows than the base cap
        base = Inspector(max_windows=cfg.max_windows, partition_threshold=cfg.partition_threshold, partition_size=cfg.partition_size)
        wide = Inspector(max_windows=expected, partition_threshold=cfg.partition_threshold, partition_size=cfg.partition_size)
        n_base = len(base(session_history=long_session, query="filler")["evidence_windows"])
        n_wide = len(wide(session_history=long_session, query="filler")["evidence_windows"])
        assert n_wide > n_base

    def test_adaptive_haystack_recovers_deep_equal_score_fact(self):
        lines = [f"User: wifi password placeholder {i}" for i in range(300)]
        lines[50] = "User: wifi password bluefish42"
        session = "\n".join(lines)
        fixed = AutoHarness(config=default_config().with_(max_windows=15)).forward("what is the wifi password", session)
        adaptive = AutoHarness(config=default_config().with_(max_windows=15, adaptive_windows=True)).forward(
            "what is the wifi password", session
        )

        assert "bluefish42" not in fixed.answer
        assert "bluefish42" in adaptive.answer
        assert adaptive.inspector_metadata is not None
        assert adaptive.inspector_metadata.adaptive_windows is True
        assert adaptive.inspector_metadata.effective_max_windows == 60

    def test_persistent_inspector_recomputes_policy_after_config_replacement(self):
        config = HarnessConfig(max_windows=2, partition_threshold=100)
        history = "\n".join(f"User: wifi password item {index}" for index in range(30))
        with AutoHarness(config=config) as harness:
            inspector = harness.inspector
            first = harness.forward("wifi password", history)
            assert first.inspector_metadata.effective_max_windows == 2
            assert first.inspector_metadata.partition_blocks_considered == 0
            harness.config = config.with_(
                adaptive_windows=True,
                adaptive_window_ratio=3,
                partition_threshold=5,
                partition_size=4,
            )
            second = harness.forward("wifi password", history)
            assert harness.inspector is inspector
            assert second.inspector_metadata.effective_max_windows == 10
            assert second.inspector_metadata.adaptive_windows is True
            assert second.inspector_metadata.partition_threshold == 5
            assert second.inspector_metadata.partition_size == 4
            assert second.inspector_metadata.partition_blocks_considered == 8
            third = harness.forward("wifi password", SESSION)
            assert third.inspector_metadata.effective_max_windows == 2
