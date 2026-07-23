#!/usr/bin/env python3
"""Thin orchestrator: validate the generated artifact manifest and refuse drift."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.formalism_traceability import load_and_validate_traceability  # noqa: E402
from src.manuscript_integrity import (  # noqa: E402
    check_bibliography_integrity,
    load_claim_ledger,
    validate_claim_ledger,
)
from src.provenance import validate_artifact_manifest  # noqa: E402


def main() -> int:
    """Validate the current output manifest and print every finding."""
    report = validate_artifact_manifest(PROJECT_ROOT)
    print(f"checked={report.checked} required={report.required} ok={report.ok}")
    for issue in report.issues:
        print(f"[error] {issue}")
    traceability = load_and_validate_traceability(project_root=PROJECT_ROOT, check_artifacts=True)
    if traceability["status"] != "pass":
        print("[error] formalism traceability claim-artifact check failed")
        issues = traceability.get("issues", [])
        if not isinstance(issues, list):
            raise TypeError("traceability issues must be a list")
        for issue in issues:
            print(f"[error] {issue}")
    claims_ok = True
    try:
        validate_claim_ledger(load_claim_ledger(), project_root=PROJECT_ROOT, check_artifacts=True)
    except ValueError as exc:
        claims_ok = False
        print(f"[error] claim ledger validation failed: {exc}")
    bibliography_ok = True
    try:
        check_bibliography_integrity(
            PROJECT_ROOT / "manuscript",
            PROJECT_ROOT / "manuscript" / "references.bib",
        )
    except ValueError as exc:
        bibliography_ok = False
        print(f"[error] bibliography validation failed: {exc}")
    return 0 if report.ok and traceability["status"] == "pass" and claims_ok and bibliography_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
