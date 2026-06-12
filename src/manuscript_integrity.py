"""Manuscript reproducibility gates: token coverage and cross-reference integrity."""

from __future__ import annotations

import re
from pathlib import Path

_TOKEN_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
_REF_RE = re.compile(r"@((?:fig|sec|tbl|eq):[A-Za-z0-9_-]+)")
_DEF_BRACE_RE = re.compile(r"\{#((?:fig|sec|tbl|eq):[A-Za-z0-9_-]+)[^}]*\}")
_DEF_LABEL_RE = re.compile(r"\\label\{((?:fig|sec|tbl|eq):[A-Za-z0-9_-]+)\}")

_INJECTION_MARKER = Path("infrastructure") / "rendering" / "manuscript_injection.py"


def find_template_root(starts: tuple[Path, ...] | None = None) -> Path | None:
    """Return the template repo root containing ``infrastructure/rendering/``.

    Walks ancestors from each start path until the injection module exists. For
    private sidecar checkouts, also checks for a sibling ``template/`` checkout
    next to the ``projects/`` repo. Returns ``None`` when ATLAS runs standalone
    outside any template tree.
    """
    seen: set[Path] = set()
    origins = starts if starts is not None else (Path.cwd(),)
    for start in origins:
        for candidate in (start, *start.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / _INJECTION_MARKER).exists():
                return candidate
            sibling_template = candidate / "template"
            if sibling_template not in seen and (sibling_template / _INJECTION_MARKER).exists():
                return sibling_template
    return None


def numbered_sections(manuscript_dir: Path) -> list[Path]:
    """Return numbered manuscript body files (``00_*.md`` … ``99_*.md``)."""
    return sorted(manuscript_dir.glob("[0-9]*.md"))


def tokens_used_in_manuscript(manuscript_dir: Path) -> set[str]:
    """Collect every ``{{TOKEN}}`` referenced in numbered body sections."""
    used: set[str] = set()
    for md in numbered_sections(manuscript_dir):
        used.update(_TOKEN_RE.findall(md.read_text()))
    return used


def check_crossref_integrity(manuscript_dir: Path) -> None:
    """Raise ValueError if any cross-reference lacks a definition anchor."""
    defined: set[str] = set()
    referenced: set[str] = set()
    for md in numbered_sections(manuscript_dir):
        body = md.read_text()
        defined.update(_DEF_BRACE_RE.findall(body))
        defined.update(_DEF_LABEL_RE.findall(body))
        referenced.update(_REF_RE.findall(body))
    dangling = sorted(referenced - defined)
    if dangling:
        raise ValueError(
            f"manuscript has {len(dangling)} dangling cross-reference(s): {dangling}"
        )


def verify_token_coverage(
    variables: dict[str, str],
    manuscript_dir: Path,
) -> tuple[set[str], list[str]]:
    """Return (tokens used, sorted missing tokens not in ``variables``)."""
    used = tokens_used_in_manuscript(manuscript_dir)
    missing = sorted(used - set(variables))
    return used, missing


__all__ = [
    "find_template_root",
    "numbered_sections",
    "tokens_used_in_manuscript",
    "check_crossref_integrity",
    "verify_token_coverage",
]
