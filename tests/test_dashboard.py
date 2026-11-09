"""Tests for the static HTML dashboard renderer (Zero-Mock)."""

import copy
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path

import pytest

from src.dashboard import render_dashboard_html, write_dashboard
from src.invariants import InvariantResult
from src.figures.manifest import FIGURE_CAPTIONS
from src.evaluation.backend_benchmark import (
    BenchmarkBackend, build_benchmark_methods, run_backend_benchmark,
)
from src.llm import CallableLM
from src.module import ExtractiveLM

METRICS = {
    "n_examples": 6,
    "composite": 0.621,
    "accuracy": 0.477,
    "grounding": 0.830,
    "efficiency": 0.854,
    "retriever_comparison": {"lexical": 0.6, "semantic": 0.6, "hybrid": 0.6, "best_mode": "lexical"},
    "category_means": {"temporal": 0.7, "code": 0.5},
}
INVARIANTS = [
    InvariantResult("harness_determinism", True, "two runs agree"),
    InvariantResult("broken_thing", False, "did not hold"),
]
FIGURES = ["figures/retriever_comparison.png", "figures/noise_scaling.png"]


class DashboardPage(HTMLParser):
    """Read the rendered document's actual table cells and element attributes."""

    def __init__(self, document):
        super().__init__()
        self.elements = []
        self.rows = []
        self.tables = {}
        self.table_id = None
        self.row = []
        self.cell = None
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))
        if tag == "table":
            self.table_id = dict(attrs).get("id")
            if self.table_id:
                self.tables[self.table_id] = []
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.row.append("".join(self.cell))
            self.cell = None
        if tag == "tr":
            self.rows.append(self.row)
            if self.table_id:
                self.tables[self.table_id].append(self.row)
        if tag == "table":
            self.table_id = None


@pytest.fixture(scope="module")
def backend_benchmark():
    return run_backend_benchmark(
        [
            BenchmarkBackend(
                name="extractive <baseline>",
                provider="offline & local",
                model='ExtractiveLM <model> "quoted"',
                lm=ExtractiveLM(),
                generation_options={"note": "<public metadata>"},
            ),
        ],
        per_category=1,
        limit=2,
        seeds=(17,),
        methods=build_benchmark_methods(("full_context", "harness")),
    )


def _raise_generation_error(prompt):
    raise RuntimeError("deliberate real generation failure")


@pytest.fixture(scope="module")
def incomplete_benchmark():
    return run_backend_benchmark(
        [
            BenchmarkBackend("baseline", "extractive", "ExtractiveLM", ExtractiveLM()),
            BenchmarkBackend("failing", "callable", "raising", CallableLM(_raise_generation_error)),
        ],
        per_category=1,
        limit=2,
        seeds=(17,),
        methods=build_benchmark_methods(("full_context", "harness")),
    )


class TestRender:
    def test_is_html_document(self):
        out = render_dashboard_html(METRICS, INVARIANTS, FIGURES)
        assert out.startswith("<!doctype html>")
        assert "THALIA" in out

    def test_includes_metrics(self):
        out = render_dashboard_html(METRICS, INVARIANTS, FIGURES)
        assert "0.621" in out and "Composite" in out

    def test_includes_category_rows(self):
        out = render_dashboard_html(METRICS, INVARIANTS, FIGURES)
        assert "temporal" in out and "code" in out

    def test_includes_invariants_with_status(self):
        out = render_dashboard_html(METRICS, INVARIANTS, FIGURES)
        assert "harness_determinism" in out
        assert "class='pass'" in out and "class='fail'" in out
        assert "(1/2 passing)" in out

    def test_embeds_figures(self):
        out = render_dashboard_html(METRICS, INVARIANTS, FIGURES)
        assert "figures/retriever_comparison.png" in out
        assert out.count("<img") == len(FIGURES)

    def test_authored_alt_is_escaped_and_does_not_replace_caption(self):
        authored = 'Description <diagram> & "quoted" with \'apostrophes\''
        out = render_dashboard_html(
            METRICS, [], FIGURES + ["figures/unknown.png"],
            figure_descriptions={"retriever_comparison": authored, "noise_scaling": " \n "},
        )
        page = DashboardPage(out)
        images = [attrs for tag, attrs in page.elements if tag == "img"]
        assert images[0]["alt"] == authored
        assert images[1]["alt"] == FIGURE_CAPTIONS["noise_scaling"]
        assert images[2]["alt"] == "unknown"
        assert authored not in out
        assert "&lt;diagram&gt;" in out and "&#x27;apostrophes&#x27;" in out
        caption = out.split("<figcaption", 1)[1].split("</figcaption>", 1)[0]
        assert FIGURE_CAPTIONS["retriever_comparison"] in caption
        assert "Description" not in caption

    def test_includes_verification_and_demo(self):
        out = render_dashboard_html(
            METRICS,
            INVARIANTS,
            FIGURES,
            verification={"status": "ok", "coverage_gate": 90},
            demo={"session": {"reopened_answer": "bluefish42"}, "compiler": {"mipro_style": {"best_score": 0.5}}},
        )
        assert "Verification Gates" in out
        assert "Deterministic Demo" in out
        assert "bluefish42" in out

    def test_includes_statistical_sample_audit(self):
        metrics = dict(METRICS)
        metrics["statistical_scaling"] = {
            "seed_values": [0, 1],
            "accounting": {"n_requested": 24, "n_evaluated": 72, "n_unique_examples": 24, "n_method_evaluations": 72, "n_failed": 0},
            "rows": [{"n_total": 24, "methods": {"hybrid": {"estimate": 0.7, "low": 0.6, "high": 0.8}}}],
        }
        out = render_dashboard_html(metrics, INVARIANTS, FIGURES)
        assert "Statistical sample audit" in out
        assert "Method evaluations" in out
        assert "Unique examples evaluated" in out and ">24<" in out

    def test_handles_missing_comparison(self):
        metrics = {
            "n_examples": 1,
            "composite": 0.5,
            "accuracy": 0.5,
            "grounding": 0.5,
            "efficiency": 0.5,
            "category_means": {},
        }
        out = render_dashboard_html(metrics, [], [])
        assert "Best retrieval mode" not in out  # comparison row omitted

    def test_escapes_html(self):
        invs = [InvariantResult("name", True, "<script>alert(1)</script>")]
        out = render_dashboard_html(METRICS, invs, [])
        assert "<script>alert(1)</script>" not in out
        assert "&lt;script&gt;" in out

    def test_missing_metrics_are_not_zero(self):
        page = DashboardPage(render_dashboard_html({"accuracy": 0.0, "grounding": None}, [], []))
        assert ["Composite", "—"] in page.rows
        assert ["Answer token-F1", "0.000"] in page.rows
        assert ["Citation-support proxy", "—"] in page.rows
        assert ["Examples", "—"] in page.rows

    def test_provenance_without_statistical_scaling(self):
        metrics = {"provenance": {"neural_model": "<local>", "neural_digest": "sha256:abc"}}
        out = render_dashboard_html(metrics, [], [])
        page = DashboardPage(out)
        assert ["Neural model", "<local>"] in page.rows
        assert ["Neural digest", "sha256:abc"] in page.rows
        assert "<local>" not in out

    def test_backend_observations_and_accessibility(self, backend_benchmark):
        out = render_dashboard_html(METRICS, INVARIANTS, FIGURES, backend_benchmark=backend_benchmark)
        page = DashboardPage(out)
        backend = backend_benchmark["backends"][-1]
        summary = backend_benchmark["summaries"][-1]
        assert [
            backend["name"], backend["provider"], backend["model"], summary["method"],
            "complete", "2", "2", "0", f"{summary['mean_token_f1']:.3f}",
            f"{summary['mean_latency_seconds']:.3f}", f"{summary['p50_latency_seconds']:.3f}",
            f"{summary['p95_latency_seconds']:.3f}", f"{summary['mean_prompt_characters']:.3f}",
        ] in page.rows
        assert "Within-model paired method contrasts" in out
        assert "Single-seed: interval unavailable" in out
        assert "not billed tokens" in out
        assert "same examples" in out and "equal seed weight" in out
        assert "Category and stratum observations" in out
        assert any(tag == "main" for tag, _ in page.elements)
        assert any(tag == "meta" and attrs.get("name") == "viewport" for tag, attrs in page.elements)
        assert any(
            tag == "div" and attrs.get("role") == "region"
            and attrs.get("tabindex") == "0"
            and attrs.get("aria-labelledby") == "backend-benchmark-heading"
            for tag, attrs in page.elements
        )
        assert any(tag == "th" and attrs.get("scope") == "col" for tag, attrs in page.elements)
        assert all(attrs.get("scope") in {"row", "col"} for tag, attrs in page.elements if tag == "th")
        assert sum(tag == "figure" for tag, _ in page.elements) == len(FIGURES)
        assert sum(tag == "figcaption" for tag, _ in page.elements) == len(FIGURES)
        assert sum(tag == "caption" for tag, _ in page.elements) == sum(tag == "table" for tag, _ in page.elements)
        assert backend["name"] not in out
        assert backend["model"] not in out
        assert "<public metadata>" not in out and "&lt;public metadata&gt;" in out
        assert backend_benchmark["dataset_fingerprint"] in out
        assert backend_benchmark["methods"][0]["method_fingerprint"] in out
        assert backend_benchmark["report_fingerprint"] in out

    def test_missing_backend_evidence_is_explicit(self):
        out = render_dashboard_html(METRICS, [], [])
        assert "MISSING" in out
        assert not any(row and row[0] == "Backend" for row in DashboardPage(out).rows)
        assert "Per-seed paired audit: not recorded; no benchmark report supplied." in out

    def test_incomplete_backend_keeps_failure_accounting(self, incomplete_benchmark):
        out = render_dashboard_html(METRICS, [], [], backend_benchmark=incomplete_benchmark)
        assert "INCOMPLETE" in out
        page = DashboardPage(out)
        assert ["failing", "callable", "raising", "harness", "incomplete", "2", "0", "2",
                "—", "—", "—", "—", "—"] in page.rows
        assert incomplete_benchmark["summaries"][0]["status"] == "complete"
        assert any(row[:5] == ["baseline", "extractive", "ExtractiveLM", "harness", "complete"]
                   for row in page.rows)
        assert "Incomplete: paired estimate suppressed" in out

    @pytest.mark.parametrize("corruption", ["empty", "schema1", "version", "counts", "latency", "rows", "comparison", "method", "group"])
    def test_rejects_invalid_backend_evidence(self, backend_benchmark, corruption):
        payload = copy.deepcopy(backend_benchmark)
        if corruption == "empty":
            payload = {}
        elif corruption in {"version", "schema1"}:
            payload["schema_version"] = 1 if corruption == "schema1" else 999
        elif corruption == "counts":
            payload["summaries"][0]["n_completed"] += 1
        elif corruption == "latency":
            payload["summaries"][0]["p95_latency_seconds"] = float("nan")
        elif corruption == "comparison":
            payload["comparisons"][0]["mean_delta"] = 999
        elif corruption == "method":
            payload["methods"][0]["method_fingerprint"] = "0" * 64
        elif corruption == "group":
            payload["groups"]["category"][0]["n_completed"] += 1
        else:
            payload["rows"].pop()
        with pytest.raises(ValueError):
            render_dashboard_html(METRICS, [], [], backend_benchmark=payload)


    def test_reference_absent_is_not_inferred(self):
        payload = run_backend_benchmark(
            [BenchmarkBackend("baseline", "extractive", "ExtractiveLM", ExtractiveLM())],
            per_category=1, limit=2,
        )
        out = render_dashboard_html(METRICS, [], [], backend_benchmark=payload)
        assert payload["comparisons"] == []
        assert "backend-seed-pairs-" not in out

    @pytest.mark.parametrize("fail_first", [False, True])
    def test_seed_audit_keeps_denominators_and_suppresses_partial_seed(self, fail_first):
        calls = 0

        def complete(prompt):
            nonlocal calls
            calls += 1
            if fail_first and calls == 1:
                raise RuntimeError("first real completion fails")
            return ExtractiveLM().complete(prompt)

        payload = run_backend_benchmark(
            [BenchmarkBackend("audit <&>", "callable", "offline", CallableLM(complete))],
            methods=build_benchmark_methods(("full_context", "harness")),
            seeds=(9, 2), per_category=1, limit=3, n_boot=10,
        )
        out = render_dashboard_html(METRICS, [], [], backend_benchmark=payload)
        page = DashboardPage(out)
        audit_index = next(
            index for index, backend in enumerate(payload["backends"])
            if backend["name"] == "audit <&>"
        )
        rows = page.tables[f"backend-seed-pairs-{audit_index}"]
        matrix = {
            (row["method"], row["example_id"]): row
            for row in payload["rows"] if row["backend"] == "audit <&>"
        }
        expected = []
        for seed in sorted({example["seed"] for example in payload["examples"]}):
            examples = [example for example in payload["examples"] if example["seed"] == seed]
            deltas = []
            for example in examples:
                candidate = matrix[("harness", example["example_id"])]
                reference = matrix[("full_context", example["example_id"])]
                if candidate["status"] == reference["status"] == "complete":
                    deltas.append(candidate["token_f1"] - reference["token_f1"])
            complete_seed = len(deltas) == len(examples)
            expected.append([
                "harness", str(seed), f"{len(examples)} / {len(deltas)}",
                f"{sum(delta > 0 for delta in deltas)} / {sum(delta == 0 for delta in deltas)} / "
                f"{sum(delta < 0 for delta in deltas)}",
                f"{sum(deltas) / len(deltas):.3f}" if complete_seed else "—",
            ])
        assert [row[:5] for row in rows[1:]] == expected
        assert {row[2].split(" / ")[0] for row in rows[1:]} == {"1", "2"}
        if fail_first:
            assert any(row[-1] == "complete" for row in rows[1:])
            comparison = next(row for row in page.rows if row[:4] == [
                "audit <&>", "harness", "full_context", "incomplete",
            ])
            assert comparison[10:12] == ["—", "—"]


class TestWrite:
    def test_writes_file(self, tmp_path):
        path = write_dashboard(tmp_path / "dash.html", METRICS, INVARIANTS, FIGURES)
        assert path.exists() and path.read_text().startswith("<!doctype html>")

    def test_creates_parent_dir(self, tmp_path):
        path = write_dashboard(tmp_path / "nested" / "dash.html", METRICS, INVARIANTS, FIGURES)
        assert path.exists()

    def test_writes_backend_evidence(self, tmp_path, incomplete_benchmark):
        path = write_dashboard(
            tmp_path / "dashboard.html", METRICS, [], [], backend_benchmark=incomplete_benchmark,
        )
        page = DashboardPage(path.read_text(encoding="utf-8"))
        assert ["failing", "callable", "raising", "harness", "incomplete", "2", "0", "2",
                "—", "—", "—", "—", "—"] in page.rows

    def test_invalid_evidence_does_not_replace_existing_dashboard(self, tmp_path):
        path = tmp_path / "dashboard.html"
        path.write_text("previous dashboard", encoding="utf-8")
        with pytest.raises(ValueError):
            write_dashboard(path, METRICS, [], [], backend_benchmark={})
        assert path.read_text(encoding="utf-8") == "previous dashboard"


class TestBuildDashboardInput:
    def test_explicit_invalid_or_missing_benchmark_fails_before_building(self, tmp_path):
        script = Path(__file__).resolve().parents[1] / "scripts" / "build_dashboard.py"
        spec = importlib.util.spec_from_file_location("dashboard_cli", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        path = tmp_path / "backend.json"
        with pytest.raises(FileNotFoundError):
            module.main(["--backend-benchmark", str(path)])
        path.write_text(json.dumps({}), encoding="utf-8")
        with pytest.raises(ValueError):
            module.main(["--backend-benchmark", str(path)])
