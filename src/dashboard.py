"""Offline static HTML asset bundle for THALIA results.

Renders an HTML page (inline CSS, no JS, no third-party dependency) that references
companion figure files. Keep those assets alongside the page for offline viewing.
The render function is pure; a thin script wires it to data and figure files.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from pathlib import Path

from .invariants import InvariantResult, summarize
from .figures.manifest import FIGURE_CAPTIONS
from .evaluation.backend_benchmark import validate_backend_benchmark
from .evaluation.benchmark_analysis import summarize_prompt_exposure, summarize_seed_pairs

_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem auto;
       max-width: 960px; padding: 0 1rem; color: #0f172a; line-height: 1.5; }
h1 { border-bottom: 3px solid #009E73; padding-bottom: .3rem; }
h2 { color: #0f766e; margin-top: 2rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #cbd5e1; padding: .4rem .6rem; text-align: left; }
th { background: #f1f5f9; }
caption { text-align: left; font-weight: 600; margin-bottom: .4rem; }
.table-scroll { overflow-x: auto; max-width: 100%; }
.table-scroll table { min-width: 52rem; }
.table-scroll th, .table-scroll td { overflow-wrap: normal; }
.table-scroll:focus { outline: 2px solid #0f766e; outline-offset: 2px; }
td, th, pre { overflow-wrap: anywhere; }
pre { white-space: pre-wrap; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; }
.card { border: 1px solid #cbd5e1; border-radius: 6px; padding: .75rem; background: #f8fafc; }
.card strong { display: block; font-size: .85rem; color: #475569; text-transform: uppercase; }
.card span { display: block; font-size: 1.2rem; font-weight: 700; margin-top: .25rem; }
.pass { color: #15803d; font-weight: 600; }
.fail { color: #b91c1c; font-weight: 600; }
.status-banner { border: 1px solid #f59e0b; border-left: 5px solid #f59e0b; padding: .75rem 1rem; margin: 1rem 0; background: #fffbeb; }
.status-banner strong { display: block; margin-bottom: .2rem; }
.fig { margin: 1rem 0; }
.fig img { max-width: 100%; border: 1px solid #e2e8f0; border-radius: 6px; }
.muted { color: #64748b; font-size: .9rem; }
"""


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _metric_rows(metrics: dict) -> str:
    rows = [
        ("Examples", metrics.get("n_examples") if metrics.get("n_examples") is not None else "—"),
        ("Composite", _number(metrics.get("composite"))),
        ("Answer token-F1", _number(metrics.get("accuracy"))),
        ("Citation-support proxy", _number(metrics.get("grounding"))),
        ("Efficiency", _number(metrics.get("efficiency"))),
    ]
    comparison = metrics.get("retriever_comparison", {})
    if comparison:
        rows.append(("Best retrieval mode", comparison.get("best_mode", "—")))
    return "".join(f"<tr><th scope='row'>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows)


def _category_rows(metrics: dict) -> str:
    cats = metrics.get("category_means", {})
    return "".join(f"<tr><th scope='row'>{html.escape(cat)}</th><td>{score:.3f}</td></tr>" for cat, score in sorted(cats.items()))


def _invariant_rows(invariants: list[InvariantResult]) -> str:
    out = []
    for inv in invariants:
        cls = "pass" if inv.passed else "fail"
        label = "PASS" if inv.passed else "FAIL"
        out.append(
            f"<tr><th scope='row'>{html.escape(inv.name)}</th>"
            f"<td class='{cls}'>{label}</td>"
            f"<td class='muted'>{html.escape(inv.detail)}</td></tr>"
        )
    return "".join(out)


def _statistical_rows(metrics: dict) -> str:
    """Render sample-size accounting and uncertainty rows when generated."""
    audit = metrics.get("statistical_scaling")
    if not audit:
        return "<p class='muted'>Run scripts/run_harness_eval.py to generate the statistical audit.</p>"
    accounting = audit.get("accounting", {})
    contract = audit.get("analysis_contract", {})
    unique_evaluated = accounting.get("n_unique_examples", accounting.get("n_evaluated", "—"))
    method_evaluations = accounting.get("n_method_evaluations", accounting.get("n_evaluated", "—"))
    rows = [
        ("Unique examples requested", accounting.get("n_requested", "—")),
        ("Unique examples evaluated", unique_evaluated),
        ("Method evaluations", method_evaluations),
        ("Failures", accounting.get("n_failed", "—")),
        ("Fixed seeds", ", ".join(str(seed) for seed in audit.get("seed_values", []))),
        ("Strata", ", ".join(str(value) for value in audit.get("accounting", {}).get("strata", [])) or "—"),
        ("Dataset fingerprint", audit.get("dataset_fingerprint", "—")),
        ("Source fingerprint", audit.get("source_fingerprint", "—")),
        ("Comparison family", f"{audit.get('comparison_family', {}).get('name', '—')} (m={audit.get('comparison_family', {}).get('size', '—')})"),
        ("Estimand", contract.get("primary_estimand", accounting.get("estimand", "—"))),
        ("Observation unit", contract.get("observation_unit", accounting.get("unit", "—"))),
        ("Interval interpretation", contract.get("interval_interpretation", "—")),
        ("Cluster warning", contract.get("small_cluster_warning", accounting.get("small_cluster_warning", "—"))),
        ("Failure accounting", accounting.get("failure_by_method", {})),
    ]
    for row in audit.get("rows", []):
        hybrid = row.get("methods", {}).get("hybrid", {})
        rows.append(
            (
                f"Hybrid composite, n={row.get('n_total', '—')}",
                f"{_number(hybrid.get('estimate'))} "
                f"[{_number(hybrid.get('low'))}, {_number(hybrid.get('high'))}]",
            )
        )
    return "<table><caption>Sample accounting and descriptive uncertainty</caption>" + "".join(
        f"<tr><th scope='row'>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in rows
    ) + "</table>"


def _provenance_table(metrics: dict) -> str:
    provenance = metrics.get("provenance") or {}
    if not provenance:
        return "<p class='muted'>No source provenance supplied.</p>"
    labels = {
        "neural_model": "Neural model",
        "neural_digest": "Neural digest",
        "embedding_model": "Embedding model",
        "embedding_digest": "Embedding digest",
        "benchmark_sha256": "Benchmark SHA-256",
        "benchmark_bytes": "Benchmark bytes",
        "generation_options": "Generation options",
        "embedding_prefixes": "Embedding prefixes",
    }
    return "<table><caption>Source provenance</caption>" + "".join(
        f"<tr><th scope='row'>{html.escape(labels.get(key, str(key)))}</th>"
        f"<td>{html.escape(str(value)) if value is not None else '—'}</td></tr>"
        for key, value in provenance.items()
    ) + "</table>"


def _backend_benchmark_table(payload: dict | None) -> str:
    if payload is None:
        return (
            "<p class='status-banner'>Backend benchmark: MISSING. "
            "No method benchmark evidence was supplied; legacy local and cloud "
            "measurements are not ranked as comparable results. "
            "Per-seed paired audit: not recorded; no benchmark report supplied.</p>"
        )

    def table(
        caption: str, headings: tuple[str, ...], rows: list[list[object]], *,
        table_id: str | None = None,
    ) -> str:
        label_id = f"{table_id}-caption" if table_id else "backend-benchmark-heading"
        table_attribute = f" id='{html.escape(table_id)}'" if table_id else ""
        caption_attribute = f" id='{html.escape(label_id)}'" if table_id else ""
        return (
            f"<div class='table-scroll' role='region' aria-labelledby='{html.escape(label_id)}' "
            "aria-describedby='backend-benchmark-description' tabindex='0'>"
            f"<table{table_attribute}><caption{caption_attribute}>{html.escape(caption)}</caption><thead><tr>"
            + "".join(f"<th scope='col'>{html.escape(h)}</th>" for h in headings)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr><th scope='row'>" + html.escape(str(row[0])) + "</th>"
                + "".join(f"<td>{html.escape(str(value))}</td>" for value in row[1:])
                + "</tr>" for row in rows
            )
            + "</tbody></table></div>"
        )

    backends = {backend["name"]: backend for backend in payload["backends"]}

    def observation(summary: dict) -> list[object]:
        backend = backends[summary["backend"]]
        return [
            summary["backend"], backend["provider"], backend["model"], summary["method"],
            summary["status"], summary["n_requested"], summary["n_completed"], summary["n_failed"],
            _number(summary["mean_token_f1"]), _number(summary["mean_latency_seconds"]),
            _number(summary["p50_latency_seconds"]), _number(summary["p95_latency_seconds"]),
            _number(summary["mean_prompt_characters"]),
        ]

    headings = (
        "Backend", "Provider", "Model", "Method", "Status", "Requested", "Completed", "Failed",
        "Mean token-F1", "Mean latency (s)", "p50 latency (s)", "p95 latency (s)",
        "Mean prompt characters",
    )
    observations = table(
        "Backend × method observations", headings,
        [observation(summary) for summary in payload["summaries"]],
    )
    reference = payload["analysis"]["reference_method"]
    exposure = summarize_prompt_exposure(
        payload["rows"], methods=[method["name"] for method in payload["methods"]],
        example_ids=[example["example_id"] for example in payload["examples"]],
        reference_method=reference,
    )
    exposure_table = table(
        "Recorded prompt exposure by method",
        ("Method", "Recorded / planned cases", "Distinct prompts",
         f"Different / paired cases vs {reference}", "Realized prompt group"),
        [
            [
                row["method"],
                f"{row['n_observed_cases']} / {row['n_requested_cases']} "
                f"({row['n_requested_cases'] - row['n_observed_cases']} unobserved)",
                row["n_unique_prompts"],
                f"{row['n_different_from_reference']} / {row['n_compared_to_reference']}"
                if row["n_compared_to_reference"] else (
                    f"— / {row['n_compared_to_reference']} (reference absent)"
                    if row["n_different_from_reference"] is None
                    else f"— / {row['n_compared_to_reference']} (no recorded prompt pairs)"
                ),
                "—" if row["prompt_group"] is None else f"P{row['prompt_group']}",
            ]
            for row in exposure
        ],
        table_id="backend-exposure-table",
    )
    groups = "".join(
        table(
            f"Backend × method observations by {group}", (group.capitalize(),) + headings,
            [[summary[group]] + observation(summary) for summary in payload["groups"][group]],
        )
        for group in ("category", "stratum")
    )
    contrasts = []
    for comparison in payload["comparisons"]:
        interval = comparison["interval"]
        caveat = (
            "Incomplete: paired estimate suppressed" if comparison["status"] != "complete"
            else "Single-seed: interval unavailable" if comparison["n_seed_clusters"] < 2
            else "Small-cluster warning" if interval["small_cluster_warning"]
            else "Descriptive seed-cluster interval"
        )
        contrasts.append([
            comparison["backend"], comparison["method"], comparison["reference_method"],
            comparison["status"], comparison["n_requested_pairs"], comparison["n_complete_pairs"],
            comparison["n_seed_clusters"], comparison["wins"], comparison["ties"], comparison["losses"],
            _number(comparison["mean_delta"]),
            "—" if interval is None else f"[{_number(interval['low'])}, {_number(interval['high'])}]",
            caveat,
        ])
    comparisons = table(
        "Within-model paired method contrasts",
        ("Backend", "Method", "Reference", "Status", "Requested pairs", "Complete pairs",
         "Seed clusters", "Wins", "Ties", "Losses", "Seed-mean token-F1 delta",
         "Descriptive interval", "Caveat"),
        contrasts,
    ) if contrasts else (
        "<p>Within-model contrasts: reference method absent or no non-reference method selected; "
        "not recorded. No paired estimate is inferred.</p>"
    )
    seed_pairs = summarize_seed_pairs(
        payload["rows"], backends=list(backends),
        methods=[method["name"] for method in payload["methods"]],
        examples=payload["examples"], reference_method=reference,
    )
    seed_tables = "".join(
        table(
            f"Per-seed paired audit — {backend_name}; model: {backend['model']}; reference: {reference}",
            ("Method", "Seed", "Pairs requested / complete", "W / T / L", "Mean delta", "Status"),
            [
                [
                    row["method"], row["seed"],
                    f"{row['n_requested_pairs']} / {row['n_complete_pairs']}",
                    f"{row['wins']} / {row['ties']} / {row['losses']}",
                    _number(row["mean_delta"]),
                    row["status"] if row["status"] == "complete"
                    else "incomplete: seed mean suppressed",
                ]
                for row in seed_pairs if row["backend"] == backend_name
            ],
            table_id=f"backend-seed-pairs-{index}",
        )
        for index, (backend_name, backend) in enumerate(backends.items())
    ) if seed_pairs else (
        "<p>Per-seed paired audit: reference method absent or no non-reference method selected; "
        "not recorded. No paired estimate is inferred.</p>"
    )
    metadata = {
        key: payload[key] for key in (
            "cohort", "dataset_fingerprint", "report_fingerprint", "n_examples", "methods",
            "backends", "analysis", "runtime_provenance", "producer_provenance", "execution_order",
        )
    }
    return (
        f"<p class='status-banner'>Backend benchmark: {html.escape(payload['status'].upper())}.</p>"
        "<p id='backend-benchmark-description'>Finite seeded synthetic backend × method observations; "
        "no mixed-method backend mean. Incomplete cells summarize successes only and retain all counts. "
        f"Unique seeded example IDs: {payload['n_examples']}; IDs are not unique submitted inputs. "
        "Recorded prompt cases collapse backends for each method and example ID, including failed "
        "completions with a captured prompt; unobserved cases are planned minus recorded. "
        "Completion failures remain visible in the observation counts. Repeated inputs are not "
        "independent new content. A realized prompt group means exact per-example submitted-text "
        "equivalence across this cohort's complete ordered case vector, not equal code, compute, "
        "latency, quality, or independent method-quality evidence. Missing prompts leave groups "
        "unavailable. Missing reference or no recorded prompt pairs means no prompt-difference "
        "comparison, not a zero quality effect. "
        "Within-model contrasts pair the same examples, then average per-seed mean paired token-F1 deltas "
        "with equal seed weight; wins/ties/losses count raw complete pairs. Any incomplete planned pair "
        "suppresses the estimate and interval. Pooled cell means weight examples, not seeds; their "
        "difference is not the equally weighted seed-mean contrast when seed sizes differ. Per-seed means "
        "are suppressed for incomplete seeds; complete seeds do not rescue an incomplete whole-report "
        "contrast. Single-seed contrasts have no interval; small seed-cluster "
        "intervals are descriptive, not population-power or significance claims. "
        "Prompt characters are submitted text length, not billed tokens or retained provider context. "
        "Latency includes method, transport, serving, and cleanup; it is not throughput or cost. "
        "This is not adjudicated answer quality or a production certificate. "
        "Source checksums bind recorded bytes, not authenticity or provider-binary attestation.</p>"
        + exposure_table + observations + comparisons + seed_tables
        + "<details><summary>Category and stratum observations</summary>"
        + groups + "</details><details><summary>Backend benchmark provenance</summary><pre>"
        + html.escape(json.dumps(metadata, indent=2, sort_keys=True))
        + "</pre></details>"
    )


def _verification_cards(verification: dict | None) -> str:
    if not verification:
        return "<p class='muted'>No verification summary generated yet.</p>"
    cards = [
        ("Status", verification.get("status", "—")),
        ("Coverage gate", f"{verification.get('coverage_gate', '—')}%"),
        ("Tests", verification.get("latest_observed_tests") or "run command below"),
        ("Coverage", verification.get("latest_observed_coverage") or "run command below"),
    ]
    return "<div class='cards'>" + "".join(
        f"<div class='card'><strong>{html.escape(str(k))}</strong><span>{html.escape(str(v))}</span></div>"
        for k, v in cards
    ) + "</div>"


def _demo_table(demo: dict | None) -> str:
    if not demo:
        return "<p class='muted'>Run scripts/run_demo.py to generate the deterministic transcript artifact.</p>"
    session = demo.get("session", {})
    compiler = demo.get("compiler", {})
    rows = [
        ("First answer", session.get("first_answer", "—")),
        ("Reopened answer", session.get("reopened_answer", "—")),
        ("Reopened citations", session.get("reopened_citations", "—")),
        ("MIPRO-style best", compiler.get("mipro_style", {}).get("best_score", "—")),
        ("GEPA-style best", compiler.get("gepa_style", {}).get("best_score", "—")),
    ]
    return "<table><caption>Deterministic session and compiler observations</caption>" + "".join(
        f"<tr><th scope='row'>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows
    ) + "</table>"


def _evidence_status(label: str, payload: dict | None, accepted_status: str) -> str:
    if not payload:
        return (
            f"<div class='status-banner'><strong>{html.escape(label)}: NOT ACCEPTED</strong>"
            "No committed certificate is present; operational and model-quality evidence remain separate.</div>"
        )
    status = str(payload.get("status", "unknown"))
    cls = "pass" if status == accepted_status else "fail"
    return (
        f"<div class='status-banner'><strong>{html.escape(label)}: "
        f"<span class='{cls}'>{html.escape(status.upper())}</span></strong>"
        "This status is evidence-tier specific and does not imply the other gate.</div>"
    )


def render_dashboard_html(
    metrics: dict,
    invariants: list[InvariantResult],
    figure_paths: list[str],
    *,
    verification: dict | None = None,
    demo: dict | None = None,
    quality_status: dict | None = None,
    production_status: dict | None = None,
    backend_benchmark: dict | None = None,
    figure_descriptions: Mapping[str, str] | None = None,
) -> str:
    """Render the full dashboard HTML page as a string.

    Args:
        metrics: The dict produced by :func:`src.evaluation.run_full_eval`.
        invariants: Results from :func:`src.invariants.all_invariants`.
        figure_paths: Relative paths/filenames of figure images to embed.
        verification: Optional generated verification-summary payload.
        demo: Optional deterministic demo payload.
        backend_benchmark: Optional validated schema2 backend × method evidence.
        figure_descriptions: Optional image-stem to authored alt text mapping.
            Blank or absent descriptions fall back to source captions; visible
            captions remain source-authored. No figure files are read here.

    Returns:
        An offline HTML document referencing the supplied companion figure assets.
    """
    if backend_benchmark is not None:
        validate_backend_benchmark(backend_benchmark)
    n_pass, n_total = summarize(invariants)
    descriptions = figure_descriptions or {}

    def figure_alt(path: str) -> str:
        stem = Path(path).stem
        description = descriptions.get(stem)
        return description if description and description.strip() else FIGURE_CAPTIONS.get(stem, stem)

    figures_html = "".join(
        f"<figure class='fig'><img src='{html.escape(p)}' alt='{html.escape(figure_alt(p))}'>"
        f"<figcaption class='muted'><strong>{html.escape(Path(p).name)}</strong> — "
        f"{html.escape(FIGURE_CAPTIONS.get(Path(p).stem, 'Generated THALIA figure.'))}</figcaption></figure>"
        for p in figure_paths
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>THALIA Dashboard</title><style>{_CSS}</style></head>
<body><main>
<h1>THALIA — Results Dashboard</h1>
<p class="muted">Typed Harness with Analytical Lexical-Integrated Architecture.
Offline asset bundle: keep the companion figure files with this page.
Deterministic headline evaluation and optional observational backend evidence are separate.</p>

<h2>Headline metrics</h2>
<table><caption>Deterministic headline metrics (— means missing)</caption>{_metric_rows(metrics)}</table>

{_evidence_status("Model quality", quality_status, "passed")}
{_evidence_status("Production readiness", production_status, "ready")}

<h2 id="backend-benchmark-heading">Backend × method benchmark</h2>
{_backend_benchmark_table(backend_benchmark)}

<h2>Per-category performance</h2>
<table><caption>Composite by task category</caption><thead><tr><th scope="col">Task category</th><th scope="col">Composite</th></tr></thead><tbody>{_category_rows(metrics)}</tbody></table>

<h2>Invariants ({n_pass}/{n_total} passing)</h2>
<table><caption>Executable invariant results</caption><thead><tr><th scope="col">Invariant</th><th scope="col">Status</th><th scope="col">Detail</th></tr></thead><tbody>{_invariant_rows(invariants)}</tbody></table>

<h2>Statistical sample audit</h2>
{_statistical_rows(metrics)}

<h2>Provenance</h2>
{_provenance_table(metrics)}

<h2>Verification Gates</h2>
{_verification_cards(verification)}

<h2>Deterministic Demo</h2>
{_demo_table(demo)}

<h2>Figures</h2>
{figures_html}
</main></body></html>
"""


def write_dashboard(
    output_path: str | Path,
    metrics: dict,
    invariants: list[InvariantResult],
    figure_paths: list[str],
    *,
    verification: dict | None = None,
    demo: dict | None = None,
    quality_status: dict | None = None,
    production_status: dict | None = None,
    backend_benchmark: dict | None = None,
    figure_descriptions: Mapping[str, str] | None = None,
) -> Path:
    """Render and write the dashboard HTML to ``output_path``; return the path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = render_dashboard_html(
        metrics,
        invariants,
        figure_paths,
        verification=verification,
        demo=demo,
        quality_status=quality_status,
        production_status=production_status,
        backend_benchmark=backend_benchmark,
        figure_descriptions=figure_descriptions,
    )
    path.write_text(document, encoding="utf-8")
    return path


__all__ = ["render_dashboard_html", "write_dashboard"]
