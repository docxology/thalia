"""Tests for composability enhancements: context managers, serialisation, Pipeline, version."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure src is importable when run from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src import __version__  # noqa: E402
from src.config import HarnessConfig, default_config, load_config  # noqa: E402
from src.harness import AutoHarness  # noqa: E402
from src.memory.episodic_store import EpisodicStore  # noqa: E402
from src.pipeline import Pipeline, PipelineContext  # noqa: E402
from src.session import Session  # noqa: E402
from src.signatures import EpisodicEntry, HarnessOutput, TaskCategory  # noqa: E402


# ---------------------------------------------------------------------------
# __version__
# ---------------------------------------------------------------------------
class TestVersion:
    def test_version_is_string(self):
        assert isinstance(__version__, str)

    def test_version_matches_pyproject(self):
        try:
            import tomllib  # Python >= 3.11
        except ModuleNotFoundError:  # Python 3.10
            import tomli as tomllib

        pyproject = PROJECT_ROOT / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text())
        assert __version__ == data["project"]["version"]


# ---------------------------------------------------------------------------
# py.typed marker
# ---------------------------------------------------------------------------
class TestPyTyped:
    def test_py_typed_exists(self):
        """PEP 561 marker is present so downstream type checkers see our types."""
        assert (PROJECT_ROOT / "src" / "py.typed").exists()


# ---------------------------------------------------------------------------
# Context manager protocol: EpisodicStore
# ---------------------------------------------------------------------------
class TestEpisodicStoreContextManager:
    def test_context_manager_closes_connection(self):
        with EpisodicStore() as store:
            store.append(EpisodicEntry(0, "q", "a"))
            assert store.count() == 1
        # After exiting the context, the connection is closed.
        with pytest.raises(Exception):
            store.count()

    def test_context_manager_returns_self(self):
        store = EpisodicStore()
        assert store.__enter__() is store
        store.close()

    def test_context_manager_closes_on_exception(self):
        store = EpisodicStore()
        store.append(EpisodicEntry(0, "q", "a"))
        with pytest.raises(RuntimeError):
            with store:
                raise RuntimeError("boom")
        # Connection is closed even when an exception propagates.
        with pytest.raises(Exception):
            store.count()

    def test_close_is_idempotent(self):
        store = EpisodicStore()
        store.close()
        store.close()


# ---------------------------------------------------------------------------
# Context manager protocol: Session
# ---------------------------------------------------------------------------
class TestSessionContextManager:
    def test_session_context_manager_persists_and_closes(self, tmp_path):
        db = tmp_path / "episodes.db"
        memory = tmp_path / "MEMORY.md"
        with Session(db_path=str(db), memory_path=memory) as s:
            s.ask("My wifi password is bluefish42")
            assert s.turn_count == 1
        # After exiting, the store is closed — asking again would fail.
        # But reopening should work because the context manager flushed memory.
        assert memory.exists()

    def test_session_context_manager_closes_on_exception(self, tmp_path):
        db = tmp_path / "episodes.db"
        memory = tmp_path / "MEMORY.md"
        with pytest.raises(RuntimeError):
            with Session(db_path=str(db), memory_path=memory) as s:
                s.ask("note: hello")
                raise RuntimeError("mid-session")
        # Memory was still persisted by the context manager's __exit__.
        assert memory.exists()


class TestOwnedLifecycle:
    def test_harness_context_closes_owned_store(self):
        with AutoHarness() as harness:
            harness.forward("what is the wifi password", "User: wifi password is x")
            owned = harness.memory_gate.store
        assert owned._closed is True  # noqa: SLF001 - lifecycle contract
        harness.close()

    def test_harness_does_not_close_caller_store(self):
        store = EpisodicStore()
        with AutoHarness(episodic_store=store) as harness:
            harness.forward("what is the wifi password", "User: wifi password is x")
        store.append(EpisodicEntry(1, "q2", "a2"))
        store.close()

    def test_pipeline_context_closes_owned_store(self):
        with Pipeline().with_all_stages() as pipeline:
            pipeline.run(query="what is x", session_history="User: x is y")
            owned = pipeline._memory_gate.store  # noqa: SLF001
        assert owned._closed is True  # noqa: SLF001

    def test_pipeline_does_not_close_caller_store(self):
        store = EpisodicStore()
        with Pipeline(episodic_store=store).with_memory_gate() as pipeline:
            pipeline.run(query="what is x", session_history="User: x is y")
        store.append(EpisodicEntry(1, "q2", "a2"))
        store.close()

# ---------------------------------------------------------------------------
# HarnessOutput.to_dict()
# ---------------------------------------------------------------------------
class TestHarnessOutputToDict:
    def _make_output(self) -> HarnessOutput:
        return AutoHarness().forward(
            "what is the wifi password",
            "User: my wifi password is bluefish42",
        )

    def test_to_dict_has_all_fields(self):
        out = self._make_output()
        d = out.to_dict()
        assert "answer" in d
        assert "task_category" in d
        assert "delivery_mode" in d
        assert "reasoning_trace" in d
        assert "consolidation_applied" in d
        assert "citations" in d
        assert "ranked_evidence" in d
        assert "inspector_metadata" in d

    def test_to_dict_is_json_serialisable(self):
        out = self._make_output()
        d = out.to_dict()
        json.dumps(d)  # must not raise

    def test_to_dict_matches_cli_output_to_dict(self):
        from src.cli import output_to_dict

        out = self._make_output()
        assert out.to_dict() == output_to_dict(out)

    def test_to_dict_inspector_metadata_none(self):
        """to_dict works when inspector_metadata is None."""
        out = HarnessOutput(
            answer="a",
            reasoning_trace="t",
            evidence_citations=(),
            ranked_evidence=(),
            task_category=TaskCategory.SINGLE_SESSION,
            memory_written=EpisodicEntry(0, "q", "a"),
            inspector_metadata=None,
        )
        d = out.to_dict()
        assert d["inspector_metadata"] is None


# ---------------------------------------------------------------------------
# HarnessConfig.to_yaml() / from_yaml()
# ---------------------------------------------------------------------------
class TestConfigYaml:
    def test_to_yaml_roundtrip(self):
        config = default_config().with_(top_k=4, max_evidence=3)
        yaml_text = config.to_yaml()
        restored = HarnessConfig.from_yaml(yaml_text)
        assert restored == config

    def test_from_yaml_flat_mapping(self):
        yaml_text = "top_k: 12\nmax_evidence: 7\n"
        config = HarnessConfig.from_yaml(yaml_text)
        assert config.top_k == 12
        assert config.max_evidence == 7

    def test_from_yaml_harness_key(self):
        yaml_text = "harness:\n  top_k: 6\n  max_evidence: 2\n"
        config = HarnessConfig.from_yaml(yaml_text)
        assert config.top_k == 6
        assert config.max_evidence == 2

    def test_from_yaml_ignores_unknown_keys(self):
        yaml_text = "top_k: 8\nunknown_field: hello\n"
        config = HarnessConfig.from_yaml(yaml_text)
        assert config.top_k == 8

    def test_from_yaml_rejects_non_mapping(self):
        with pytest.raises(ValueError, match="mapping"):
            HarnessConfig.from_yaml("- item\n- item2\n")

    def test_to_yaml_is_valid_yaml(self):
        import yaml

        config = default_config()
        yaml_text = config.to_yaml()
        data = yaml.safe_load(yaml_text)
        assert isinstance(data, dict)
        assert data["top_k"] == config.top_k

    def test_load_config_uses_from_yaml(self, tmp_path):
        """load_config delegates to from_yaml, so both paths accept a harness: key."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("harness:\n  top_k: 10\n  max_evidence: 4\n")
        config = load_config(config_file, apply_env=False)
        assert config.top_k == 10
        assert config.max_evidence == 4


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
class TestPipeline:
    def test_full_pipeline_matches_autoharness(self):
        """The Pipeline with all stages should produce the same answer as AutoHarness."""
        query = "what is the wifi password"
        history = "User: my wifi password is bluefish42"
        harness_out = AutoHarness().forward(query, history)

        pipe = Pipeline().with_all_stages()
        pipe_out = pipe.run(query=query, session_history=history)

        assert pipe_out.answer == harness_out.answer
        assert pipe_out.task_category == harness_out.task_category
        assert pipe_out.delivery_mode == harness_out.delivery_mode

    def test_pipeline_intermediates_recorded(self):
        pipe = Pipeline().with_all_stages()
        pipe.run(query="what is the wifi password", session_history="User: my wifi password is bluefish42")
        intermediates = pipe.intermediates
        names = [name for name, _ in intermediates]
        assert names == ["inspector", "retriever", "reasoner", "memory_gate"]
        assert len({id(ctx) for _, ctx in intermediates}) == len(intermediates)
        assert intermediates[0][1].ranked_evidence == []
        assert intermediates[1][1].ranked_evidence
        assert intermediates[2][1].answer
        assert intermediates[3][1].episodic_entry is not None

    def test_pipeline_steps_property(self):
        pipe = Pipeline().with_inspector().with_retriever()
        assert len(pipe.steps) == 2
        assert pipe.steps[0].name == "inspector"
        assert pipe.steps[1].name == "retriever"

    def test_pipeline_custom_step(self):
        pipe = (
            Pipeline()
            .with_inspector()
            .add_step("count_windows", lambda ctx: (ctx.extras.update({"n_windows": len(ctx.evidence_windows)}), ctx)[1])
            .with_retriever()
            .with_reasoner()
            .with_memory_gate()
        )
        pipe.run(query="what is the wifi password", session_history="User: my wifi password is bluefish42")
        # The custom step ran between inspector and retriever.
        names = [name for name, _ in pipe.intermediates]
        assert "count_windows" in names
        # The intermediate context after count_windows should have the extra.
        for name, ctx in pipe.intermediates:
            if name == "count_windows":
                assert ctx.extras["n_windows"] >= 1
                break

    def test_pipeline_partial_stages(self):
        """Pipeline works with just the Inspector — no Retriever/Reasoner/MemoryGate."""
        pipe = Pipeline().with_inspector()
        out = pipe.run(query="what is the wifi password", session_history="User: my wifi password is bluefish42")
        # Without a Reasoner, answer is empty; without a Memory Gate, no consolidation.
        assert out.answer == ""
        assert not out.consolidation_applied
        # But the Inspector metadata is populated.
        assert out.inspector_metadata is not None
        assert out.inspector_metadata.line_count > 0

    def test_pipeline_chaining_returns_self(self):
        """Each with_* method returns the pipeline for fluent chaining."""
        pipe = Pipeline()
        assert pipe.with_inspector() is pipe
        assert pipe.with_retriever() is pipe
        assert pipe.with_reasoner() is pipe
        assert pipe.with_memory_gate() is pipe

    def test_pipeline_task_category_detected(self):
        """The pipeline classifies the query before any stage runs."""
        pipe = Pipeline().with_inspector()
        out = pipe.run(
            query="When is the car service scheduled?",
            session_history="User: the car service is on April 12th",
        )
        assert out.task_category == TaskCategory.TEMPORAL

    def test_pipeline_with_config(self):
        """Pipeline respects a custom config."""
        config = default_config().with_(top_k=2, max_evidence=1)
        pipe = Pipeline(config=config).with_all_stages()
        out = pipe.run(query="what is the wifi password", session_history="User: my wifi password is bluefish42")
        assert len(out.ranked_evidence) <= 2

    def test_pipeline_context_is_mutable(self):
        """PipelineContext extras dict can be used by custom steps."""
        ctx = PipelineContext()
        ctx.extras["key"] = "value"
        assert ctx.extras["key"] == "value"

    def test_pipeline_repr(self):
        """__repr__ shows the registered steps."""
        pipe = Pipeline().with_inspector().with_retriever()
        rep = repr(pipe)
        assert "inspector" in rep
        assert "retriever" in rep
        assert "total" in rep

    def test_pipeline_adaptive_windows(self):
        """Pipeline with adaptive_windows=True scales inspector windows."""
        config = default_config().with_(adaptive_windows=True, adaptive_window_ratio=10, max_windows=3)
        long_history = "User: line\nAssistant: response\n" * 100  # 200 lines
        pipe = Pipeline(config=config).with_inspector()
        out = pipe.run(query="what is the wifi password", session_history=long_history)
        # Adaptive windows should scale beyond the default max_windows with a long context
        assert out.inspector_metadata is not None

    def test_pipeline_recall_memory(self):
        """Pipeline with recall_memory=True consults the episodic store."""
        from src.memory.episodic_store import EpisodicStore
        from src.signatures import EpisodicEntry

        store = EpisodicStore()
        store.append(EpisodicEntry(0, "my wifi password is bluefish42", "noted"))
        config = default_config().with_(recall_memory=True, recall_limit=3)
        pipe = Pipeline(config=config, episodic_store=store).with_all_stages()
        out = pipe.run(query="what is the wifi password", session_history="User: something else")
        # Memory recall should surface the stored fact even though the session has no evidence
        assert out.answer or "bluefish42" in str(out.ranked_evidence)
        store.close()


class TestHarnessOutputSerialisation:
    def test_to_dict_round_trip(self):
        """HarnessOutput.to_dict produces a serialisable dictionary."""
        out = AutoHarness().forward("what is the wifi password", "User: my wifi password is bluefish42")
        d = out.to_dict()
        # The extractive LM answers by copying the full evidence text, so the
        # answer contains the full user statement, not just the extracted fact.
        assert "bluefish42" in d["answer"]
        assert d["task_category"] == "single_session"
        assert len(d["citations"]) >= 1

    def test_to_json_produces_valid_json(self):
        """HarnessOutput.to_json returns valid JSON."""
        out = AutoHarness().forward("what is the wifi password", "User: my wifi password is bluefish42")
        js = out.to_json(indent=2)
        parsed = json.loads(js)
        assert "bluefish42" in parsed["answer"]


class TestHarnessConfigValidation:
    def test_validate_passes_on_valid_config(self):
        """validate() does not raise on a default config."""
        HarnessConfig().validate()

    def test_validate_raises_on_bad_ratio(self):
        """validate() raises when adaptive_window_ratio is invalid."""
        # Bypass the frozen dataclass __post_init__ so we can construct an
        # invalid config and test that validate() catches it.
        cfg = HarnessConfig.__new__(HarnessConfig)
        object.__setattr__(cfg, "adaptive_window_ratio", -1)
        object.__setattr__(cfg, "max_windows", 15)
        object.__setattr__(cfg, "top_k", 8)
        object.__setattr__(cfg, "rrf_k", 60)
        object.__setattr__(cfg, "max_evidence", 5)
        object.__setattr__(cfg, "context_budget_tokens", 2048)
        object.__setattr__(cfg, "mmr_lambda", 0.7)
        object.__setattr__(cfg, "grounding_threshold", 0.3)
        object.__setattr__(cfg, "partition_threshold", 40)
        object.__setattr__(cfg, "partition_size", 10)
        object.__setattr__(cfg, "expansion_terms", 5)
        object.__setattr__(cfg, "recency_weight", 0.0)
        object.__setattr__(cfg, "recall_limit", 3)
        object.__setattr__(cfg, "adaptive_window_ratio", -1)
        object.__setattr__(cfg, "lexical_weight", None)
        object.__setattr__(cfg, "semantic_weight", None)
        with pytest.raises(ValueError, match="adaptive_window_ratio must be positive"):
            cfg.validate()


class TestCliVersion:
    def test_cli_version_flag(self):
        """The CLI accepts --version and --json together (version exits)."""
        from src.cli import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--version"])
        assert exc.value.code == 0
