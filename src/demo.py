"""Canonical deterministic THALIA demo artifacts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .compiler.gepa import GEPAOptimizer
from .compiler.mipro import MIPROCompiler
from .config import default_config
from .evaluation import build_demo_dataset
from .harness import build_run_fn
from .provenance import write_artifact_manifest, write_verification_summary
from .session import Session


def build_demo_artifacts(output_dir: str | Path) -> dict[str, Path]:
    """Build deterministic demo JSON and provenance summaries.

    The session portion uses real file-backed SQLite and MEMORY.md paths inside a
    temporary directory, then serialises only the resulting transcript/answers.
    This demonstrates restart-safe recall without committing local state files.
    """
    root = Path(output_dir)
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="thalia-demo-") as tmp:
        db = Path(tmp) / "episodes.db"
        memory = Path(tmp) / "MEMORY.md"
        with Session(config=default_config().with_(recall_memory=True), db_path=str(db), memory_path=memory) as session:
            first = session.ask("My wifi password is bluefish42")
            first_turns = session.turn_count

        with Session(config=default_config().with_(recall_memory=True), db_path=str(db), memory_path=memory) as reopened:
            second = reopened.ask("What is the wifi password?")
            reopened_turns = reopened.turn_count

    dataset = build_demo_dataset()
    mipro = MIPROCompiler(auto="light").compile(lambda cfg: build_run_fn(cfg), dataset)
    gepa = GEPAOptimizer().evolve(lambda cfg: build_run_fn(cfg), dataset, iterations=2)

    payload = {
        "claim_boundary": "Deterministic demo transcript; not a benchmark result.",
        "session": {
            "first_answer": first.answer,
            "first_turn_count": first_turns,
            "reopened_answer": second.answer,
            "reopened_turn_count": reopened_turns,
            "reopened_citations": [c.source_index for c in second.evidence_citations],
        },
        "compiler": {
            "mipro_style": {
                "best_score": mipro.best_score,
                "n_candidates": mipro.n_candidates,
                "selection_rationale": "bounded structural HarnessConfig search; ties keep first winner",
            },
            "gepa_style": {
                "best_score": gepa.best_score,
                "n_candidates": gepa.n_candidates,
                "selection_rationale": "bounded metric-component reflection over HarnessConfig",
            },
        },
    }

    demo_path = data_dir / "demo_result.json"
    demo_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Materialize the current artifact set before refreshing the summary so its
    # artifact-pipeline observation includes this newly written demo result.
    write_artifact_manifest(root.parent)
    verification_path = write_verification_summary(root / "reports" / "verification_summary.json")
    manifest_path = write_artifact_manifest(root.parent)
    return {
        "demo": demo_path,
        "verification_summary": verification_path,
        "artifact_manifest": manifest_path,
    }


__all__ = ["build_demo_artifacts"]
