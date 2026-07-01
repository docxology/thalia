"""Manuscript / reproducibility integrity gates (Zero-Mock)."""

from pathlib import Path

import pytest

from src.manuscript_integrity import (
    check_crossref_integrity,
    find_template_root,
    verify_token_coverage,
)
from src.manuscript_variables import generate_variables

PROJECT = Path(__file__).resolve().parent.parent
MANUSCRIPT = PROJECT / "manuscript"
STALE_PREFIX = "projects_in_progress"


class TestReproPathHygiene:
    _EXCLUDE = ("/output/", "/.venv/", "/__pycache__/", "/.pytest_cache/", "/htmlcov/", ".egg-info")

    def _shipped_markdown(self) -> list[Path]:
        return [
            p
            for p in PROJECT.rglob("*.md")
            if not any(frag in str(p) for frag in self._EXCLUDE)
        ]

    def test_every_shipped_markdown_has_no_stale_path(self):
        docs = self._shipped_markdown()
        assert docs, "no markdown discovered — globbing is broken"
        offenders = [str(p.relative_to(PROJECT)) for p in docs if STALE_PREFIX in p.read_text()]
        assert not offenders, f"stale '{STALE_PREFIX}' path(s) in shipped docs: {offenders}"

    def test_documented_test_command_targets_real_repo_root_path(self):
        docs = [p for p in self._shipped_markdown() if "uv run" in p.read_text()]
        assert docs, "no documented uv commands discovered"
        offenders = []
        for doc in docs:
            text = doc.read_text()
            if "pytest" in text and "uv run --project working/thalia pytest working/thalia/tests/" not in text:
                offenders.append(str(doc.relative_to(PROJECT)))
            if "projects/working/thalia" in text:
                offenders.append(str(doc.relative_to(PROJECT)))
        assert offenders == []


class TestTemplateRootDiscovery:
    def test_find_template_root_detects_marker_in_ancestor(self, tmp_path):
        root = tmp_path / "tmpl"
        (root / "infrastructure" / "rendering").mkdir(parents=True)
        (root / "infrastructure" / "rendering" / "manuscript_injection.py").write_text("x = 1\n")
        nested = root / "projects" / "working" / "thalia" / "scripts"
        nested.mkdir(parents=True)
        assert find_template_root(starts=(nested,)) == root

    def test_find_template_root_returns_none_when_marker_absent(self, tmp_path):
        assert find_template_root(starts=(tmp_path,)) is None

    def test_find_template_root_detects_sibling_template_checkout(self, tmp_path):
        sidecar = tmp_path / "projects" / "working" / "thalia"
        sidecar.mkdir(parents=True)
        template = tmp_path / "template"
        (template / "infrastructure" / "rendering").mkdir(parents=True)
        (template / "infrastructure" / "rendering" / "manuscript_injection.py").write_text("x = 1\n")
        assert find_template_root(starts=(sidecar,)) == template

    def test_find_template_root_skips_duplicate_candidates(self, tmp_path):
        """Multiple starts that share ancestors should not cause duplicate work (line 29 continue)."""
        # Both starts share tmp_path as a common ancestor; neither has the marker.
        # The seen-set deduplication (line 29) prevents revisiting tmp_path twice.
        start_a = tmp_path / "proj_a"
        start_b = tmp_path / "proj_b"
        start_a.mkdir()
        start_b.mkdir()
        # No marker anywhere — should return None without errors.
        assert find_template_root(starts=(start_a, start_b)) is None


class TestCrossrefIntegrity:
    def test_dangling_crossref_raises(self, tmp_path):
        """check_crossref_integrity must raise ValueError for an @ref with no matching anchor."""
        md = tmp_path / "01_intro.md"
        # Reference an undefined label — no {#fig:missing} or \label{fig:missing} anywhere.
        md.write_text("See @fig:missing for details.\n")
        with pytest.raises(ValueError, match="dangling cross-reference"):
            check_crossref_integrity(tmp_path)

    def test_defined_crossref_does_not_raise(self, tmp_path):
        md = tmp_path / "01_intro.md"
        md.write_text("![caption](img.png){#fig:defined}\n\nAs shown in @fig:defined.\n")
        check_crossref_integrity(tmp_path)  # should not raise


class TestManuscriptGates:
    def test_token_coverage_passes(self):
        variables = generate_variables()
        used, missing = verify_token_coverage(variables, MANUSCRIPT)
        assert used
        assert missing == []

    def test_crossref_integrity_passes(self):
        check_crossref_integrity(MANUSCRIPT)

    def test_script_main_writes_json(self):
        import importlib.util

        path = PROJECT / "scripts" / "z_generate_manuscript_variables.py"
        spec = importlib.util.spec_from_file_location("_thalia_z_gen", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = mod.main()
        assert Path(out).exists()
        assert out.name == "manuscript_variables.json"

    def test_bounded_title_and_no_overstated_lead_claims(self):
        config = (MANUSCRIPT / "config.yaml").read_text()
        readme = (PROJECT / "README.md").read_text()
        package = (PROJECT / "src" / "__init__.py").read_text()

        assert "A Typed Agentic Harness for Reproducible Long-Context Memory Experiments" in config
        assert "Sophisticated DSPy + Hermes Auto-Harness" not in config
        assert "self-improving, declaratively-specified" not in readme
        assert "self-improving, declaratively-specified" not in package
        assert "self-improvement loop" not in (MANUSCRIPT / "04_harness_design.md").read_text()
        assert "self-improving agentic harness" not in (PROJECT / "tasks.yaml").read_text()

    def test_count_bearing_docs_use_generated_verification_summary(self):
        tasks = (PROJECT / "tasks.yaml").read_text()
        review = (PROJECT / "docs" / "code_quality_review.md").read_text()
        combined = "\n".join((tasks, review))

        assert "513 passed" not in combined
        assert "8 skipped" not in combined
        assert "98.97%" not in combined
        assert "99.17%" not in combined
        assert "536 passed, 2 skipped" not in combined
        assert "98.80%" not in combined
        assert "verification_summary.json" in combined

    def test_grep_claim_uses_source_qualified_language(self):
        intro = (MANUSCRIPT / "01_introduction.md").read_text()
        foundations = (MANUSCRIPT / "02_foundations.md").read_text()
        lexical = (PROJECT / "src" / "retrieval" / "lexical.py").read_text()

        combined = "\n".join((intro, foundations, lexical))
        assert "uniformly\n   stronger" not in combined
        assert "lexical search is uniformly" not in combined
        assert "generally" in combined and "tool-style-dependent" in combined

    def test_bibliography_has_corrected_and_added_keys(self):
        bib = (MANUSCRIPT / "references.bib").read_text()

        for key in (
            "wei2022cot",
            "yao2023react",
            "carbonell1998mmr",
            "sqlite2026fts5",
            "anthropic2025mcp",
            "agrawal2025gepa",
            "gemma2025gemma3",
            "nussbaum2024nomic",
            "packer2023memgpt",
            "chhikara2025mem0",
            "li2026timem",
            "banerjee2026apexmem",
        ):
            assert f"{{{key}," in bib
        assert "Santhanam, Keshav" in bib
        assert "Sen, Sahil" in bib and "Kasturi, Akhil" in bib and "Lumer, Elias" in bib
        assert "Zhang, Dylan" in bib and "Lin, Yanshan" in bib and "Wu, Zhengkun" in bib

    def test_injection_and_figure_captions_are_small_n_honest(self):
        evaluation = (MANUSCRIPT / "07_evaluation.md").read_text()

        assert "true source in its cited evidence" in evaluation
        assert evaluation.count("true source in its cited evidence") == 1
        assert "the dashed line marks the overall composite" not in evaluation
        assert "exact cases, not population rates" in evaluation
        assert "optional neural rows appear only when" in evaluation
