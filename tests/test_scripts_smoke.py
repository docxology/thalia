"""Smoke tests that the thin-orchestrator scripts actually run (Zero-Mock).

Each script is loaded from disk and its ``main()`` invoked in-process; we assert it
produces the artifact it advertises. Scripts are not measured for coverage, but
running them validates the end-to-end orchestration.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(stem: str) -> ModuleType:
    """Load a script module from disk by file stem (handles digit-prefixed names)."""
    path = SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(f"_thalia_script_{stem.replace('0', 'o')}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestScripts:
    def test_preflight(self):
        assert _load("00_preflight").main() == 0

    def test_run_harness_eval_writes_json(self, tmp_path):
        path = _load("run_harness_eval").main(tmp_path / "output", per_category_values=(1,), seeds=(0,))
        assert Path(path).exists()

    def test_run_compiler_writes_json(self):
        path = _load("run_compiler").main()
        assert Path(path).exists()

    def test_generate_figures_writes_pngs(self):
        paths = _load("generate_figures").main()
        assert paths and all(Path(p).exists() for p in paths)
        stems = {Path(p).stem for p in paths if Path(p).suffix == ".png"}
        for required in (
            "thalia_overview",
            "foundations_map",
            "memory_lifecycle",
            "gepa_evolution_loop",
        ):
            assert required in stems

    def test_manuscript_variables_token_coverage(self):
        path = _load("z_generate_manuscript_variables").main()
        assert Path(path).exists()

    def test_validate_artifacts_passes(self):
        # Keep this test order-independent: the validator is intentionally
        # fail-closed when a required artifact has not been generated yet.
        _load("run_pipeline").main()
        _load("run_demo").main()
        assert _load("validate_artifacts").main() == 0

    def test_build_dashboard_writes_html(self):
        path = _load("build_dashboard").main()
        assert Path(path).exists()
        assert Path(path).read_text().startswith("<!doctype html>")

    def test_run_demo_writes_artifacts(self):
        paths = _load("run_demo").main()
        assert paths
        assert all(Path(path).exists() for path in paths.values())

    def test_run_pipeline_writes_json(self):
        path = _load("run_pipeline").main()
        assert Path(path).exists()
        import json

        data = json.loads(Path(path).read_text())
        assert data["n_examples"] > 0
        assert all("intermediate_steps" in row for row in data["rows"])

    def test_run_query_cli(self):
        rc = _load("run_query").main(
            ["--query", "what is the wifi password", "--session-history", "User: my wifi password is bluefish42"]
        )
        assert rc == 0

    def test_run_query_demo_bare(self):
        # No args -> deterministic demo. The working-render pipeline runs every
        # script bare; this must exit 0 rather than fail on the required --query
        # (the defect that broke Stage 4 and blocked the PDF render).
        assert _load("run_query").main([]) == 0

    def test_run_dspy(self):
        # Real DSPy runtime writes JSON. Must not blow up.
        result = _load("run_dspy").main()
        assert isinstance(result, str)
        assert Path(result).exists()

    def test_run_learned_retrieval(self, tmp_path):
        # Real learned-embedder measurement when a model is live; clean exit-0
        # notice otherwise. The availability probe is a live external check and
        # can change between calls, so assert against the script's returned
        # contract rather than performing a second probe after it runs.
        result = _load("run_learned_retrieval").main(tmp_path / "learned_retrieval.json")
        if isinstance(result, str):
            assert Path(result).exists()
        else:
            assert result == 0

    def test_run_injection_probe(self, tmp_path):
        # Always writes the deterministic rows (+ neural when a model is live).
        result = _load("run_injection_probe").main(tmp_path / "injection_eval.json")
        assert Path(result).exists()

    def test_relabel_injection_probe_replays_retained_answers_without_model(self, tmp_path):
        source = SCRIPTS.parent / "data" / "injection_eval.json"
        target = tmp_path / "injection_eval.json"
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        before = json.loads(target.read_text(encoding="utf-8"))

        result = _load("run_injection_probe").main(
            target,
            relabel_recorded_answers=True,
        )
        relabelled = json.loads(target.read_text(encoding="utf-8"))

        assert result == str(target)
        assert relabelled["runtime_provenance"] == before["runtime_provenance"]
        assert relabelled["neural_model_metadata"] == before["neural_model_metadata"]
        assert relabelled["neural_poison_rate"] == 22 / 30
        assert sum(row["neural_poisoned"] for row in relabelled["neural_rows"]) == 22
        assert all(row["injected_answer"] for row in relabelled["rows"])
        assert all(row["injected_answer"] for row in relabelled["neural_rows"])

    def test_relabel_injection_probe_refuses_tampered_rows_without_rewrite(self, tmp_path):
        source = SCRIPTS.parent / "data" / "injection_eval.json"
        target = tmp_path / "injection_eval.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["neural_rows"][0]["query"] = "tampered"
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        before = target.read_text(encoding="utf-8")

        with pytest.raises(ValueError, match="does not bind to fixture 1"):
            _load("run_injection_probe").main(target, relabel_recorded_answers=True)

        assert target.read_text(encoding="utf-8") == before

    def test_run_openrouter(self):
        # OpenRouter script skips cleanly when no API key (exit 0).
        # When a key is set it writes the result JSON.
        result = _load("run_openrouter").main()
        assert result == 0 or Path(str(result)).exists()
