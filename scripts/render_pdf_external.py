#!/usr/bin/env python3
"""Render and optionally validate THALIA through the sibling template checkout.

The template renderer resolves projects by name.  This thin adapter exposes the
standalone THALIA checkout through a temporary, exact symlink for the duration
of the call, then removes only that link.  The sibling template remains
unchanged after the command exits.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_NAME = PROJECT_ROOT.name

for candidate in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from src.manuscript_integrity import find_template_root  # noqa: E402
from src.provenance import validate_artifact_manifest  # noqa: E402


@contextmanager
def _template_project_link(template_root: Path) -> Iterator[str]:
    """Expose this checkout under the template's WIP namespace temporarily."""
    working_dir = template_root / "projects" / "working"
    working_dir.mkdir(parents=True, exist_ok=True)
    link = working_dir / PROJECT_NAME
    resolved_project = PROJECT_ROOT.resolve()
    if link.exists() or link.is_symlink():
        if link.resolve() != resolved_project:
            raise RuntimeError(
                f"refusing to replace existing template path {link}; "
                f"it resolves to {link.resolve()}"
            )
        yield f"working/{PROJECT_NAME}"
        return

    link.symlink_to(resolved_project, target_is_directory=True)
    try:
        yield f"working/{PROJECT_NAME}"
    finally:
        if link.is_symlink() and link.resolve() == resolved_project:
            link.unlink()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render THALIA's manuscript via the sibling template checkout."
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run template-side output validation after rendering.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate frozen retained outputs without rendering or refreshing evidence.",
    )
    parser.add_argument(
        "--template-root",
        type=Path,
        help="Use an explicit template checkout, such as a clean pinned worktree.",
    )
    parser.add_argument(
        "--skip-manuscript-hydration",
        action="store_true",
        help="Skip token hydration (use only when output/manuscript is already fresh).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Render or validate retained outputs, preserving each manifest's ownership."""
    args = _build_parser().parse_args(argv)
    template_root = args.template_root.resolve() if args.template_root else find_template_root(starts=(PROJECT_ROOT,))
    if template_root is None or not (template_root / "infrastructure" / "rendering").is_dir():
        print(
            "No sibling template checkout with infrastructure/rendering was found; "
            "PDF rendering is an external integration prerequisite.",
            file=sys.stderr,
        )
        return 2

    if str(template_root) not in sys.path:
        sys.path.insert(0, str(template_root))

    with _template_project_link(template_root) as project_name:
        if not args.validate_only:
            from infrastructure.rendering.pipeline import execute_render_pipeline  # type: ignore[import-not-found]

            status = execute_render_pipeline(
                project_name,
                repo_root=template_root,
                skip_manuscript_hydration=args.skip_manuscript_hydration,
            )
            if status != 0:
                return status

        if args.validate or args.validate_only:
            from infrastructure.validation.output.pipeline import execute_validation_pipeline  # type: ignore[import-not-found]

            status = execute_validation_pipeline(project_name, repo_root=template_root)
            if status != 0:
                return status

        # Rendering owns artifact_manifest.json, never THALIA's required-data
        # manifest. Validation must detect drift rather than refresh its hashes.
        report = validate_artifact_manifest(PROJECT_ROOT)
        for issue in report.issues:
            print(f"[error] {issue}", file=sys.stderr)
        return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
