#!/usr/bin/env python3
"""Thin orchestrator: generate manuscript {{TOKEN}} values and verify coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = None

for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from src.manuscript_integrity import (  # noqa: E402
    check_bibliography_integrity,
    check_crossref_integrity,
    find_template_root,
    find_hardcoded_numeric_claims,
    load_claim_ledger,
    validate_claim_ledger,
    verify_injected_manuscript,
    verify_token_coverage,
    write_paper_audit_json,
)
from src.formalism_traceability import write_traceability_report  # noqa: E402
from src.manuscript_variables import generate_variables  # noqa: E402
from src.provenance import write_artifact_manifest  # noqa: E402

TEMPLATE_ROOT = find_template_root(starts=(Path.cwd(), PROJECT_ROOT))
if TEMPLATE_ROOT is not None and str(TEMPLATE_ROOT) not in sys.path:
    sys.path.insert(0, str(TEMPLATE_ROOT))


def main() -> Path:
    """Generate variables, verify manuscript token coverage, and serialise."""
    output_dir = PROJECT_ROOT / "output" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    manuscript_dir = PROJECT_ROOT / "manuscript"

    variables = generate_variables()
    validate_claim_ledger(load_claim_ledger(), project_root=PROJECT_ROOT)
    used, missing = verify_token_coverage(variables, manuscript_dir)
    if missing:
        raise SystemExit(
            f"manuscript uses {len(missing)} token(s) the generator does not emit: {missing}"
        )
    try:
        check_crossref_integrity(manuscript_dir)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        check_bibliography_integrity(manuscript_dir, manuscript_dir / "references.bib")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    hardcoded = find_hardcoded_numeric_claims(manuscript_dir)
    if hardcoded:
        raise SystemExit(
            "manuscript contains result-bearing numeric literals outside generated tokens: "
            + repr(hardcoded)
        )

    output_path = output_dir / "manuscript_variables.json"
    output_path.write_text(json.dumps(variables, indent=2, sort_keys=True))
    write_paper_audit_json(PROJECT_ROOT / "output" / "reports" / "paper_audit.json")
    # Source-only generation must work in a clean checkout.  The release
    # validator performs the stricter claim-artifact check after all generators.
    write_traceability_report(
        PROJECT_ROOT / "output" / "reports" / "formalism_traceability.json",
        check_artifacts=False,
    )
    manifest_path = write_artifact_manifest(PROJECT_ROOT)

    if TEMPLATE_ROOT is None:
        print(str(output_path))
        print(str(manifest_path))
        print(
            f"[ok] {len(used)} manuscript token(s) all generated; "
            "[skip] output/manuscript/ injection — template 'infrastructure' "
            "package not on path (run via the template pipeline to inject)."
        )
        return output_path

    from infrastructure.rendering.manuscript_injection import write_resolved_manuscript_tree  # type: ignore[import-not-found]

    injected = write_resolved_manuscript_tree(PROJECT_ROOT, variables)
    injected_files = verify_injected_manuscript(
        manuscript_dir,
        Path(injected),
        variables,
    )
    print(str(output_path))
    print(str(manifest_path))
    print(
        f"[ok] {len(used)} manuscript token(s) all generated; "
        f"{len(injected_files)} numbered section(s) exactly injected -> {injected}"
    )
    return output_path


if __name__ == "__main__":
    main()
