"""Static determinism guards for the ATLAS deterministic core."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

_CORE_ALLOWLIST = {
    Path("src/llm.py"),
    Path("src/dspy_runtime.py"),
    Path("src/retrieval/learned.py"),
}
_FORBIDDEN_IMPORTS = {
    "openai",
    "anthropic",
    "requests",
    "socket",
    "urllib",
    "urllib.request",
    "urllib.error",
    "time",
    "datetime",
    "unittest.mock",
}
_SEEDED_RANDOM_ALLOWLIST = {
    Path("src/evaluation/dataset.py"),
    Path("src/evaluation/scaling.py"),
}
_SELF = Path("src/determinism.py")


@dataclass(frozen=True)
class DeterminismIssue:
    """One static determinism-boundary finding."""

    path: str
    line: int
    detail: str


def scan_core_determinism(project_root: str | Path = PROJECT_ROOT) -> tuple[DeterminismIssue, ...]:
    """Return forbidden import/call issues in ``src/`` deterministic-core files."""
    root = Path(project_root)
    issues: list[DeterminismIssue] = []
    for path in sorted((root / "src").rglob("*.py")):
        rel = path.relative_to(root)
        if rel in _CORE_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _check_import(alias.name, rel, node.lineno, issues)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    _check_import(node.module, rel, node.lineno, issues)
            elif isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in {"random.random", "random.randrange", "random.choice"} and rel not in _SEEDED_RANDOM_ALLOWLIST:
                    issues.append(DeterminismIssue(rel.as_posix(), node.lineno, f"unseeded-looking RNG call: {name}"))
                if name in {"time.time", "datetime.datetime.now", "datetime.now"}:
                    issues.append(DeterminismIssue(rel.as_posix(), node.lineno, f"wall-clock call in core: {name}"))
    return tuple(issues)


def scan_zero_mock(project_root: str | Path = PROJECT_ROOT) -> tuple[DeterminismIssue, ...]:
    """Return mock-framework usage in ``tests/`` and deterministic source files."""
    root = Path(project_root)
    issues: list[DeterminismIssue] = []
    for base in (root / "src", root / "tests"):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(root)
            if rel == _SELF:
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if any(marker in line for marker in ("unittest.mock", "MagicMock", "mocker.patch")):
                    issues.append(DeterminismIssue(rel.as_posix(), lineno, "mock-framework usage is forbidden"))
    return tuple(issues)


def _check_import(module: str, rel: Path, line: int, issues: list[DeterminismIssue]) -> None:
    root = module.split(".", 1)[0]
    if module in _FORBIDDEN_IMPORTS or root in _FORBIDDEN_IMPORTS:
        issues.append(DeterminismIssue(rel.as_posix(), line, f"forbidden deterministic-core import: {module}"))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


__all__ = ["DeterminismIssue", "scan_core_determinism", "scan_zero_mock"]
