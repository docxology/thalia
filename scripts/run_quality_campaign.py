#!/usr/bin/env python3
"""Run the target-model campaign and exploratory local-LLM diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.dspy_runtime import ollama_model_metadata  # noqa: E402
from src.evaluation.llm_judge import JudgeModelSpec, bind_judge_models, run_llm_judging  # noqa: E402
from src.evaluation.quality import QualityObservation, QualityProtocol, default_quality_conditions  # noqa: E402
from src.evaluation.quality_runner import (  # noqa: E402
    DEFAULT_BENCHMARK,
    DEFAULT_QUALITY_ROOT,
    load_benchmark,
    load_jsonl,
    run_quality_campaign,
)


def _normalize_digest(value: object, name: str) -> str:
    text = str(value or "")
    if text.startswith("sha256:"):
        text = text[7:]
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    if text:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    raise ValueError(f"missing digest for {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("pilot", "confirmatory"), required=True)
    parser.add_argument("--protocol", type=Path, default=None, help="frozen protocol JSON; required for confirmation")
    parser.add_argument("--protocol-id", default="thalia-quality-llmjudge")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_QUALITY_ROOT)
    parser.add_argument("--pilot-per-stratum", type=int, default=10)
    parser.add_argument("--models", default="gemma3:4b,hermes3:latest")
    parser.add_argument("--judge-models", default="qwen2.5:3b,llama3.2:3b")
    parser.add_argument("--adjudicator-model", default="phi3:mini")
    args = parser.parse_args(argv)

    if not args.benchmark.is_file():
        raise FileNotFoundError(f"benchmark not found: {args.benchmark}")
    examples = load_benchmark(args.benchmark)
    models = tuple(model.strip() for model in args.models.split(",") if model.strip())
    judge_models = tuple(model.strip() for model in args.judge_models.split(",") if model.strip())
    if len(judge_models) != 2 or len(set(judge_models)) != 2:
        raise ValueError("--judge-models must contain exactly two distinct models")
    adjudicator_model = args.adjudicator_model.strip()
    if not adjudicator_model:
        raise ValueError("--adjudicator-model must be non-empty")

    judge_metadata = {model: ollama_model_metadata(model) for model in (*judge_models, adjudicator_model)}
    unavailable_judges = [model for model, payload in judge_metadata.items() if not payload.get("available")]
    if unavailable_judges:
        raise RuntimeError(f"LLM judge models unavailable: {', '.join(sorted(unavailable_judges))}")
    judge_specs = tuple(
        JudgeModelSpec(
            judge_id=f"judge-{index + 1}",
            model=model,
            digest=_normalize_digest(judge_metadata[model].get("digest"), model),
        )
        for index, model in enumerate(judge_models)
    )
    adjudicator_spec = JudgeModelSpec(
        judge_id="adjudicator",
        model=adjudicator_model,
        digest=_normalize_digest(judge_metadata[adjudicator_model].get("digest"), adjudicator_model),
        role="adjudicator",
    )

    if args.protocol is not None:
        protocol = QualityProtocol.from_dict(json.loads(args.protocol.read_text(encoding="utf-8")))
    else:
        if args.phase != "pilot":
            raise ValueError("--protocol is required for confirmatory runs")
        protocol = QualityProtocol.from_examples(
            protocol_id=args.protocol_id,
            benchmark_path=args.benchmark,
            examples=examples,
            conditions=default_quality_conditions(models),
            pilot_per_stratum=args.pilot_per_stratum,
        )
        protocol = bind_judge_models(protocol, judge_specs, adjudicator_spec)

    if protocol.judge_models:
        expected_judges = {judge_id: (model, digest) for judge_id, model, digest in protocol.judge_models}
        actual_judges = {judge.judge_id: (judge.model, judge.digest) for judge in judge_specs}
        if expected_judges != actual_judges:
            raise ValueError("requested judge models do not match the protocol binding")
        if protocol.adjudicator_model != (adjudicator_spec.model, adjudicator_spec.digest):
            raise ValueError("requested adjudicator model does not match the protocol binding")

    target_metadata = {
        model: ollama_model_metadata(model)
        for model in {condition.model for condition in protocol.conditions}
    }
    unavailable_targets = [model for model, payload in target_metadata.items() if not payload.get("available")]
    if unavailable_targets:
        raise RuntimeError(f"target models unavailable: {', '.join(sorted(unavailable_targets))}")

    summary = run_quality_campaign(
        protocol,
        examples,
        phase=args.phase,
        output_root=args.output_root,
        model_metadata=target_metadata,
    )
    observations = load_jsonl(summary.observations_path, QualityObservation.from_dict)
    judge_summary = run_llm_judging(
        protocol,
        observations,
        examples,
        phase=args.phase,
        output_root=args.output_root,
        judge_specs=judge_specs,
        adjudicator=adjudicator_spec,
        project_root=PROJECT_ROOT,
    )
    print(json.dumps({"target_run": summary.to_dict(), "judge_run": judge_summary.to_dict()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
