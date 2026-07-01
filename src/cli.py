"""Command-line interface for running queries against the THALIA harness.

Precedence for configuration (lowest to highest): built-in defaults, a ``--config``
YAML file, ``THALIA_*`` environment variables, then explicit CLI flags. The default
language model is the deterministic extractive responder; pass a real model
programmatically via :func:`run_query`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import HarnessConfig, apply_env_overrides, default_config, load_config
from .harness import AutoHarness
from .module import LMClient
from .signatures import HarnessOutput
from . import __version__


def output_to_dict(out: HarnessOutput) -> dict:
    """Serialise a :class:`HarnessOutput` to a JSON-friendly dict.

    Delegates to :meth:`HarnessOutput.to_dict` so the serialisation lives on the
    dataclass itself — the CLI is a thin caller, not a second source of truth.
    """
    return out.to_dict()


def run_query(
    query: str,
    session_history: str = "",
    config: HarnessConfig | None = None,
    lm: LMClient | None = None,
) -> dict:
    """Run one harness turn and return a serialisable result dict.

    Args:
        query: The question to answer.
        session_history: The transcript to inspect (may be empty).
        config: Harness configuration (defaults to the harness default).
        lm: Language model (defaults to the deterministic extractive LM).

    Returns:
        The dict produced by :func:`output_to_dict`.
    """
    config = config or default_config()
    out = AutoHarness(config=config, lm=lm).forward(query, session_history)
    return output_to_dict(out)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the THALIA query CLI."""
    parser = argparse.ArgumentParser(prog="thalia", description="Run a query against the THALIA auto-harness.")
    parser.add_argument("--version", "-V", action="version", version=f"THALIA v{__version__}", help="Show version and exit.")
    parser.add_argument("--query", "-q", required=True, help="The question to answer.")
    parser.add_argument("--session-history", default="", help="Inline transcript to inspect.")
    parser.add_argument("--session-file", default=None, help="Path to a transcript file to inspect.")
    parser.add_argument("--config", default=None, help="Path to a harness YAML config.")
    parser.add_argument("--top-k", type=int, default=None, help="Override retriever top_k.")
    parser.add_argument("--max-windows", type=int, default=None, help="Override inspector max_windows.")
    parser.add_argument("--max-evidence", type=int, default=None, help="Override reasoner max_evidence.")
    parser.add_argument("--rrf-k", type=int, default=None, help="Override RRF k.")
    parser.add_argument("--context-budget", type=int, default=None, help="Override context_budget_tokens.")
    parser.add_argument("--rerank", choices=("rrf", "mmr"), default=None, help="Override re-ranking strategy.")
    parser.add_argument("--mmr-lambda", type=float, default=None, help="Override MMR relevance/diversity tradeoff.")
    parser.add_argument(
        "--verify",
        action="store_const",
        const=True,
        default=None,
        help="Enable the Reasoner grounding-verification pass.",
    )
    parser.add_argument(
        "--query-expansion",
        action="store_const",
        const=True,
        default=None,
        help="Enable pseudo-relevance-feedback query expansion.",
    )
    parser.add_argument("--recency-weight", type=float, default=None, help="Recency bonus in [0,1].")
    parser.add_argument(
        "--recall-memory",
        action="store_const",
        const=True,
        default=None,
        help="Consult the episodic store + MEMORY.md for evidence.",
    )
    parser.add_argument(
        "--adaptive-windows",
        action="store_const",
        const=True,
        default=None,
        help="Scale Inspector windows by context length for long contexts.",
    )
    parser.add_argument(
        "--adaptive-window-ratio",
        type=int,
        default=None,
        help="When adaptive: keep roughly one Inspector window per N session lines.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser


def resolve_config(args: argparse.Namespace) -> HarnessConfig:
    """Resolve the effective config: file < env < explicit CLI flags."""
    base = load_config(args.config, apply_env=False) if args.config else default_config()
    base = apply_env_overrides(base)
    changes: dict = {}
    for flag, field in (
        ("top_k", "top_k"),
        ("max_windows", "max_windows"),
        ("max_evidence", "max_evidence"),
        ("rrf_k", "rrf_k"),
        ("context_budget", "context_budget_tokens"),
        ("rerank", "rerank"),
        ("mmr_lambda", "mmr_lambda"),
        ("verify", "verify"),
        ("query_expansion", "query_expansion"),
        ("recency_weight", "recency_weight"),
        ("recall_memory", "recall_memory"),
        ("adaptive_windows", "adaptive_windows"),
        ("adaptive_window_ratio", "adaptive_window_ratio"),
    ):
        value = getattr(args, flag)
        if value is not None:
            changes[field] = value
    return base.with_(**changes) if changes else base


# The documented demo (also exercised by the smoke test): a one-line session
# whose gold answer is a single discriminative fact.
_DEMO_QUERY = "What is the wifi password?"
_DEMO_HISTORY = "User: my wifi password is bluefish42"


def run_demo() -> int:
    """Run the documented demo query deterministically and print its JSON result.

    Invoked when the CLI receives no arguments — the working-render pipeline runs
    every ``scripts/*.py`` bare, so a required ``--query`` would make this CLI fail
    Stage 4 (Analysis) and block the PDF render. Running a fixed demo instead makes
    ``run_query.py`` double as a self-demonstrating, deterministic analysis artifact.
    """
    result = run_query(_DEMO_QUERY, session_history=_DEMO_HISTORY)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code.

    With no arguments (batch/analysis context) this runs :func:`run_demo`; with
    arguments it behaves exactly as a normal CLI (including ``--query`` required).
    """
    raw = sys.argv[1:] if argv is None else argv
    if not raw:
        return run_demo()
    args = build_parser().parse_args(raw)

    history = args.session_history
    if args.session_file:
        history = Path(args.session_file).read_text()

    config = resolve_config(args)
    result = run_query(args.query, session_history=history, config=config)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"answer:    {result['answer']}")
        print(f"category:  {result['task_category']}")
        print(f"delivery:  {result['delivery_mode']}")
        indices = [c["source_index"] for c in result["citations"]]
        cited = f"{len(indices)} (source indices: {', '.join(map(str, indices))})" if indices else "none"
        print(f"citations: {cited}")
        # Surface the number of evidence windows the pipeline narrowed to.
        n_ranked = len(result.get("ranked_evidence", []))
        print(f"evidence:  {n_ranked} ranked window(s)")
    return 0


__all__ = ["run_query", "run_demo", "output_to_dict", "build_parser", "resolve_config", "main"]
