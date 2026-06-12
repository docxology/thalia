"""Static determinism-boundary tests."""

from src.determinism import scan_core_determinism, scan_zero_mock


class TestStaticDeterminism:
    def test_core_has_no_forbidden_imports_or_calls(self):
        assert scan_core_determinism() == ()

    def test_zero_mock_policy_has_no_mock_framework_usage(self):
        assert scan_zero_mock() == ()
