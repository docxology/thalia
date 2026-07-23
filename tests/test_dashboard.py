"""Tests for the static HTML dashboard renderer (Zero-Mock)."""

from src.dashboard import render_dashboard_html, write_dashboard
from src.invariants import InvariantResult

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


class TestWrite:
    def test_writes_file(self, tmp_path):
        path = write_dashboard(tmp_path / "dash.html", METRICS, INVARIANTS, FIGURES)
        assert path.exists() and path.read_text().startswith("<!doctype html>")

    def test_creates_parent_dir(self, tmp_path):
        path = write_dashboard(tmp_path / "nested" / "dash.html", METRICS, INVARIANTS, FIGURES)
        assert path.exists()
