#!/usr/bin/env python3
"""Thin orchestrator: preflight check that the THALIA package imports and runs.

Imports the package, runs one harness turn on a demo example, and confirms the
output is well-formed. Exits non-zero on failure so the pipeline halts early.
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.evaluation import build_demo_dataset  # noqa: E402
from src.evaluation.longmemeval import longmemeval_available  # noqa: E402
from src.harness import AutoHarness  # noqa: E402
from src.llm import OllamaLM  # noqa: E402
from src.manuscript_integrity import find_template_root  # noqa: E402
from src.retrieval.learned import embed_model_available, embed_model_metadata  # noqa: E402
from src.signatures import HarnessOutput  # noqa: E402
from src.dspy_runtime import (  # noqa: E402
    DSPY_AVAILABLE,
    ollama_model_available,
    ollama_model_metadata,
)


def main() -> int:
    """Run a single harness turn and validate the output shape.

    Also probes whether a local Ollama server is available (opt-in neural
    backend). The preflight does not require it; the probe surfaces its status
    so downstream scripts know whether neural stages will run.
    """
    example = build_demo_dataset()[0]
    with AutoHarness() as harness:
        out = harness.run(example)
    assert isinstance(out, HarnessOutput), "harness did not return a HarnessOutput"
    assert out.answer, "harness produced an empty answer"
    assert out.memory_written is not None, "full harness did not persist the first turn"
    assert out.memory_written.turn_id == 0, "first turn id should be 0"
    assert out.delivery_mode is not None, "full harness did not produce a delivery mode"

    # Report each external capability separately.  The deterministic core is
    # the only required status; every other line is diagnostic and non-blocking.
    core_status = "ready"
    dspy_status = "available" if DSPY_AVAILABLE and importlib.util.find_spec("dspy") else "unavailable"
    ollama_server = OllamaLM().is_available()
    neural_listed = ollama_model_metadata().get("available", False) if ollama_server else False
    neural_live = ollama_model_available() if ollama_server and neural_listed else False
    embedding_listed = embed_model_metadata().get("available", False) if ollama_server else False
    embedding_live = embed_model_available() if ollama_server and embedding_listed else False
    benchmark = longmemeval_available()
    template = find_template_root((PROJECT_ROOT,))
    template_ready = bool(
        template
        and (template / "infrastructure" / "rendering" / "pdf_renderer.py").is_file()
    )

    print(
        f"[ok] deterministic core: {core_status} category={out.task_category.value} "
        f"delivery={out.delivery_mode.value} cited={len(out.evidence_citations)}"
    )
    print(
        "[status] "
        f"dspy={dspy_status} "
        f"ollama_server={'available' if ollama_server else 'unavailable'} "
        f"neural_model={'available' if neural_live else ('listed' if neural_listed else 'unavailable')} "
        f"embedding_model={'available' if embedding_live else ('listed' if embedding_listed else 'unavailable')} "
        f"longmemeval={'available' if benchmark else 'unavailable'} "
        f"template_render={'available' if template_ready else 'external/empty'} "
        f"template_root={template if template_ready else 'none'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
