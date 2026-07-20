"""Static determinism-boundary tests."""

import tempfile
from pathlib import Path

from src.determinism import scan_core_determinism, scan_zero_mock

# Marker strings split so this test file doesn't trip the scanner itself.
_UT_MOCK = "unittest" + ".mock"
_MAGIC_MOCK = "Magic" + "Mock"
_MOCKER_PATCH = "mocker" + ".patch"


class TestStaticDeterminism:
    def test_core_has_no_forbidden_imports_or_calls(self):
        assert scan_core_determinism() == ()

    def test_zero_mock_policy_has_no_mock_framework_usage(self):
        assert scan_zero_mock() == ()


class TestScanCoreDeterminismUncoveredPaths:
    """Tests that exercise uncovered branches in scan_core_determinism."""

    def _make_src(self, tmp: Path) -> Path:
        """Create a src/ directory under tmp and return it."""
        src = tmp / "src"
        src.mkdir(parents=True, exist_ok=True)
        return src

    def test_unseeded_rng_calls_flagged(self):
        """Line 64: RNG calls (random.random/randrange/choice) outside allowlist are issues."""
        with tempfile.TemporaryDirectory() as td:
            src = self._make_src(Path(td))
            (src / "core_rng.py").write_text(
                "import random\n"
                "x = random.random()\n"
                "y = random.randrange(10)\n"
                "z = random.choice([1, 2, 3])\n",
                encoding="utf-8",
            )
            issues = scan_core_determinism(project_root=td)

        details = [i.detail for i in issues]
        assert any("random.random" in d for d in details), issues
        assert any("random.randrange" in d for d in details), issues
        assert any("random.choice" in d for d in details), issues
        for issue in issues:
            assert "unseeded-looking RNG call" in issue.detail

    def test_unseeded_rng_not_flagged_in_allowlist_file(self):
        """Files in _SEEDED_RANDOM_ALLOWLIST should not be flagged for RNG calls."""
        with tempfile.TemporaryDirectory() as td:
            src = self._make_src(Path(td))
            # Replicate the allowlist path structure inside the temp tree
            allowed_dir = src / "evaluation"
            allowed_dir.mkdir(parents=True, exist_ok=True)
            (allowed_dir / "dataset.py").write_text(
                "import random\nx = random.random()\n", encoding="utf-8"
            )
            issues = scan_core_determinism(project_root=td)

        # No RNG issues expected — the file is on the allowlist
        rng_issues = [i for i in issues if "unseeded-looking RNG call" in i.detail]
        assert rng_issues == [], rng_issues

    def test_wall_clock_calls_flagged(self):
        """Line 66: wall-clock calls (time.time, datetime.datetime.now, datetime.now)."""
        with tempfile.TemporaryDirectory() as td:
            src = self._make_src(Path(td))
            (src / "core_time.py").write_text(
                "import time\nimport datetime\n"
                "t = time.time()\n"
                "now1 = datetime.datetime.now()\n"
                "now2 = datetime.now()\n",
                encoding="utf-8",
            )
            issues = scan_core_determinism(project_root=td)

        details = [i.detail for i in issues]
        wall_clock = [d for d in details if "wall-clock call in core" in d]
        assert len(wall_clock) >= 1, f"Expected wall-clock issues, got: {details}"
        assert any("time.time" in d for d in wall_clock), wall_clock

    def test_root_module_forbidden_import_flagged(self):
        """Line 91: root-module check catches dotted imports like 'openai.chat'."""
        with tempfile.TemporaryDirectory() as td:
            src = self._make_src(Path(td))
            (src / "calls_openai.py").write_text(
                "import openai.chat\n", encoding="utf-8"
            )
            issues = scan_core_determinism(project_root=td)

        assert len(issues) >= 1, issues
        assert any("openai.chat" in i.detail for i in issues), issues
        assert any("forbidden deterministic-core import" in i.detail for i in issues)

    def test_root_module_exact_forbidden_import_flagged(self):
        """_check_import: module in _FORBIDDEN_IMPORTS path (e.g. plain 'openai')."""
        with tempfile.TemporaryDirectory() as td:
            src = self._make_src(Path(td))
            (src / "calls_openai_plain.py").write_text(
                "import openai\n", encoding="utf-8"
            )
            issues = scan_core_determinism(project_root=td)

        assert any("openai" in i.detail for i in issues), issues


class TestScanZeroMockUncoveredPaths:
    """Tests that exercise uncovered branches in scan_zero_mock."""

    def test_nonexistent_root_returns_no_issues(self):
        """Line 76: if not base.exists(): continue — scanning a root with no src/tests dirs."""
        with tempfile.TemporaryDirectory() as td:
            empty_root = Path(td) / "does_not_exist"
            # Do NOT create the directory — both src/ and tests/ are absent
            issues = scan_zero_mock(project_root=empty_root)

        assert issues == ()

    def test_partial_root_only_src_exists(self):
        """Line 76: tests/ is missing but src/ exists — only src/ is scanned."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "clean.py").write_text("x = 1\n", encoding="utf-8")
            # tests/ intentionally absent
            issues = scan_zero_mock(project_root=root)

        assert issues == ()

    def test_mock_framework_usage_flagged_in_src(self):
        """Line 84: mock usage in src/ files triggers an issue."""
        # Build forbidden content dynamically so this file doesn't trip the scanner.
        forbidden_content = f"import {_UT_MOCK}\nfrom {_UT_MOCK} import {_MAGIC_MOCK}\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "uses_mock.py").write_text(forbidden_content, encoding="utf-8")
            issues = scan_zero_mock(project_root=root)

        assert len(issues) >= 1, issues
        for issue in issues:
            assert issue.detail == "mock-framework usage is forbidden"

    def test_mock_framework_usage_flagged_in_tests(self):
        """Line 84: mock usage in tests/ files triggers an issue."""
        forbidden_content = (
            f"from {_UT_MOCK} import patch\n"
            f"{_MOCKER_PATCH}('os.path.exists')\n"
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_with_mock.py").write_text(forbidden_content, encoding="utf-8")
            issues = scan_zero_mock(project_root=root)

        assert len(issues) >= 1, issues
        assert any(i.path.startswith("tests/") for i in issues), issues

    def test_magicmock_marker_flagged(self):
        """Line 84: magic-mock class mention in a line triggers issue."""
        forbidden_content = f"# {_MAGIC_MOCK} should not be here\nm = {_MAGIC_MOCK}()\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "has_magic.py").write_text(forbidden_content, encoding="utf-8")
            issues = scan_zero_mock(project_root=root)

        assert len(issues) >= 1, issues
        paths = [i.path for i in issues]
        assert any("has_magic.py" in p for p in paths), paths
