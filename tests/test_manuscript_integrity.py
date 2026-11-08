"""Manuscript / reproducibility integrity gates (Zero-Mock)."""

import json
from pathlib import Path
import re
from typing import Any, cast

import pytest

from src.manuscript_integrity import (
    check_bibliography_integrity,
    check_crossref_integrity,
    find_hardcoded_numeric_claims,
    find_template_root,
    load_claim_ledger,
    validate_claim_ledger,
    validate_integrity_advantage_report,
    verify_injected_manuscript,
    verify_token_coverage,
    load_paper_audit,
    validate_paper_audit,
)
from src.manuscript_variables import generate_variables

PROJECT = Path(__file__).resolve().parent.parent
MANUSCRIPT = PROJECT / "docs" / "manuscript"


class TestReproPathHygiene:
    _EXCLUDE = ("/output/", "/.venv/", "/__pycache__/", "/.pytest_cache/", "/htmlcov/", ".egg-info")
    _LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

    def _shipped_markdown(self) -> list[Path]:
        return [
            p
            for p in PROJECT.rglob("*.md")
            if not any(frag in str(p) for frag in self._EXCLUDE)
        ]

    def test_local_markdown_links_resolve(self):
        """Keep documentation signposts real as sections are split or renamed."""
        offenders: list[tuple[str, str]] = []
        variables = generate_variables()
        for doc in self._shipped_markdown():
            for raw_target in self._LINK_RE.findall(doc.read_text(encoding="utf-8")):
                for token in sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", raw_target))):
                    assert token in variables, f"unresolved link token in {doc}: {token}"
                    raw_target = raw_target.replace("{{" + token + "}}", variables[token])
                target = raw_target.strip()
                if target.startswith("<") and ">" in target:
                    target = target[1 : target.index(">")]
                else:
                    target = target.split()[0]
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                local_target = target.split("#", 1)[0]
                if local_target and not (doc.parent / local_target).resolve().exists():
                    offenders.append((str(doc.relative_to(PROJECT)), target))
        assert offenders == [], f"broken local Markdown links: {offenders}"


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


class TestBibliographyIntegrity:
    def test_current_manuscript_citations_have_bibliography_entries(self):
        used, declared = check_bibliography_integrity(MANUSCRIPT, MANUSCRIPT / "references.bib")
        assert used
        assert used <= declared

    def test_missing_bibliography_key_raises(self, tmp_path):
        (tmp_path / "01_intro.md").write_text("A claim [@missing2026]. Narrative @missing2027.\n")
        (tmp_path / "references.bib").write_text("@article{present2026,\n  title = {Present}\n}\n")
        with pytest.raises(ValueError, match="missing from bibliography"):
            check_bibliography_integrity(tmp_path, tmp_path / "references.bib")


class TestManuscriptGates:
    def test_paper_audit_ledger_is_valid(self):
        validate_paper_audit(load_paper_audit())

    def test_claim_ledger_matches_generated_json_artifacts(self):
        # Source-only validation keeps the unit suite runnable before output/ is generated;
        # scripts/validate_artifacts.py owns the strict release-time artifact check.
        validate_claim_ledger(load_claim_ledger(), project_root=PROJECT)

    def test_integrity_advantage_report_is_source_bound_and_unpromoted(self):
        validate_integrity_advantage_report(project_root=PROJECT)

    def test_integrity_advantage_report_rejects_promoted_unexecuted_p0(self, tmp_path):
        source = PROJECT / "data" / "integrity_advantage.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        promotion = dict(payload["promotion"])
        promotion.update(
            {
                "status": "promoted",
                "promoted": True,
                "promotion_gate_passed": True,
            }
        )
        payload["promotion"] = promotion
        report = tmp_path / "integrity_advantage.json"
        report.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ValueError, match="unexecuted P0 integrity evidence"):
            validate_integrity_advantage_report(project_root=PROJECT, report_path=report)

    def test_integrity_advantage_report_rejects_drifted_source_fingerprint(self, tmp_path):
        source = PROJECT / "data" / "integrity_advantage.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["source_provenance"][0]["sha256"] = "0" * 64
        report = tmp_path / "integrity_advantage.json"
        report.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ValueError, match="source_provenance\\[0\\].sha256 does not match"):
            validate_integrity_advantage_report(project_root=PROJECT, report_path=report)

    def test_integrity_advantage_report_rejects_missing_source_input(self, tmp_path):
        source = PROJECT / "data" / "integrity_advantage.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["source_provenance"] = [
            entry
            for entry in payload["source_provenance"]
            if entry["path"] != "data/injection_eval.json"
        ]
        report = tmp_path / "integrity_advantage.json"
        report.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ValueError, match="missing source inputs"):
            validate_integrity_advantage_report(project_root=PROJECT, report_path=report)

    def test_claim_ledger_checks_json_field_when_artifacts_exist(self, tmp_path):
        artifact = tmp_path / "metrics.json"
        artifact.write_text('{"score": 0.5}\n')
        payload = {
            "claims": [
                {
                    "claim_id": "score",
                    "kind": "number",
                    "value": 0.5,
                    "source": "test",
                    "source_tier": "generated_metric",
                    "freshness": "active",
                    "artifact_path": "metrics.json",
                    "artifact_field": "score",
                }
            ]
        }
        validate_claim_ledger(payload, project_root=tmp_path, check_artifacts=True)

    def test_claim_ledger_rejects_unsafe_artifact_path(self):
        ledger = cast(dict[str, Any], load_claim_ledger())
        payload = {"claims": [dict(ledger["claims"][0], artifact_path="../outside.json")]}
        with pytest.raises(ValueError, match="unsafe artifact path"):
            validate_claim_ledger(payload, project_root=PROJECT)

    def test_token_coverage_passes(self):
        variables = generate_variables()
        used, missing = verify_token_coverage(variables, MANUSCRIPT)
        assert used
        assert missing == []

    def test_injected_manuscript_matches_exact_source_substitution(self, tmp_path):
        source = tmp_path / "manuscript"
        injected = tmp_path / "output" / "manuscript"
        source.mkdir()
        injected.mkdir(parents=True)
        (source / "01_intro.md").write_text("Value {{ANSWER}}.\n", encoding="utf-8")
        (injected / "01_intro.md").write_text("Value blue.\n", encoding="utf-8")

        checked = verify_injected_manuscript(source, injected, {"ANSWER": "blue"})

        assert checked == (injected / "01_intro.md",)

    def test_injected_manuscript_rejects_file_set_drift(self, tmp_path):
        source = tmp_path / "manuscript"
        injected = tmp_path / "injected"
        source.mkdir()
        injected.mkdir()
        (source / "01_intro.md").write_text("ok\n", encoding="utf-8")
        (injected / "02_extra.md").write_text("ok\n", encoding="utf-8")

        with pytest.raises(ValueError, match="file set drift"):
            verify_injected_manuscript(source, injected, {})

    def test_injected_manuscript_rejects_unresolved_token(self, tmp_path):
        source = tmp_path / "manuscript"
        injected = tmp_path / "injected"
        source.mkdir()
        injected.mkdir()
        (source / "01_intro.md").write_text("Value {{ANSWER}}.\n", encoding="utf-8")
        (injected / "01_intro.md").write_text("Value {{ANSWER}}.\n", encoding="utf-8")

        with pytest.raises(ValueError, match="unresolved tokens"):
            verify_injected_manuscript(source, injected, {"ANSWER": "blue"})

    def test_injected_manuscript_rejects_content_drift(self, tmp_path):
        source = tmp_path / "manuscript"
        injected = tmp_path / "injected"
        source.mkdir()
        injected.mkdir()
        (source / "01_intro.md").write_text("Value {{ANSWER}}.\n", encoding="utf-8")
        (injected / "01_intro.md").write_text("Value green.\n", encoding="utf-8")

        with pytest.raises(ValueError, match="exact source token substitution"):
            verify_injected_manuscript(source, injected, {"ANSWER": "blue"})

    def test_result_bearing_numeric_literals_are_tokenized(self):
        findings = find_hardcoded_numeric_claims(MANUSCRIPT)
        assert findings == [], "hardcoded manuscript result numbers: " + repr(findings)

    def test_numeric_lint_reports_result_literal_with_location(self, tmp_path):
        body = tmp_path / "07_results.md"
        body.write_text("The measured accuracy was 0.75 across 12 examples.\n")
        findings = find_hardcoded_numeric_claims(tmp_path)
        assert findings == [("07_results.md", 1, body.read_text().strip())]

    def test_numeric_lint_allows_tokens_code_and_equations(self, tmp_path):
        body = tmp_path / "07_results.md"
        body.write_text(
            "The measured accuracy was {{RESULT_ACCURACY}}.\n"
            "```text\naccuracy 0.75 across 12 examples\n```\n"
            "The metric is $1 - |ranked|/N$ with N as the budget.\n"
        )
        assert find_hardcoded_numeric_claims(tmp_path) == []

    def test_numeric_lint_catches_result_next_to_equation(self, tmp_path):
        body = tmp_path / "07_results.md"
        body.write_text("The measured accuracy was 0.75 under $1 - |ranked|/N$.\n")
        findings = find_hardcoded_numeric_claims(tmp_path)
        assert findings == [("07_results.md", 1, body.read_text().strip())]

    def test_crossref_integrity_passes(self):
        check_crossref_integrity(MANUSCRIPT)

