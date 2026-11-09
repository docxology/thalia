"""Tests for manuscript variable generation (Zero-Mock)."""

import json
import copy

import pytest

from src import __version__
from src.manuscript_variables import generate_variables
from src.evaluation.backend_benchmark import BenchmarkBackend, build_benchmark_methods, run_backend_benchmark
from src.llm import CallableLM
from src.module import ExtractiveLM


class TestGenerateVariables:
    def test_missing_neural_eval_raises_clearly(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_NEURAL_EVAL_PATH", tmp_path / "absent.json")
        with pytest.raises(FileNotFoundError):
            mv.generate_variables()

    def test_missing_learned_eval_raises_clearly(self, monkeypatch, tmp_path):
        """Missing retained model evidence must not acquire a synthetic fallback."""
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_LEARNED_EVAL_PATH", tmp_path / "absent_learned.json")
        with pytest.raises(FileNotFoundError):
            mv.generate_variables()

    def test_all_values_are_strings(self):
        variables = generate_variables()
        assert all(isinstance(v, str) for v in variables.values())


    def test_missing_v2_aggregate_raises_clearly(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_SEED_SENSITIVITY_PATH", tmp_path / "absent_seed.json")
        with pytest.raises(FileNotFoundError):
            mv.generate_variables()


    def test_current_and_archived_identities_are_source_bound(self):
        import src.manuscript_variables as mv

        metadata = json.loads(mv._ZENODO_METADATA_PATH.read_text())
        archived = next(
            item["identifier"]
            for item in metadata["related_identifiers"]
            if item["relation"] == "isNewVersionOf"
        )
        variables = generate_variables()
        assert variables["ARCHIVED_RELEASE_DOI"] == archived
        assert variables["CURRENT_RELEASE_VERSION"] == __version__
        assert variables["CURRENT_RELEASE_URL"] == (
            f"https://github.com/docxology/thalia/releases/tag/v{__version__}"
        )

    @pytest.mark.parametrize(
        "metadata",
        [
            {},
            [],
            {"related_identifiers": None},
            {"related_identifiers": [None]},
            {"related_identifiers": [{"relation": "isIdenticalTo", "scheme": "doi"}]},
        ],
    )
    def test_missing_archive_relation_fails_closed(self, monkeypatch, tmp_path, metadata):
        import src.manuscript_variables as mv

        path = tmp_path / ".zenodo.json"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError):
            mv.generate_variables()

    @pytest.mark.parametrize("identifier", [None, 42, "", "not-a-doi", "10.5281/has whitespace"])
    def test_invalid_archived_doi_fails_closed(self, monkeypatch, tmp_path, identifier):
        import src.manuscript_variables as mv

        metadata = {
            "related_identifiers": [
                {"relation": "isNewVersionOf", "scheme": "doi", "identifier": identifier}
            ]
        }
        path = tmp_path / ".zenodo.json"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError):
            mv.generate_variables()

    @pytest.mark.parametrize("change", ["duplicate", "wrong_scheme"])
    def test_ambiguous_or_non_doi_archive_fails_closed(self, monkeypatch, tmp_path, change):
        import src.manuscript_variables as mv

        metadata = json.loads(mv._ZENODO_METADATA_PATH.read_text())
        archive = next(
            item for item in metadata["related_identifiers"] if item["relation"] == "isNewVersionOf"
        )
        if change == "duplicate":
            metadata["related_identifiers"].append(dict(archive))
        else:
            archive["scheme"] = "url"
        path = tmp_path / ".zenodo.json"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError):
            mv.generate_variables()

    @pytest.mark.parametrize("contents", [None, "{", b"\xff"])
    def test_unreadable_archive_metadata_fails_closed(self, monkeypatch, tmp_path, contents):
        import src.manuscript_variables as mv

        path = tmp_path / ".zenodo.json"
        if isinstance(contents, str):
            path.write_text(contents, encoding="utf-8")
        elif isinstance(contents, bytes):
            path.write_bytes(contents)
        monkeypatch.setattr(mv, "_ZENODO_METADATA_PATH", path)
        with pytest.raises(ValueError):
            mv.generate_variables()

    def test_deterministic(self):
        assert generate_variables() == generate_variables()

    def test_bottleneck_aggregate_requires_mode_breakdown(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        original = json.loads(mv._LME_BN_PATH.read_text())
        original.pop("ranking_recall_by_mode", None)
        path = tmp_path / "longmemeval_bottleneck.json"
        path.write_text(json.dumps(original), encoding="utf-8")
        monkeypatch.setattr(mv, "_LME_BN_PATH", path)

        with pytest.raises(KeyError, match="ranking_recall_by_mode"):
            mv.generate_variables()

    def test_missing_audit_bundle_raises_clearly(self, monkeypatch, tmp_path):
        import src.manuscript_variables as mv

        monkeypatch.setattr(mv, "_EVAL_RESULTS_PATH", tmp_path / "absent_eval.json")
        with pytest.raises(FileNotFoundError):
            mv.generate_variables()


def _failed_completion(prompt):
    raise RuntimeError("real callable failure")


@pytest.fixture(scope="module")
def method_report():
    return run_backend_benchmark(
        [BenchmarkBackend("baseline <&>|", "extractive", "ExtractiveLM <model>", ExtractiveLM())],
        methods=build_benchmark_methods(("full_context", "harness")),
        per_category=1, seeds=(0, 1), limit=4, n_boot=10,
    )


class TestBackendMethodVariables:
    def test_missing_is_explicit(self, tmp_path):
        from src.manuscript_variables import _backend_benchmark_variables

        variables = _backend_benchmark_variables(tmp_path / "missing.json")
        assert variables["BACKEND_BENCHMARK_STATUS"] == "not recorded"
        assert variables["BACKEND_SEED_PAIR_TABLE"] == (
            "No per-seed paired audit is recorded; no benchmark report supplied."
        )

    def test_selected_path_must_exist(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            generate_variables(backend_benchmark_path=tmp_path / "missing.json")


    @pytest.mark.parametrize("change", ["schema1", "summary", "method", "comparison", "group", "source"])
    def test_mutation_fails_closed(self, tmp_path, method_report, change):
        from src.manuscript_variables import _backend_benchmark_variables

        payload = copy.deepcopy(method_report)
        if change == "schema1":
            payload["schema_version"] = 1
        elif change == "summary":
            payload["summaries"][0]["mean_token_f1"] = 999
        elif change == "method":
            payload["methods"][0]["kind"] = "unknown"
        elif change == "comparison":
            payload["comparisons"][0]["n_complete_pairs"] += 1
        elif change == "group":
            payload["groups"]["stratum"][0]["n_failed"] += 1
        else:
            payload["producer_provenance"] = {}
        path = tmp_path / "mutated.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            _backend_benchmark_variables(path)

    def test_explicit_incomplete_artifact_is_not_promoted(self, tmp_path):
        payload = run_backend_benchmark(
            [
                BenchmarkBackend("baseline", "extractive", "ExtractiveLM", ExtractiveLM()),
                BenchmarkBackend("failed", "callable", "failed", CallableLM(_failed_completion)),
            ],
            methods=build_benchmark_methods(("full_context", "harness")),
            per_category=1, limit=2,
        )
        path = tmp_path / "selected.incomplete.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        variables = generate_variables(backend_benchmark_path=path)
        assert variables["BACKEND_BENCHMARK_STATUS"] == "incomplete"
        assert "incomplete: paired estimate suppressed" in variables["BACKEND_COMPARISON_TABLE"]
        assert "single-seed: interval unavailable" in variables["BACKEND_COMPARISON_TABLE"]
        assert "failed" in variables["BACKEND_BENCHMARK_TABLE"]
        assert "| harness | 0 | 2 / 0 | 0 / 0 / 0 | not recorded | incomplete: seed mean suppressed |" in (
            variables["BACKEND_SEED_PAIR_TABLE"]
        )
        assert "| harness | 0 | 2 / 2 |" in variables["BACKEND_SEED_PAIR_TABLE"]

    def test_missing_reference_has_no_inferred_comparison(self, tmp_path):
        from src.manuscript_variables import _backend_benchmark_variables

        payload = run_backend_benchmark(
            [BenchmarkBackend("baseline", "extractive", "ExtractiveLM", ExtractiveLM())],
            per_category=1, limit=2,
        )
        path = tmp_path / "harness-only.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        variables = _backend_benchmark_variables(path)
        assert "Reference method absent" in variables["BACKEND_COMPARISON_TABLE"]
        assert "Reference method absent" in variables["BACKEND_SEED_PAIR_TABLE"]
        assert "| Method | Seed |" not in variables["BACKEND_SEED_PAIR_TABLE"]

    def test_seed_audit_is_grouped_and_escaped(self, tmp_path, method_report):
        from src.manuscript_variables import _backend_benchmark_variables

        path = tmp_path / "selected.json"
        path.write_text(json.dumps(method_report), encoding="utf-8")
        variables = _backend_benchmark_variables(path)
        audit = variables["BACKEND_SEED_PAIR_TABLE"]
        assert "**Backend:** baseline &lt;&amp;&gt;\\|" in audit
        assert "**model:** ExtractiveLM &lt;model&gt;" in audit
        assert "**Reference:** full\\_context." in audit
        assert "| Method | Seed | Pairs R/C | W / T / L | Mean delta | Status |" in audit
        matrix = {(row["method"], row["example_id"]): row for row in method_report["rows"]}
        for seed in (0, 1):
            examples = [example for example in method_report["examples"] if example["seed"] == seed]
            deltas = [
                matrix[("harness", example["example_id"])]["token_f1"]
                - matrix[("full_context", example["example_id"])]["token_f1"]
                for example in examples
            ]
            assert (
                f"| harness | {seed} | {len(examples)} / {len(examples)} | "
                f"{sum(delta > 0 for delta in deltas)} / {sum(delta == 0 for delta in deltas)} / "
                f"{sum(delta < 0 for delta in deltas)} | {sum(deltas) / len(deltas):.3f} | complete |"
            ) in audit

    def test_partial_seed_is_suppressed_without_discarding_complete_seed(self, tmp_path):
        from src.manuscript_variables import _backend_benchmark_variables

        calls = 0

        def complete(prompt):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("first real completion fails")
            return ExtractiveLM().complete(prompt)

        payload = run_backend_benchmark(
            [BenchmarkBackend("partial", "callable", "offline", CallableLM(complete))],
            methods=build_benchmark_methods(("full_context", "harness")),
            seeds=(9, 2), per_category=1, limit=3, n_boot=10,
        )
        path = tmp_path / "partial.incomplete.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        variables = _backend_benchmark_variables(path)
        audit = variables["BACKEND_SEED_PAIR_TABLE"].split("**Backend:** partial", 1)[1]
        rows = [
            [value.strip() for value in line.strip("|").split("|")]
            for line in audit.splitlines() if line.startswith("| harness |")
        ]
        assert [int(row[1]) for row in rows] == [2, 9]
        assert {row[2].split(" / ")[0] for row in rows} == {"1", "2"}
        assert any(row[4] == "not recorded" and row[2] == "2 / 1" for row in rows)
        assert any(row[-1] == "complete" and row[-2] != "not recorded" for row in rows)
        comparison = next(
            row for row in payload["comparisons"]
            if row["backend"] == "partial" and row["method"] == "harness"
        )
        assert comparison["mean_delta"] is None and comparison["interval"] is None

