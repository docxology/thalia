"""Self-contained static HTML dashboard for THALIA results.

Renders a single HTML page (inline CSS, no JS, no third-party dependency) that
embeds the headline metrics, the per-category breakdown, the invariant results,
and the generated figures. The render function is pure (returns a string) so it is
trivially testable; a thin script wires it to live data and figure files.
"""

from __future__ import annotations

import html
from pathlib import Path

from .invariants import InvariantResult, summarize

_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem auto;
       max-width: 960px; color: #0f172a; line-height: 1.5; }
h1 { border-bottom: 3px solid #009E73; padding-bottom: .3rem; }
h2 { color: #0f766e; margin-top: 2rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #cbd5e1; padding: .4rem .6rem; text-align: left; }
th { background: #f1f5f9; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; }
.card { border: 1px solid #cbd5e1; border-radius: 6px; padding: .75rem; background: #f8fafc; }
.card strong { display: block; font-size: .85rem; color: #475569; text-transform: uppercase; }
.card span { display: block; font-size: 1.2rem; font-weight: 700; margin-top: .25rem; }
.pass { color: #15803d; font-weight: 600; }
.fail { color: #b91c1c; font-weight: 600; }
.fig { margin: 1rem 0; }
.fig img { max-width: 100%; border: 1px solid #e2e8f0; border-radius: 6px; }
.muted { color: #64748b; font-size: .9rem; }
"""


def _metric_rows(metrics: dict) -> str:
    rows = [
        ("Examples", metrics.get("n_examples", "—")),
        ("Composite", f"{metrics.get('composite', 0):.3f}"),
        ("Accuracy", f"{metrics.get('accuracy', 0):.3f}"),
        ("Grounding", f"{metrics.get('grounding', 0):.3f}"),
        ("Efficiency", f"{metrics.get('efficiency', 0):.3f}"),
    ]
    comparison = metrics.get("retriever_comparison", {})
    if comparison:
        rows.append(("Best retrieval mode", comparison.get("best_mode", "—")))
    return "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows)


def _category_rows(metrics: dict) -> str:
    cats = metrics.get("category_means", {})
    return "".join(f"<tr><td>{html.escape(cat)}</td><td>{score:.3f}</td></tr>" for cat, score in sorted(cats.items()))


def _invariant_rows(invariants: list[InvariantResult]) -> str:
    out = []
    for inv in invariants:
        cls = "pass" if inv.passed else "fail"
        label = "PASS" if inv.passed else "FAIL"
        out.append(
            f"<tr><td>{html.escape(inv.name)}</td>"
            f"<td class='{cls}'>{label}</td>"
            f"<td class='muted'>{html.escape(inv.detail)}</td></tr>"
        )
    return "".join(out)


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
    return "<table>" + "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows
    ) + "</table>"


def render_dashboard_html(
    metrics: dict,
    invariants: list[InvariantResult],
    figure_paths: list[str],
    *,
    verification: dict | None = None,
    demo: dict | None = None,
) -> str:
    """Render the full dashboard HTML page as a string.

    Args:
        metrics: The dict produced by :func:`src.evaluation.run_full_eval`.
        invariants: Results from :func:`src.invariants.all_invariants`.
        figure_paths: Relative paths/filenames of figure images to embed.
        verification: Optional generated verification-summary payload.
        demo: Optional deterministic demo payload.

    Returns:
        A complete, self-contained HTML document.
    """
    n_pass, n_total = summarize(invariants)
    figures_html = "".join(
        f"<div class='fig'><img src='{html.escape(p)}' alt='{html.escape(Path(p).stem)}'>"
        f"<div class='muted'>{html.escape(Path(p).name)}</div></div>"
        for p in figure_paths
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>THALIA Dashboard</title><style>{_CSS}</style></head>
<body>
<h1>THALIA — Results Dashboard</h1>
<p class="muted">Agentic Typed-pipeline with Lexical And Structured stages.
Deterministic evaluation; numbers are regenerated by the analysis scripts.</p>

<h2>Headline metrics</h2>
<table>{_metric_rows(metrics)}</table>

<h2>Per-category performance</h2>
<table><tr><th>Task category</th><th>Composite</th></tr>{_category_rows(metrics)}</table>

<h2>Invariants ({n_pass}/{n_total} passing)</h2>
<table><tr><th>Invariant</th><th>Status</th><th>Detail</th></tr>{_invariant_rows(invariants)}</table>

<h2>Verification Gates</h2>
{_verification_cards(verification)}

<h2>Deterministic Demo</h2>
{_demo_table(demo)}

<h2>Figures</h2>
{figures_html}
</body></html>
"""


def write_dashboard(
    output_path: str | Path,
    metrics: dict,
    invariants: list[InvariantResult],
    figure_paths: list[str],
    *,
    verification: dict | None = None,
    demo: dict | None = None,
) -> Path:
    """Render and write the dashboard HTML to ``output_path``; return the path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard_html(metrics, invariants, figure_paths, verification=verification, demo=demo))
    return path


__all__ = ["render_dashboard_html", "write_dashboard"]
