#!/usr/bin/env python3
"""Thin orchestrator: run the full THALIA evaluation and serialise results.

All computation lives in ``src/evaluation``; this script only handles I/O.
Writes ``output/data/eval_results.json`` and prints the path to stdout for
manifest collection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.evaluation import (  # noqa: E402
    DEFAULT_SAMPLE_SIZE_SEEDS,
    DEFAULT_SAMPLE_SIZE_VALUES,
    noise_scaling_experiment,
    run_full_eval,
    sample_size_scaling_eval,
)
from src.evaluation import write_accounting_report, write_ledger_and_events  # noqa: E402


def main(
    output_root: str | Path | None = None,
    *,
    per_category_values: tuple[int, ...] | None = None,
    seeds: tuple[int, ...] | None = None,
    n_boot: int = 2000,
) -> Path:
    """Run the evaluation bundle and write it to output/data/eval_results.json."""
    root = Path(output_root) if output_root is not None else PROJECT_ROOT / "output"
    output_dir = root / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = run_full_eval()
    results["noise_scaling"] = noise_scaling_experiment()
    statistical = sample_size_scaling_eval(
        per_category_values=per_category_values if per_category_values is not None else DEFAULT_SAMPLE_SIZE_VALUES,
        seeds=seeds if seeds is not None else DEFAULT_SAMPLE_SIZE_SEEDS,
        n_boot=n_boot,
        include_ledger=True,
    )
    ledger = statistical.pop("ledger", [])
    events = statistical.pop("events", [])
    results["statistical_scaling"] = statistical

    output_path = output_dir / "eval_results.json"
    output_path.write_text(json.dumps(results, indent=2, sort_keys=True))
    write_accounting_report(statistical["accounting"], root / "reports" / "evaluation_accounting.json")
    ledger_path, events_path = write_ledger_and_events(
        ledger,
        events,
        root / "reports" / "evaluation_ledger.jsonl",
        root / "reports" / "evaluation_events.jsonl",
    )
    print(str(root / "reports" / "evaluation_accounting.json"))
    print(str(events_path))
    print(str(ledger_path))
    print(str(output_path))
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="artifact root (default: output/)",
    )
    parser.add_argument(
        "--per-category-values",
        type=int,
        nargs="+",
        default=None,
        metavar="N",
        help="audited per-category sample sizes; defaults to the quick four-size smoke grid",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        metavar="SEED",
        help="independent dataset seeds; defaults to the quick five-seed smoke grid",
    )
    parser.add_argument(
        "--n-boot",
        type=int,
        default=2000,
        help="cluster/bootstrap resamples per summary (default: 2000)",
    )
    args = parser.parse_args()
    main(
        args.output_root,
        per_category_values=tuple(args.per_category_values) if args.per_category_values is not None else None,
        seeds=tuple(args.seeds) if args.seeds is not None else None,
        n_boot=args.n_boot,
    )
