"""Tests for the typed signature framework and domain payloads (Zero-Mock)."""

import pytest
from src.signatures import (
    DeliveryMode,
    EpisodicEntry,
    EvidenceCitation,
    EvidenceWindow,
    Field,
    FieldKind,
    HarnessOutput,
    InputField,
    InspectorMetadata,
    InspectorSignature,
    MemoryGateSignature,
    MemorySnapshot,
    OutputField,
    RankedEvidence,
    REACT_CATEGORIES,
    ReasonerSignature,
    RetrieverSignature,
    Signature,
    TaskCategory,
)


class TestTaskCategory:
    def test_from_str_valid(self):
        assert TaskCategory.from_str("temporal") is TaskCategory.TEMPORAL

    def test_from_str_invalid_defaults_single_session(self):
        assert TaskCategory.from_str("nonsense") is TaskCategory.SINGLE_SESSION

    def test_react_categories_membership(self):
        assert TaskCategory.MULTI_SESSION in REACT_CATEGORIES
        assert TaskCategory.SINGLE_SESSION not in REACT_CATEGORIES


class TestFieldFactories:
    def test_input_field(self):
        f = InputField("desc", annotation=int)
        assert f.kind is FieldKind.INPUT
        assert f.desc == "desc"
        assert f.annotation is int

    def test_output_field(self):
        f = OutputField("out")
        assert f.kind is FieldKind.OUTPUT
        assert f.annotation is str


class _Demo(Signature):
    """Return the query unchanged."""

    query: str = InputField("user query")
    count: int = InputField("how many")
    answer: str = OutputField("echoed answer")


class TestSignature:
    def test_fields_collects_all(self):
        fields = _Demo.fields()
        assert set(fields) == {"query", "count", "answer"}
        assert isinstance(fields["query"], Field)

    def test_annotation_carried_from_class(self):
        assert _Demo.fields()["count"].annotation is int

    def test_inputs_and_outputs_split(self):
        assert set(_Demo.inputs()) == {"query", "count"}
        assert set(_Demo.outputs()) == {"answer"}

    def test_instructions_is_docstring(self):
        assert _Demo.instructions() == "Return the query unchanged."

    def test_instructions_empty_when_no_docstring(self):
        class NoDoc(Signature):
            x: str = InputField()

        assert NoDoc.instructions() == ""

    def test_validate_inputs_ok(self):
        _Demo.validate_inputs(query="hi", count=1)

    def test_validate_inputs_missing_raises(self):
        with pytest.raises(ValueError, match="missing required input"):
            _Demo.validate_inputs(query="hi")


class TestConcreteSignatures:
    def test_inspector_signature_shape(self):
        assert set(InspectorSignature.inputs()) == {"session_history", "query"}
        assert set(InspectorSignature.outputs()) == {"evidence_windows", "metadata"}

    def test_retriever_signature_shape(self):
        assert "context_budget_tokens" in RetrieverSignature.inputs()
        assert "delivery_mode" in RetrieverSignature.outputs()

    def test_reasoner_signature_shape(self):
        assert "memory_context" in ReasonerSignature.inputs()
        assert set(ReasonerSignature.outputs()) == {
            "reasoning_trace",
            "answer",
            "evidence_citations",
            "requires_consolidation",
        }

    def test_memory_gate_signature_shape(self):
        assert "requires_consolidation" in MemoryGateSignature.inputs()
        assert "episodic_entry" in MemoryGateSignature.outputs()


class TestPayloads:
    def test_evidence_window_defaults(self):
        w = EvidenceWindow(text="t", source_index=2)
        assert w.relevance == 0.0 and w.start == 0 and w.end == 0

    def test_inspector_metadata(self):
        m = InspectorMetadata(("a",), (1,), 0.5, 100)
        assert m.session_length == 100

    def test_ranked_evidence(self):
        w = EvidenceWindow("t", 0)
        r = RankedEvidence(window=w, score=1.0)
        assert r.lexical_rank == -1 and r.semantic_rank == -1

    def test_evidence_citation(self):
        c = EvidenceCitation(source_index=3, excerpt="x")
        assert c.source_index == 3

    def test_memory_snapshot_defaults(self):
        s = MemorySnapshot()
        assert s.memory_md == "" and s.user_md == ""

    def test_episodic_entry_defaults(self):
        e = EpisodicEntry(turn_id=0, query="q", answer="a")
        assert e.evidence_indices == ()
        assert e.task_category == TaskCategory.SINGLE_SESSION.value

    def test_delivery_mode_values(self):
        assert DeliveryMode.INLINE.value == "inline"
        assert DeliveryMode.FILE_BASED.value == "file_based"

    def test_harness_output(self):
        e = EpisodicEntry(0, "q", "a")
        out = HarnessOutput(
            answer="a",
            reasoning_trace="t",
            evidence_citations=(),
            ranked_evidence=(),
            task_category=TaskCategory.CODE,
            memory_written=e,
        )
        assert out.consolidation_applied is False
        assert out.delivery_mode is DeliveryMode.INLINE
