"""Tests for figure generators (Zero-Mock; writes real PNGs to tmp_path)."""

from src.evaluation import RetrieverComparison
from src.figures import (
    EXPORT_DPI,
    PALETTE,
    plot_compiler_convergence,
    plot_consolidation_curve,
    plot_retriever_comparison,
    plot_rrf_weight_sensitivity,
)


class TestConstants:
    def test_palette_has_modes(self):
        for key in ("lexical", "semantic", "hybrid"):
            assert key in PALETTE

    def test_export_dpi(self):
        assert EXPORT_DPI == 300


class TestRetrieverComparisonPlot:
    def test_writes_png(self, tmp_path):
        cmp = RetrieverComparison(lexical=0.7, semantic=0.6, hybrid=0.72)
        path = plot_retriever_comparison(cmp, tmp_path / "cmp.png")
        assert path.exists() and path.stat().st_size > 0

    def test_creates_parent_dir(self, tmp_path):
        cmp = RetrieverComparison(lexical=0.7, semantic=0.6, hybrid=0.72)
        path = plot_retriever_comparison(cmp, tmp_path / "nested" / "cmp.png")
        assert path.exists()


class TestRRFSensitivityPlot:
    def test_writes_png(self, tmp_path):
        path = plot_rrf_weight_sensitivity(tmp_path / "rrf.png", steps=5)
        assert path.exists() and path.stat().st_size > 0


class TestCompilerConvergencePlot:
    def test_writes_png(self, tmp_path):
        trace = [(None, 0.5), (None, 0.7), (None, 0.6), (None, 0.8)]
        path = plot_compiler_convergence(trace, tmp_path / "conv.png")
        assert path.exists() and path.stat().st_size > 0


class TestConsolidationPlot:
    def test_writes_png(self, tmp_path):
        path = plot_consolidation_curve(tmp_path / "cons.png", turns=8)
        assert path.exists() and path.stat().st_size > 0


class TestExtendedFigures:
    def test_category_breakdown(self, tmp_path):
        from src.figures import plot_category_breakdown

        path = plot_category_breakdown({"temporal": 0.7, "code": 0.5}, tmp_path / "cat.png")
        assert path.exists() and path.stat().st_size > 0

    def test_evidence_funnel(self, tmp_path):
        from src.figures import plot_evidence_funnel

        path = plot_evidence_funnel(tmp_path / "funnel.png")
        assert path.exists() and path.stat().st_size > 0

    def test_noise_scaling(self, tmp_path):
        from src.figures import plot_noise_scaling

        path = plot_noise_scaling(tmp_path / "noise.png")
        assert path.exists() and path.stat().st_size > 0

    def test_mmr_tradeoff(self, tmp_path):
        from src.figures import plot_mmr_tradeoff

        path = plot_mmr_tradeoff(tmp_path / "mmr.png", steps=5)
        assert path.exists() and path.stat().st_size > 0

    def test_method_ablation(self, tmp_path):
        from src.figures import plot_method_ablation

        path = plot_method_ablation(tmp_path / "ablation.png")
        assert path.exists() and path.stat().st_size > 0

    def test_backend_comparison(self, tmp_path):
        from src.figures import plot_backend_comparison

        data = {
            "model": "gemma3:4b",
            "mean_extractive_f1": 0.477,
            "mean_neural_f1": 0.621,
            "n": 3,
            "rows": [
                {"category": "code", "extractive_f1": 0.0, "neural_f1": 0.77},
                {"category": "single_session", "extractive_f1": 0.8, "neural_f1": 0.4},
                {"category": "temporal", "extractive_f1": 0.62, "neural_f1": 0.67},
            ],
            "category_extractive_f1": {"code": 0.0, "single_session": 0.8, "temporal": 0.62},
            "category_neural_f1": {"code": 0.77, "single_session": 0.4, "temporal": 0.67},
        }
        path = plot_backend_comparison(data, tmp_path / "backend.png")
        assert path.exists() and path.stat().st_size > 0

    def test_bottleneck(self, tmp_path):
        from src.figures import plot_bottleneck

        data = {
            "n_ranking": 40, "ranking_recall_at_10": 1.0, "inspector_recall": 0.6, "neural_model": "gemma3:4b",
            "ranking_recall_by_mode": {"available": True, "n": 8, "k": 10, "lexical": 1.0, "dense": 1.0, "hybrid": 1.0},
            "sweep_values": [15, 30, 50, 100],
            "extractive_grounding_by_maxwindows": {"15": 0.422, "30": 0.468, "50": 0.511, "100": 0.575},
            "neural_by_maxwindows": {"15": {"accuracy": 0.092, "grounding": 0.359}, "100": {"accuracy": 0.178, "grounding": 0.533}},
            "neural_adaptive": {"accuracy": 0.183, "grounding": 0.533},
        }
        path = plot_bottleneck(data, tmp_path / "bn.png")
        assert path.exists() and path.stat().st_size > 0
        # also renders without the adaptive field (back-compat)
        assert plot_bottleneck({k: v for k, v in data.items() if k != "neural_adaptive"}, tmp_path / "bn2.png").exists()

    def test_longmemeval(self, tmp_path):
        from src.figures import plot_longmemeval

        data = {
            "n_extractive": 500, "n_neural": 50, "neural_model": "gemma3:4b",
            "extractive_accuracy": (0.048, 0.043, 0.055), "neural_accuracy": (0.119, 0.083, 0.159),
            "extractive_grounding": (0.430, 0.409, 0.451), "neural_grounding": (0.381, 0.310, 0.448),
        }
        path = plot_longmemeval(data, tmp_path / "lme.png")
        assert path.exists() and path.stat().st_size > 0

    def test_scaling_ci(self, tmp_path):
        from src.figures import plot_scaling_ci

        data = {
            "n": 60, "per_category": 10, "composite_mean": 0.816, "composite_lo": 0.80, "composite_hi": 0.83,
            "category_accuracy": {"code": (0.76, 0.74, 0.78), "temporal": (0.66, 0.65, 0.67), "preference": (0.81, 0.80, 0.82)},
        }
        path = plot_scaling_ci(data, tmp_path / "scaling.png")
        assert path.exists() and path.stat().st_size > 0

    def test_injection_resistance(self, tmp_path):
        from src.figures import plot_injection_resistance

        data = {
            "n_probes": 3, "harness_poison_rate": 0.33, "harness_audit_rate": 1.0,
            "naive_poison_rate": 0.33, "naive_audit_rate": 0.0,
            "neural_model": "gemma3:4b", "neural_poison_rate": 1.0,
            "rows": [
                {"probe": 1, "harness_poisoned": True, "harness_auditable": True, "naive_poisoned": True, "naive_auditable": False},
                {"probe": 2, "harness_poisoned": False, "harness_auditable": True, "naive_poisoned": False, "naive_auditable": False},
                {"probe": 3, "harness_poisoned": False, "harness_auditable": True, "naive_poisoned": False, "naive_auditable": False},
            ],
            "neural_rows": [
                {"probe": 1, "neural_poisoned": True, "neural_auditable": False},
                {"probe": 2, "neural_poisoned": True, "neural_auditable": False},
                {"probe": 3, "neural_poisoned": True, "neural_auditable": False},
            ],
        }
        path = plot_injection_resistance(data, tmp_path / "inj.png")
        assert path.exists() and path.stat().st_size > 0
        # also the no-neural variant (neural row absent)
        data2 = dict(data, neural_poison_rate=None)
        assert plot_injection_resistance(data2, tmp_path / "inj2.png").exists()

    def test_orchestration_value(self, tmp_path):
        from src.figures import plot_orchestration_value

        baseline = {
            "naive_accuracy": 0.477, "naive_grounding": 0.0, "naive_efficiency": 0.0, "naive_composite": 0.286,
            "pipeline_accuracy": 0.477, "pipeline_grounding": 0.83, "pipeline_efficiency": 0.85, "pipeline_composite": 0.621,
        }
        path = plot_orchestration_value(baseline, tmp_path / "orch.png")
        assert path.exists() and path.stat().st_size > 0

    def test_paraphrase_retrieval(self, tmp_path):
        from src.figures import plot_paraphrase_retrieval

        data = {"model": "nomic-embed-text", "n_probes": 4, "surrogate_recall_at_1": 0.25, "learned_recall_at_1": 1.0}
        path = plot_paraphrase_retrieval(data, tmp_path / "para.png")
        assert path.exists() and path.stat().st_size > 0

    def test_zoomed_ylim_flat_and_spread(self):
        from src.figures import _zoomed_ylim

        lo, hi = _zoomed_ylim([0.62, 0.62, 0.62])  # flat -> honest window around value
        assert lo < 0.62 < hi
        lo2, hi2 = _zoomed_ylim([0.61, 0.70])  # spread -> tight band
        assert lo2 <= 0.61 and hi2 >= 0.70 and (hi2 - lo2) < 0.2

    def test_pipeline_flow_figure(self, tmp_path):
        from src.evaluation import pipeline_evidence_flow
        from src.figures import plot_pipeline_flow

        flow_data = pipeline_evidence_flow()
        # Verify the data structure
        assert len(flow_data) > 0
        for row in flow_data:
            assert "query" in row
            assert "task_category" in row
            assert "n_windows" in row
            assert "n_ranked" in row
            assert "n_cited" in row
        # Verify the figure is produced
        path = plot_pipeline_flow(flow_data, tmp_path / "pipeline_flow.png")
        assert path.exists() and path.stat().st_size > 0

    def test_category_components_figure(self, tmp_path):
        from src.evaluation import category_component_breakdown
        from src.figures import plot_category_components

        breakdown = category_component_breakdown()
        # All 6 TaskCategory values should be present
        assert len(breakdown) == 6
        for cat, components in breakdown.items():
            assert set(components) == {"accuracy", "grounding", "efficiency"}
            assert all(0.0 <= v <= 1.0 for v in components.values())
        path = plot_category_components(breakdown, tmp_path / "category_components.png")
        assert path.exists() and path.stat().st_size > 0

    def test_gepa_trajectory_figure(self, tmp_path):
        from src.evaluation import gepa_component_trajectory
        from src.figures import plot_gepa_trajectory

        trajectory = gepa_component_trajectory(iterations=3)

        # Verify the trajectory data structure
        assert len(trajectory) == 4  # 1 seed + 3 iterations
        for record in trajectory:
            assert set(record) == {
                "iteration",
                "composite",
                "accuracy",
                "grounding",
                "efficiency",
                "weakest_component",
            }
            assert record["weakest_component"] in ("accuracy", "grounding", "efficiency")
            assert 0.0 <= record["composite"] <= 1.0

        # Verify the figure is produced
        path = plot_gepa_trajectory(trajectory, tmp_path / "gepa_trajectory.png")
        assert path.exists() and path.stat().st_size > 0
