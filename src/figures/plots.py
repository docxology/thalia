"""Data-driven matplotlib figures for the THALIA manuscript."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from matplotlib.lines import Line2D

from ..config import DEFAULT_CONFIDENCE_LEVEL, HarnessConfig
from ..compiler.metrics import ACCURACY_WEIGHT, EFFICIENCY_WEIGHT, GROUNDING_WEIGHT
from ..evaluation import (
    RetrieverComparison,
    consolidation_simulation,
    evidence_funnel,
    method_ablation,
    mmr_lambda_sweep,
    noise_scaling_experiment,
    rrf_weight_sweep,
)
from ..evaluation.schemas import (
    BottleneckPayload,
    InjectionEvalPayload,
    InjectionProbeRow,
    IntegrityAdvantagePayload,
    LearnedRetrievalPayload,
    LongMemEvalPayload,
    NeuralEvalPayload,
    OrchestrationBaseline,
    SampleSizePayload,
    ScalingCiPayload,
)
from ..figure_style import EXPORT_DPI, PALETTE, annotate_bars as _annotate_bars
from ..figure_style import plt, prepare as _prepare, pretty as _pretty, zoomed_ylim as _zoomed_ylim



def plot_retriever_comparison(comparison: RetrieverComparison, output_path: str | Path) -> Path:
    """Bar chart of lexical vs. semantic vs. hybrid composite metric."""
    path = _prepare(output_path)
    labels = ["Lexical\n(BM25/grep)", "Semantic\n(hashing)", "Hybrid\n(RRF)"]
    values = [comparison.lexical, comparison.semantic, comparison.hybrid]
    colors = [PALETTE["lexical"], PALETTE["semantic"], PALETTE["hybrid"]]

    fig, ax = plt.subplots()
    bars = ax.bar(labels, values, color=colors, edgecolor=PALETTE["ink"], linewidth=0.6)
    ax.set_ylabel("Composite metric (0–1)")
    ax.set_title("Retrieval modes under a slack inline budget")
    ax.set_ylim(0, 1)
    _annotate_bars(ax, bars, values, dy=0.02)
    # The clean-set tie is a measured property of this finite bundle. State it on
    # the figure so equal bars carry an interpretable annotation.
    if max(values) - min(values) < 1e-9:
        ax.annotate(
            f"all lanes = {values[0]:.3f}; the clean bundle exposes the same gold span\n"
            "the tight-budget noise probe supplies the contrast",
            (0.5, 0.88),
            xycoords="axes fraction",
            ha="center",
            fontsize=8,
            color=PALETTE["muted"],
        )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_rrf_weight_sensitivity(output_path: str | Path, steps: int = 11) -> Path:
    """Line plot of composite metric vs. lexical lane weight (RRF sweep)."""
    path = _prepare(output_path)
    sweep = rrf_weight_sweep(steps=steps)
    weights = [w for w, _ in sweep]
    scores = [s for _, s in sweep]
    best_w, best_s = max(sweep, key=lambda pair: pair[1])

    fig, ax = plt.subplots()
    ax.plot(weights, scores, marker="o", color=PALETTE["hybrid"], linewidth=1.8, zorder=2)
    ax.set_ylim(*_zoomed_ylim(scores, pad=0.012))
    # Draw the maximum on top with a halo and label the observed minimum so the
    # budget-specific shape is directly readable.
    ax.scatter([best_w], [best_s], s=90, facecolor=PALETTE["accent"], edgecolor="white", linewidth=1.4, zorder=5, label=f"optimum @ w_lex={best_w:.2f}")
    dip_i = min(range(len(scores)), key=lambda i: scores[i])
    if 0 < dip_i < len(scores) - 1:
        ax.annotate(
            f"minimum at w_lex={weights[dip_i]:.2f}: {scores[dip_i]:.3f}\n"
            f"Δ vs maximum = {scores[dip_i] - best_s:+.3f}",
            (weights[dip_i], scores[dip_i]),
            textcoords="offset points",
            xytext=(44, 26),  # up-and-right of the dip, clear of the x-axis ticks
            ha="center",
            fontsize=8,
            color=PALETTE["muted"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["muted"], lw=0.8),
        )
    ax.margins(x=0.04)  # ensure the far-left optimum marker (w_lex=0) is fully visible
    ax.set_xlabel("Lexical lane weight (semantic = 1 − weight)")
    ax.set_ylabel("Composite metric (zoomed)")
    ax.set_title("RRF composite across lexical weights")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_compiler_convergence(
    trace: list[tuple[HarnessConfig | None, float]],
    output_path: str | Path,
    components: dict[str, float] | None = None,
) -> Path:
    """Compiler search trace, with the component decomposition that explains the tie.

    The composite-vs-candidate curve is flat on the easy dataset. The inset bars
    show the three weighted metric components that produce the tie
    (answer token-F1/citation-support/efficiency constant across candidates).
    ``components`` is a
    ``{"accuracy","grounding","efficiency"}`` dict (e.g. from ``run_full_eval``).
    """
    path = _prepare(output_path)
    scores = [score for _, score in trace]
    best_so_far: list[float] = []
    running = float("-inf")
    for s in scores:
        running = max(running, s)
        best_so_far.append(running)
    x = list(range(1, len(scores) + 1))
    tied = bool(scores) and max(scores) - min(scores) < 1e-9

    fig, ax = plt.subplots()
    ax.plot(x, scores, marker="o", color=PALETTE["muted"], linewidth=1.0, label="candidate composite")
    ax.plot(x, best_so_far, color=PALETTE["hybrid"], linewidth=2.0, linestyle=(0, (4, 3)), label="best so far")
    ax.set_xlabel("Candidate / iteration")
    ax.set_ylabel("Composite metric (0–1)")
    ax.set_title("Compiler candidate scores and weighted components")
    ax.set_ylim(0, 1)
    if tied:
        ax.annotate(
            f"all {len(scores)} candidates = {scores[0]:.3f}\n"
            "reported configuration follows the deterministic tie rule",
            (x[len(x) // 2], scores[0]),
            textcoords="offset points", xytext=(0, 20), ha="center", fontsize=8, color=PALETTE["muted"],
        )
    # Inset: the weighted components that sum to the (constant) composite — proving the tie.
    if components:
        labels = [
            f"{ACCURACY_WEIGHT:.1f}·F1",
            f"{GROUNDING_WEIGHT:.1f}·support",
            f"{EFFICIENCY_WEIGHT:.1f}·eff",
        ]
        vals = [
            ACCURACY_WEIGHT * components["accuracy"],
            GROUNDING_WEIGHT * components["grounding"],
            EFFICIENCY_WEIGHT * components["efficiency"],
        ]
        colors = [PALETTE["lexical"], PALETTE["hybrid"], PALETTE["accent"]]
        inset = ax.inset_axes((0.6, 0.1, 0.36, 0.42))
        pos = list(range(len(labels)))
        bars = inset.bar(pos, vals, color=colors, edgecolor=PALETTE["ink"], linewidth=0.4)
        for bar, v in zip(bars, vals):
            inset.text(bar.get_x() + bar.get_width() / 2, v + 0.006, f"{v:.2f}", ha="center", va="bottom", fontsize=7)
        inset.set_xticks(pos)
        inset.set_xticklabels(labels, fontsize=7)
        inset.set_ylim(0, max(vals) * 1.35)
        inset.set_title("weighted components\n(same for every candidate)", fontsize=7.5)
        inset.tick_params(axis="y", labelsize=6)
        inset.set_yticks([])
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_consolidation_curve(output_path: str | Path, turns: int = 12) -> Path:
    """Schematic utility curves: forced consolidation vs. episodic-first.

    Illustrative mechanism chart for the consolidation-fault discussion from
    Zhang et al. (2026). The curves carry no observed data.
    """
    path = _prepare(output_path)
    sim = consolidation_simulation(turns=turns)
    x = list(range(1, turns + 1))

    fig, ax = plt.subplots()
    ax.plot(x, sim["forced"], marker="s", color=PALETTE["accent"], label="forced consolidation")
    ax.plot(x, sim["episodic_first"], marker="o", color=PALETTE["hybrid"], label="episodic-first (gated)")
    ax.axhline(0.5, color=PALETTE["muted"], linestyle="--", linewidth=1.0, label="no-memory baseline")
    ax.set_xlabel("Turn")
    ax.set_ylabel("Illustrative utility index")
    ax.set_title("Illustrative consolidation trajectories")
    ax.text(0.5, 1.02, "Mechanism schematic; values are illustrative", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=8, color=PALETTE["muted"])
    ax.set_ylim(0, 1)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_category_breakdown(category_means: dict[str, float], output_path: str | Path) -> Path:
    """Horizontal bar chart of composite metric per task category."""
    path = _prepare(output_path)
    items = sorted(category_means.items(), key=lambda kv: kv[1])
    labels = [_pretty(k) for k, _ in items]
    values = [v for _, v in items]
    # Highlight the observed minimum while keeping the remaining categories in the
    # common hybrid colour. The rule follows the supplied data and survives changes
    # in category ordering or task mix.
    minimum = min(values) if values else 0.0
    colors = [PALETTE["accent"] if value == minimum else PALETTE["hybrid"] for value in values]

    fig, ax = plt.subplots()
    ax.barh(labels, values, color=colors, edgecolor=PALETTE["ink"], linewidth=0.6)
    ax.set_xlabel("Composite metric (0–1)")
    ax.set_title("Per-task-category performance")
    ax.set_xlim(0, 1)
    ax.grid(axis="x")
    if values:
        mean_value = sum(values) / len(values)
        ax.axvline(mean_value, color=PALETTE["muted"], linestyle="--", linewidth=1.0, label=f"mean {mean_value:.3f}")
    for i, value in enumerate(values):
        ax.text(value + 0.01, i, f"{value:.3f}", va="center", fontsize=9)
    if values:
        ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_evidence_funnel(output_path: str | Path) -> Path:
    """Funnel of mean evidence counts, with retention rates that explain the narrowing."""
    path = _prepare(output_path)
    funnel = evidence_funnel()
    stages = ["session\nlines", "inspector\nwindows", "ranked\nevidence", "cited\nsources"]
    values = [funnel["session_lines"], funnel["windows"], funnel["ranked"], funnel["cited"]]
    colors = [PALETTE["muted"], PALETTE["lexical"], PALETTE["hybrid"], PALETTE["accent"]]

    fig, ax = plt.subplots()
    bars = ax.bar(stages, values, color=colors, edgecolor="black", linewidth=0.6)
    ax.set_ylabel("Mean count per query")
    ax.set_title("Evidence counts at pipeline boundaries", pad=28)
    session_retention = values[1] / values[0] if values[0] else 0.0
    citation_retention = values[3] / values[2] if values[2] else 0.0
    ax.text(
        0.5,
        1.02,
        f"Inspector retention {session_retention:.0%} · citation retention {citation_retention:.0%}",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8,
        color=PALETTE["muted"],
    )
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.05, f"{value:.1f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(values) * 1.18)
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_pipeline_flow(
    flow_data: list[dict],
    output_path: str | Path,
) -> Path:
    """Grouped bar chart of per-example evidence counts at each Pipeline stage.

    Shows evidence counts at Inspector, Retriever, and Reasoner boundaries for
    every demo example. Three bars per group:

    * **windows** (lexical blue) — Inspector output.
    * **ranked** (hybrid green) — Retriever output.
    * **cited** (accent pink) — Reasoner citations.

    Args:
        flow_data: List of dicts as returned by
            :func:`src.evaluation.pipeline_evidence_flow`.
        output_path: Destination path for the 300-dpi PNG.

    Returns:
        The resolved output :class:`~pathlib.Path`.
    """
    path = _prepare(output_path)
    n = len(flow_data)
    width = 0.25
    x = list(range(n))

    windows = [row["n_windows"] for row in flow_data]
    ranked = [row["n_ranked"] for row in flow_data]
    cited = [row["n_cited"] for row in flow_data]
    # Label each group by task category so the complete category code remains
    # visible and consistent with the evaluation framing.
    labels = [_pretty(str(row.get("task_category", row.get("query", "")))).replace("_", " ") for row in flow_data]

    fig, ax = plt.subplots(figsize=(max(6.2, n * 1.4), 4.4))
    ax.bar([xi - width for xi in x], windows, width=width, color=PALETTE["lexical"], edgecolor=PALETTE["ink"], linewidth=0.5, label="inspector windows")
    ax.bar(x, ranked, width=width, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label="retriever ranked")
    ax.bar([xi + width for xi in x], cited, width=width, color=PALETTE["accent"], edgecolor=PALETTE["ink"], linewidth=0.5, label="reasoner cited")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Evidence count per example")
    mean_ranked = sum(ranked) / n if n else 0.0
    mean_cited = sum(cited) / n if n else 0.0
    citation_rate = mean_cited / mean_ranked if mean_ranked else 0.0
    losses = [ranked[i] - cited[i] for i in range(n)]
    max_loss = max(losses, default=0)
    loss_labels = [labels[i] for i, loss in enumerate(losses) if loss == max_loss and loss > 0]
    if loss_labels:
        loss_text = f"largest citation gap: {', '.join(loss_labels)} (−{max_loss})"
    else:
        loss_text = "all ranked evidence is cited in the recorded examples"
    ax.set_title("Per-example evidence counts by stage", pad=30)
    ax.text(
        0.5,
        1.02,
        f"{citation_rate:.0%} of ranked evidence is cited · {loss_text}",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8,
        color=PALETTE["muted"],
    )
    for xi, ranked_value, cited_value, loss in zip(x, ranked, cited, losses):
        if loss > 0:
            ax.annotate(
                f"−{loss}",
                (xi + width, cited_value),
                textcoords="offset points",
                xytext=(0, 7),
                ha="center",
                fontsize=8,
                fontweight="bold",
                color=PALETTE["accent"],
            )
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", linewidth=0.4)
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_noise_scaling(output_path: str | Path) -> Path:
    """Composite metric per retrieval mode as session noise scales."""
    path = _prepare(output_path)
    experiment = noise_scaling_experiment()

    fig, ax = plt.subplots()
    # The hybrid lane tracks the lexical lane exactly on this dataset. Distinct
    # line styles and markers preserve both series in the exported figure.
    style: dict[str, dict[str, Any]] = {
        "lexical": dict(linestyle="-", marker="o", linewidth=1.8, zorder=2),
        "semantic": dict(linestyle="-", marker="s", linewidth=1.8, zorder=2),
        "hybrid": dict(linestyle="--", marker="x", linewidth=1.8, zorder=3),
    }
    label_dy = {"lexical": -11, "semantic": 4, "hybrid": 7}
    for mode in ("lexical", "semantic", "hybrid"):
        levels = [lvl for lvl, _ in experiment[mode]]
        scores = [s for _, s in experiment[mode]]
        ax.plot(levels, scores, color=PALETTE[mode], label=mode, **style[mode])
        # Label each lane at the noisiest level. Vertical offsets keep overlapping
        # labels legible.
        ax.annotate(
            f"{scores[-1]:.3f}",
            (levels[-1], scores[-1]),
            textcoords="offset points",
            xytext=(4, label_dy[mode]),
            fontsize=8,
            color=PALETTE[mode],
        )
    ax.set_xlabel("Distractor lines added (session noise)")
    ax.set_ylabel("Composite metric (0–1)")
    ax.set_title("Composite score under session noise")
    ax.set_ylim(0, 1)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_mmr_tradeoff(output_path: str | Path, steps: int = 11) -> Path:
    """Composite metric as the MMR lambda (relevance/diversity) is swept 0..1."""
    path = _prepare(output_path)
    sweep = mmr_lambda_sweep(steps=steps)
    lambdas = [lam for lam, _ in sweep]
    scores = [s for _, s in sweep]

    fig, ax = plt.subplots()
    ax.plot(lambdas, scores, marker="o", color=PALETTE["accent"], linewidth=1.8)
    ax.set_ylim(*_zoomed_ylim(scores, pad=0.01))
    ax.set_xlabel("MMR λ  (0 = max diversity, 1 = pure relevance)")
    ax.set_ylabel("Composite metric (zoomed)")
    ax.set_title("MMR score across relevance weights")
    # The finite sweep has a visible penalty at λ=0; the zoomed axis makes that
    # observed difference readable.
    if len(scores) > 1 and scores[0] < scores[1]:
        ax.annotate(
            f"λ=0 score {scores[0]:.3f}\nΔ vs λ={lambdas[1]:.2f}: {scores[0] - scores[1]:+.3f}",
            (lambdas[0], scores[0]),
            textcoords="offset points",
            xytext=(34, -2),
            fontsize=8,
            color=PALETTE["accent"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["accent"], lw=0.8),
        )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_method_ablation(output_path: str | Path) -> Path:
    """Bar chart of composite metric for base + each added method + all combined."""
    path = _prepare(output_path)
    ablation = method_ablation()
    labels = list(ablation.keys())
    values = [ablation[k] for k in labels]
    colors = [PALETTE["muted"]] + [PALETTE["lexical"], PALETTE["semantic"], PALETTE["accent"], PALETTE["hybrid"]][
        : len(labels) - 1
    ]

    fig, ax = plt.subplots()
    lo, hi = _zoomed_ylim(values, pad=0.02)
    bars = ax.bar(labels, values, color=colors, edgecolor=PALETTE["ink"], linewidth=0.6)
    base = values[0]
    ax.axhline(base, color=PALETTE["muted"], linestyle="--", linewidth=0.9, zorder=0, label=f"base = {base:.3f}")
    ax.set_ylabel("Composite metric (zoomed)")
    ax.set_title("Added-method ablation under a tight budget")
    ax.set_ylim(lo, hi)
    _annotate_bars(ax, bars, values, dy=(hi - lo) * 0.01)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_backend_comparison(data: NeuralEvalPayload, output_path: str | Path) -> Path:
    """Per-example extractive vs real neural Reasoner token-F1.

    The comparison uses paired example-level points because each backend produces
    an outcome for the same retained question. Data comes from
    ``data/neural_eval.json``.
    """
    path = _prepare(output_path)
    rows = sorted(data.rows, key=lambda r: (r.neural_f1 - r.extractive_f1, r.category))
    category_codes = {
        category: "".join(part[0] for part in category.split("_"))[:3].upper()
        for category in {row.category for row in rows}
    }
    labels = [f"{index + 1}\n{category_codes[r.category]}" for index, r in enumerate(rows)]
    ext = [r.extractive_f1 for r in rows]
    neu = [r.neural_f1 for r in rows]
    x = list(range(len(rows)))

    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    for i, (e, n) in enumerate(zip(ext, neu)):
        ax.plot([i, i], [e, n], color="#BBBBBB", linewidth=1.2, zorder=1)
    ax.scatter(x, ext, color=PALETTE["muted"], edgecolor=PALETTE["ink"], linewidth=0.5, s=48, label="extractive")
    ax.scatter(
        x,
        neu,
        color=PALETTE["semantic"],
        edgecolor=PALETTE["ink"],
        linewidth=0.5,
        s=56,
        marker="s",
        label=f"neural ({data.model})",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0, ha="center", fontsize=8)
    ax.set_ylabel("Token-F1 vs gold answer")
    ax.set_xlabel("Paired example index (category code below index; n={})".format(data.n))
    ax.set_ylim(0, 1)
    summary = data.extractive_statistics or data.neural_statistics
    confidence = int(summary.confidence * 100) if summary else int(DEFAULT_CONFIDENCE_LEVEL * 100)
    ax.set_title(f"Paired backend observations by example (n={data.n})")
    me, mn = data.mean_extractive_f1, data.mean_neural_f1
    ax.axhline(me, color=PALETTE["muted"], linestyle=":", linewidth=1.0, zorder=0)
    ax.axhline(mn, color=PALETTE["semantic"], linestyle=":", linewidth=1.0, zorder=0)
    if data.extractive_statistics:
        ax.axhspan(
            data.extractive_statistics.low,
            data.extractive_statistics.high,
            color=PALETTE["muted"],
            alpha=0.10,
            zorder=0,
            label=f"extractive {int(data.extractive_statistics.confidence * 100)}% descriptive interval",
        )
    if data.neural_statistics:
        ax.axhspan(
            data.neural_statistics.low,
            data.neural_statistics.high,
            color=PALETTE["semantic"],
            alpha=0.10,
            zorder=0,
            label=f"neural {int(data.neural_statistics.confidence * 100)}% descriptive interval",
        )
    ax.annotate(
        f"mean token-F1 | extractive {me:.3f} | neural {mn:.3f}\n"
        f"bands: {confidence}% descriptive intervals",
        (0.02, 0.95),
        xycoords="axes fraction",
        ha="left",
        va="top",
        fontsize=9,
        color=PALETTE["ink"],
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#DDDDDD", alpha=0.9),
    )
    if data.paired_comparison:
        paired = data.paired_comparison
        ax.annotate(
            f"paired Δ={float(paired.get('mean_delta', mn - me)):+.3f}; "
            f"p_signflip={float(paired.get('p_value', 1.0)):.3f}",
            (0.02, 0.87),
            xycoords="axes fraction",
            ha="left",
            va="top",
            fontsize=8.5,
            color=PALETTE["ink"],
        )
    ax.grid(axis="y")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_bottleneck(data: BottleneckPayload, output_path: str | Path) -> Path:
    """Show the bottleneck diagnostics without mixing their constructs.

    Session reachability, citation-support proxy, and neural answer token-F1 are
    rendered in separate panels. This keeps a context-exposure rate from looking
    like an answer-quality rate merely because both lie in ``[0, 1]``.
    """
    path = _prepare(output_path)
    mws = sorted(data.extractive_grounding_by_maxwindows)
    proxy = [data.extractive_grounding_by_maxwindows[k] for k in mws]
    reachability = (
        [data.extractive_session_reachability_by_maxwindows[k] for k in sorted(data.extractive_session_reachability_by_maxwindows)]
        if data.extractive_session_reachability_by_maxwindows
        else []
    )
    reach_mws = sorted(data.extractive_session_reachability_by_maxwindows or {})
    neural_points = [
        (mw, row.accuracy, row.grounding, row.session_reachability)
        for mw, row in data.neural_by_maxwindows.items()
        if row.accuracy is not None
    ]
    sorted_neural = sorted(neural_points)
    nmws = [mw for mw, _, _, _ in sorted_neural]
    neural_acc = [accuracy for _, accuracy, _, _ in sorted_neural]
    neural_proxy = [grounding for _, _, grounding, _ in sorted_neural if grounding is not None]
    neural_proxy_mws = [mw for mw, _, grounding, _ in sorted_neural if grounding is not None]
    adaptive = data.neural_adaptive
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.2), sharey=True)
    reach_ax, proxy_ax, answer_ax = axes

    def label_points(axis: Any, xs: list[int], ys: list[float], color: str, offset: int = 7) -> None:
        for x_value, y_value in zip(xs, ys):
            axis.annotate(
                f"{y_value:.2f}",
                (x_value, y_value),
                textcoords="offset points",
                xytext=(0, offset),
                ha="center",
                fontsize=7,
                color=color,
            )

    if reachability:
        reach_ax.plot(reach_mws, reachability, marker="o", color=PALETTE["hybrid"], linewidth=1.8, label="extractive")
        label_points(reach_ax, reach_mws, reachability, PALETTE["hybrid"])
        neural_reach = [(mw, value) for mw, _, _, value in sorted_neural if value is not None]
        if neural_reach:
            neural_reach_x = [mw for mw, _ in neural_reach]
            neural_reach_y = [value for _, value in neural_reach]
            reach_ax.plot(
                neural_reach_x,
                neural_reach_y,
                marker="s",
                color=PALETTE["semantic"],
                linewidth=1.8,
                label=f"neural ({data.neural_model})",
            )
            label_points(reach_ax, neural_reach_x, neural_reach_y, PALETTE["semantic"], offset=-12)
        reach_ax.set_title("A. Session reachability")
        reach_ax.set_ylabel("Metric value (0–1)")
        reach_ax.legend(loc="best", fontsize=8)
    else:
        reach_ax.text(0.5, 0.5, "Not recorded in\nthis aggregate", ha="center", va="center", transform=reach_ax.transAxes)
        reach_ax.set_title("A. Session reachability")
        reach_ax.set_ylabel("Metric value (0–1)")
    proxy_ax.plot(mws, proxy, marker="o", color=PALETTE["hybrid"], linewidth=1.8, label="extractive")
    label_points(proxy_ax, mws, proxy, PALETTE["hybrid"])
    if neural_proxy:
        proxy_ax.plot(
            neural_proxy_mws,
            neural_proxy,
            marker="s",
            color=PALETTE["semantic"],
            linewidth=1.8,
            label=f"neural ({data.neural_model})",
        )
        label_points(proxy_ax, neural_proxy_mws, neural_proxy, PALETTE["semantic"], offset=-12)
    proxy_ax.set_title("B. Citation-support proxy")
    proxy_ax.set_xlabel("Inspector max_windows")
    proxy_ax.legend(loc="best", fontsize=8)
    answer_ax.plot(nmws, neural_acc, marker="s", color=PALETTE["semantic"], linewidth=1.8, label=f"neural ({data.neural_model})")
    label_points(answer_ax, nmws, neural_acc, PALETTE["semantic"])
    if len(neural_acc) == 2:
        answer_ax.annotate(
            f"Δ token-F1 {neural_acc[1] - neural_acc[0]:+.3f}",
            (nmws[1], neural_acc[1]),
            textcoords="offset points",
            xytext=(-6, 10),
            fontsize=8.5,
            color=PALETTE["semantic"],
            ha="right",
        )
    answer_ax.set_title("C. Answer token-F1")
    answer_ax.set_xlabel("Inspector max_windows")
    answer_ax.legend(loc="best", fontsize=8)
    for ax in axes:
        ax.set_ylim(0, 1.0)
        ax.grid(True)
    if adaptive:
        adaptive_x = nmws[-1] if nmws else (mws[-1] if mws else 0)
        if adaptive.grounding is not None:
            proxy_ax.axhline(adaptive.grounding, color=PALETTE["accent"], linestyle=":", linewidth=1.4, zorder=1)
            proxy_ax.scatter([adaptive_x], [adaptive.grounding], marker="*", s=150, color=PALETTE["accent"], zorder=6, label="adaptive")
        answer_ax.axhline(adaptive.accuracy, color=PALETTE["accent"], linestyle=":", linewidth=1.4, zorder=1)
        answer_ax.scatter([adaptive_x], [adaptive.accuracy], marker="*", s=150, color=PALETTE["accent"], zorder=6, label="adaptive")
        proxy_ax.legend(loc="best", fontsize=8)
        answer_ax.legend(loc="best", fontsize=8)
    fig.suptitle("Inspector-window sweep: retained benchmark diagnostics", y=1.02)
    mode = data.ranking_recall_by_mode
    if mode:
        mode_text = (
            f"lex {mode.lexical:.2f} / dense {mode.dense:.2f} / hybrid {mode.hybrid:.2f}"
            f" (n={mode.n}, k={mode.k})"
        )
    else:
        mode_text = "dense/hybrid mode rows unavailable"
    fig.text(
        0.5,
        0.012,
        f"ranking recall: full haystack {data.ranking_recall_at_10:.2f} | Inspector {data.inspector_recall:.2f} · "
        f"{mode_text} · neural rows={data.n_neural or 'NA'}",
        ha="center",
        va="bottom",
        fontsize=8.0,
        color=PALETTE["muted"],
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.95))
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_longmemeval(data: LongMemEvalPayload, output_path: str | Path) -> Path:
    """Plot answer token-F1 and evidence exposure as separate constructs."""
    path = _prepare(output_path)
    backends = ["Extractive", f"Neural\n({data.neural_model})"]
    acc = [data.extractive_accuracy, data.neural_accuracy]
    support = [data.extractive_grounding, data.neural_grounding]
    reachability = (
        [data.extractive_session_reachability, data.neural_session_reachability]
        if data.extractive_session_reachability is not None and data.neural_session_reachability is not None
        else None
    )
    x = range(len(backends))

    fig, axes = plt.subplots(1, 3 if reachability is not None else 2, figsize=(10.2 if reachability is not None else 7.2, 4.2), sharey=True)
    axes = list(axes) if isinstance(axes, (list, tuple)) else list(axes.flat)
    answer_ax = axes[0]
    support_ax = axes[1]
    am = [t[0] for t in acc]
    ae = [[t[0] - t[1] for t in acc], [t[2] - t[0] for t in acc]]
    answer_ax.bar(list(x), am, width=0.55, yerr=ae, capsize=4, color=PALETTE["semantic"], edgecolor=PALETTE["ink"], linewidth=0.5, label="answer token-F1", error_kw={"elinewidth": 1.1})
    for i, t in zip(list(x), acc):
        answer_ax.text(i, t[2] + 0.015, f"{t[0]:.3f}", ha="center", va="bottom", fontsize=8)
    answer_ax.set_title("A. Answer token-F1")
    answer_ax.set_ylabel("Metric value (0–1)")
    answer_ax.set_xticks(list(x))
    answer_ax.set_xticklabels(backends)
    sm = [t[0] for t in support]
    se = [[t[0] - t[1] for t in support], [t[2] - t[0] for t in support]]
    support_ax.bar(list(x), sm, width=0.55, yerr=se, capsize=4, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label="citation-support proxy", error_kw={"elinewidth": 1.1})
    for i, t in zip(list(x), support):
        support_ax.text(i, t[2] + 0.015, f"{t[0]:.3f}", ha="center", va="bottom", fontsize=8)
    support_ax.set_title("B. Citation-support proxy")
    support_ax.set_xticks(list(x))
    support_ax.set_xticklabels(backends)
    if reachability is not None:
        reach_ax = axes[2]
        rm = [t[0] for t in reachability]
        re = [[t[0] - t[1] for t in reachability], [t[2] - t[0] for t in reachability]]
        reach_ax.bar(list(x), rm, width=0.55, yerr=re, capsize=4, color=PALETTE["accent"], edgecolor=PALETTE["ink"], linewidth=0.5, label="session reachability", error_kw={"elinewidth": 1.1})
        for i, t in zip(list(x), reachability):
            reach_ax.text(i, t[2] + 0.015, f"{t[0]:.3f}", ha="center", va="bottom", fontsize=8)
        reach_ax.set_title("C. Session reachability")
        reach_ax.set_xticks(list(x))
        reach_ax.set_xticklabels(backends)
    for ax in axes:
        ax.set_ylim(0, 1.0)
        ax.grid(axis="y")
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(
        f"LongMemEval_S retained slice (n={data.n_extractive} extractive, {data.n_neural} neural)",
        y=1.04,
    )
    fig.text(
        0.5,
        0.01,
        f"Vertical bars show {int(data.confidence * 100)}% descriptive percentile intervals; panels use separate outcomes",
        ha="center",
        va="bottom",
        fontsize=8,
        color=PALETTE["muted"],
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_scaling_ci(data: ScalingCiPayload, output_path: str | Path) -> Path:
    """Per-category accuracy with descriptive intervals on seeded synthetic data.

    The demo set is a point diagnostic, while this seeded synthetic set has
    repeated observations. Data from
    :func:`src.evaluation.large_dataset_eval`.
    """
    path = _prepare(output_path)
    items = sorted(data.category_accuracy.items(), key=lambda kv: kv[1][0])
    labels = [_pretty(c) for c, _ in items]
    means = [m for _, (m, _, _) in items]
    lo = [m - low for _, (m, low, _) in items]
    hi = [high - m for _, (m, _, high) in items]
    y = range(len(labels))

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.barh(list(y), means, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.6, height=0.62, zorder=2)
    ax.errorbar(means, list(y), xerr=[lo, hi], fmt="none", ecolor=PALETTE["ink"], elinewidth=1.2, capsize=4, zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1)
    ax.set_xlabel(f"Answer token-F1 ({int(data.confidence * 100)}% descriptive bootstrap interval)")
    ax.set_title(f"Synthetic category answer token-F1 (n={data.n}, {data.per_category}/category)")
    overall_accuracy = sum(means) / len(means)
    ax.axvline(overall_accuracy, color=PALETTE["accent"], linestyle="--", linewidth=1.0, zorder=1, label=f"mean token-F1 {overall_accuracy:.3f}")
    for yi, mean in zip(y, means):
        ax.text(mean + 0.015, yi, f"{mean:.3f}", va="center", fontsize=8.5)
    ax.grid(axis="x")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_sample_size_precision(data: SampleSizePayload, output_path: str | Path) -> Path:
    """Show precision growth and paired method deltas across sample sizes.

    The left panel reports method means with descriptive intervals over multiple
    independent seeds. The right panel reports paired hybrid-minus-baseline
    deltas with the corresponding intervals and Holm-adjusted p-values.
    Sample-size accounting and the paired estimand share one figure.
    """
    path = _prepare(output_path)
    rows = sorted(data.rows, key=lambda row: row.n_total)
    x = [row.n_total for row in rows]
    colors = {"hybrid": PALETTE["hybrid"], "lexical": PALETTE["lexical"], "semantic": PALETTE["semantic"]}
    accounting = data.accounting or {}
    unique_examples = int(accounting.get("n_unique_examples", sum(row.n_total for row in rows)))
    method_evaluations = int(accounting.get("n_method_evaluations", unique_examples * 3))
    failed = int(accounting.get("n_failed", 0))
    family = data.comparison_family or {}
    interval_label = str(accounting.get("interval_interpretation", "descriptive resampling interval"))
    cluster_warning = bool(accounting.get("small_cluster_warning", False))
    cluster_note = (
        "small-cluster warning applies"
        if cluster_warning
        else "small-cluster diagnostic threshold not triggered"
    )
    x_labels = [f"{row.n_total:,}\n{row.per_category}/cat" for row in rows]

    fig, (ax_mean, ax_delta) = plt.subplots(1, 2, figsize=(10.2, 4.2), sharex=False)
    for method in ("hybrid", "lexical", "semantic"):
        if not all(method in row.methods for row in rows):
            continue
        summaries = [row.methods[method] for row in rows]
        means = [summary.estimate for summary in summaries]
        errors = [
            [summary.estimate - summary.low for summary in summaries],
            [summary.high - summary.estimate for summary in summaries],
        ]
        ax_mean.errorbar(
            x,
            means,
            yerr=errors,
            marker="o",
            linewidth=1.7,
            capsize=3,
            color=colors[method],
            label=method,
        )
    ax_mean.set_xlabel("Total unique examples (paired across methods)")
    ax_mean.set_ylabel(f"Composite (mean ± {int(data.confidence * 100)}% descriptive interval)")
    ax_mean.set_title("Method means across audited sample sizes")
    ax_mean.set_xticks(x)
    ax_mean.set_ylim(0, 1)
    ax_mean.grid(True)
    ax_mean.legend(loc="best")
    ax_mean.set_xticklabels(x_labels, rotation=25, ha="right")

    comparison_keys = ("hybrid_vs_lexical", "hybrid_vs_semantic")
    comparison_colors = {comparison_keys[0]: PALETTE["lexical"], comparison_keys[1]: PALETTE["semantic"]}
    labels = {comparison_keys[0]: "Hybrid − lexical", comparison_keys[1]: "Hybrid − surrogate semantic"}
    for key in comparison_keys:
        if not all(key in row.paired_comparisons for row in rows):
            continue
        comparisons = [row.paired_comparisons[key] for row in rows]
        means = [float(comparison["mean_delta"]) for comparison in comparisons]
        errors = [
            [mean - float(comparison["low"]) for mean, comparison in zip(means, comparisons)],
            [float(comparison["high"]) - mean for mean, comparison in zip(means, comparisons)],
        ]
        ax_delta.errorbar(
            x,
            means,
            yerr=errors,
            marker="o",
            linewidth=1.7,
            capsize=3,
            color=comparison_colors[key],
            label=labels[key],
        )
        last_p: float | None = None
        for index, (n_value, mean, comparison) in enumerate(zip(x, means, comparisons)):
            p_value = float(comparison["holm_adjusted_p_value"])
            # Label the first point, the last point, and every change so a flat
            # curve stays readable while future non-flat runs remain auditable.
            if index < len(comparisons) - 1 and last_p is not None and p_value == last_p:
                continue
            ax_delta.annotate(
                f"p_Holm={p_value:.3f}",
                (n_value, mean),
                textcoords="offset points",
                xytext=(0, 8 if key == comparison_keys[0] else -15),
                ha="center",
                fontsize=7,
                color=comparison_colors[key],
            )
            last_p = p_value
    ax_delta.axhline(0.0, color=PALETTE["ink"], linewidth=0.8)
    ax_delta.set_xlabel("Total unique examples (paired across methods)")
    ax_delta.set_ylabel("Paired composite delta")
    ax_delta.set_title("Paired deltas with Holm-adjusted p-values")
    ax_delta.set_xticks(x)
    ax_delta.set_xticklabels(x_labels, rotation=25, ha="right")
    ax_delta.grid(True)
    ax_delta.legend(loc="best")
    fig.suptitle(
        f"Seeded statistical audit: {data.categories} categories × {len(data.seed_values)} seeds; "
        f"{data.n_boot:,} resamples",
        y=1.08,
        fontsize=13,
        fontweight="semibold",
    )
    fig.text(
        0.5,
        1.015,
        f"rows={unique_examples:,} · method evaluations={method_evaluations:,} · failures={failed:,} · "
        f"Holm family m={family.get('size', '—')} · {interval_label}"
        + f" · {cluster_note}",
        ha="center",
        va="center",
        fontsize=8.5,
        color=PALETTE["muted"],
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.91))
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_statistical_audit(data: SampleSizePayload, output_path: str | Path) -> Path:
    """Render seed-cluster paired effects by stratum.

    The paired interval is computed from aligned hybrid/baseline outcomes within
    each stratum and resamples whole seed clusters. The figure displays the paired
    comparison estimand directly; marginal interval subtraction would define a
    different quantity.
    """
    path = _prepare(output_path)
    row = sorted(data.rows, key=lambda item: item.n_total)[-1]
    strata = sorted({stratum for values in row.stratum_statistics.values() for stratum in values})
    labels: list[str] = []
    effects: list[float] = []
    lows: list[float] = []
    highs: list[float] = []
    colors: list[str] = []
    p_values: list[float | None] = []
    paired_by_baseline = row.stratum_paired_comparisons
    for stratum in strata:
        for baseline, color in (("lexical", PALETTE["lexical"]), ("semantic", PALETTE["semantic"])):
            comparison_key = f"hybrid_vs_{baseline}"
            comparison = paired_by_baseline.get(comparison_key, {}).get(stratum)
            if not comparison or "mean_delta" not in comparison:
                continue
            effect = float(comparison["mean_delta"])
            low = float(comparison["low"])
            high = float(comparison["high"])
            p_value = comparison.get("holm_adjusted_p_value")
            if high < low:
                continue
            effects.append(effect)
            lows.append(low)
            highs.append(high)
            labels.append(f"{_pretty(stratum)}: H−{baseline[0].upper()}")
            colors.append(color)
            p_values.append(float(p_value) if p_value is not None else None)
    y = list(range(len(labels)))
    fig, (ax, info) = plt.subplots(1, 2, figsize=(10.8, 4.8), gridspec_kw={"width_ratios": [3.4, 1.4]})
    if effects:
        for effect, low, high, position, color, p_value in zip(effects, lows, highs, y, colors, p_values):
            ax.errorbar(
                effect,
                position,
                xerr=[[effect - low], [high - effect]],
                fmt="none",
                ecolor=color,
                elinewidth=1.3,
                capsize=3,
            )
        ax.scatter(effects, y, c=colors, edgecolors=PALETTE["ink"], zorder=3)
        for effect, high, position, p_value in zip(effects, highs, y, p_values):
            if p_value is not None:
                ax.annotate(
                    f"Δ {effect:+.4f}\np_Holm {p_value:.3f}",
                    (high, position),
                    textcoords="offset points",
                    xytext=(4, 0),
                    va="center",
                    fontsize=7,
                    color=PALETTE["muted"],
                )
    ax.axvline(0.0, color=PALETTE["ink"], linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel(f"Hybrid minus baseline ({int(data.confidence * 100)}% seed-cluster descriptive interval)")
    ax.set_title("Paired effects by difficulty stratum")
    ax.grid(axis="x")
    accounting = getattr(row, "n_total", 0)
    total_accounting = data.accounting or {}
    family = data.comparison_family or {}
    cluster_warning = bool(total_accounting.get("small_cluster_warning", False))
    cluster_note = (
        "warning: fewer than 10 clusters"
        if cluster_warning
        else "threshold not triggered; interval remains descriptive"
    )
    info.axis("off")
    info.text(0.0, 0.95, "Recorded design", fontweight="bold", va="top")
    info.text(
        0.0,
        0.82,
        f"largest row n={accounting:,}\n{row.n_seeds} seed clusters\n"
        f"{len(strata)} strata\n{data.n_boot:,} resamples\n"
        f"failures={int(total_accounting.get('n_failed', 0))}\n"
        f"cluster note:\n{cluster_note}",
        va="top",
    )
    info.text(0.0, 0.48, "Estimand", fontweight="bold", va="top")
    info.text(
        0.0,
        0.38,
        "paired mean delta\ncluster-resampling interval\nHolm-adjusted p-values",
        va="top",
    )
    info.text(0.0, 0.20, "Comparison family", fontweight="bold", va="top")
    family_size = family.get("size", "unknown")
    info.text(0.0, 0.10, f"method × stratum grid\nm={family_size} comparisons", va="top")
    if effects:
        observed_low = min(lows)
        observed_high = max(highs)
        observed_span = observed_high - observed_low
        margin = max(observed_span * 0.12, max(abs(observed_low), abs(observed_high), 1e-6) * 0.08, 1e-5)
        ax.set_xlim(min(0.0, observed_low) - margin, max(0.0, observed_high) + margin)
        ax.legend(handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=PALETTE["lexical"], markeredgecolor=PALETTE["ink"], label="H−lexical"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor=PALETTE["semantic"], markeredgecolor=PALETTE["ink"], label="H−semantic"),
        ], loc="best")
    fig.suptitle("Statistical evidence audit: paired finite-set effects", y=1.02, fontsize=13, fontweight="semibold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_injection_resistance(data: InjectionEvalPayload, output_path: str | Path) -> Path:
    """Finite context-poisoning grid with a lexical cited-excerpt proxy."""
    path = _prepare(output_path)
    neural_by_probe = {row.probe: row for row in data.neural_rows}
    rows = [
        InjectionProbeRow(
            probe=row.probe,
            harness_poisoned=row.harness_poisoned,
            harness_auditable=row.harness_auditable,
            naive_poisoned=row.naive_poisoned,
            naive_auditable=row.naive_auditable,
            neural_poisoned=neural_by_probe[row.probe].neural_poisoned if row.probe in neural_by_probe else None,
            neural_auditable=neural_by_probe[row.probe].neural_auditable if row.probe in neural_by_probe else None,
        )
        for row in data.rows
    ]
    n = data.n_probes
    conditions = [
        ("Harness", "harness_poisoned", "harness_auditable", data.harness_poison_ci),
        ("Naive", "naive_poisoned", "naive_auditable", data.naive_poison_ci),
    ]
    if data.neural_poison_rate is not None:
        conditions.append((f"Neural\n({data.neural_model})", "neural_poisoned", "neural_auditable", data.neural_poison_ci))

    fig, ax = plt.subplots(figsize=(max(7.5, min(13.0, 0.32 * n)), 4.2))
    for y, (_label, poison_key, audit_key, _interval) in enumerate(conditions):
        for x, row in enumerate(rows):
            poisoned = getattr(row, poison_key)
            auditable = getattr(row, audit_key)
            if poisoned is None or auditable is None:
                ax.scatter(
                    x,
                    y,
                    s=240,
                    marker="$?$",
                    color="white",
                    edgecolor=PALETTE["muted"],
                    linewidth=0.9,
                    zorder=3,
                )
                continue
            face = PALETTE["accent"] if poisoned else PALETTE["hybrid"]
            marker = "X" if poisoned else "o"
            ax.scatter(x, y, s=280, marker=marker, color=face, edgecolor=PALETTE["ink"], linewidth=0.8, zorder=3)
            if auditable:
                ax.text(
                    x,
                    y,
                    "A",
                    ha="center",
                    va="center",
                    fontsize=7.5,
                    color="white",
                    zorder=4,
                )
    tick_step = max(1, len(rows) // 8)
    tick_positions = list(range(0, len(rows), tick_step))
    if tick_positions[-1] != len(rows) - 1:
        tick_positions.append(len(rows) - 1)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([str(rows[index].probe) for index in tick_positions])
    ax.set_xlabel("Probe index (labels shown at regular intervals)")
    ax.set_yticks(list(range(len(conditions))))
    labels = []
    for label, poison_key, _audit_key, interval in conditions:
        observed = [getattr(row, poison_key) for row in rows]
        observed = [value for value in observed if value is not None]
        suffix = f"\npoison rate {sum(observed) / len(observed):.2f}" if observed else "\npoison rate unrecorded"
        if len(observed) < n:
            suffix += f"; {len(observed)}/{n} rows"
        if interval:
            suffix += f" [{float(interval[1]):.2f}, {float(interval[2]):.2f}]"
        labels.append(label + suffix)
    ax.set_yticklabels(labels)
    ax.set_xlim(-0.55, len(rows) - 0.45)
    ax.set_ylim(-0.65, len(conditions) - 0.25)
    ax.invert_yaxis()
    ax.grid(False)
    ax.set_title(
        f"Context-poisoning probe outcomes (n={n}; X = poisoned; "
        "A = cited excerpt lexically contains gold)"
    )
    ax.legend(
        handles=[
            Line2D([0], [0], marker="X", color="none", markerfacecolor=PALETTE["accent"], markeredgecolor=PALETTE["ink"], label="poisoned"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor=PALETTE["hybrid"], markeredgecolor=PALETTE["ink"], label="answer remains unpoisoned"),
            Line2D([0], [0], marker="$A$", color=PALETTE["hybrid"], markerfacecolor=PALETTE["hybrid"], markeredgecolor=PALETTE["ink"], markersize=10, label="A overlay: lexical cited-excerpt proxy"),
            Line2D([0], [0], marker="$?$", color="none", markerfacecolor="white", markeredgecolor=PALETTE["muted"], label="unrecorded"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=4,
        frameon=False,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_orchestration_value(baseline: OrchestrationBaseline, output_path: str | Path) -> Path:
    """Stacked composite decomposition: naive full-context baseline vs full pipeline.

    Each bar stacks the weighted metric components from ``src.compiler.metrics`` so
    they sum to the composite. The finite comparison records equal raw answer
    token-F1 and the support/efficiency contributions supplied by the typed
    pipeline. Data from
    :func:`src.evaluation.no_harness_baseline`.
    """
    path = _prepare(output_path)
    labels = ["Naive\n(full context to LM)", "Full pipeline\n(typed stages)"]
    acc = [ACCURACY_WEIGHT * baseline.naive_accuracy, ACCURACY_WEIGHT * baseline.pipeline_accuracy]
    grd = [GROUNDING_WEIGHT * baseline.naive_grounding, GROUNDING_WEIGHT * baseline.pipeline_grounding]
    eff = [EFFICIENCY_WEIGHT * baseline.naive_efficiency, EFFICIENCY_WEIGHT * baseline.pipeline_efficiency]

    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.bar(labels, acc, color=PALETTE["lexical"], edgecolor=PALETTE["ink"], linewidth=0.5, label=f"{ACCURACY_WEIGHT:.1f} · answer token-F1")
    ax.bar(labels, grd, bottom=acc, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label=f"{GROUNDING_WEIGHT:.1f} · citation support")
    bottom2 = [a + g for a, g in zip(acc, grd)]
    ax.bar(labels, eff, bottom=bottom2, color=PALETTE["accent"], edgecolor=PALETTE["ink"], linewidth=0.5, label=f"{EFFICIENCY_WEIGHT:.1f} · efficiency")
    for i, total in enumerate([baseline.naive_composite, baseline.pipeline_composite]):
        ax.text(i, total + 0.012, f"{total:.3f}", ha="center", va="bottom", fontsize=10, fontweight="semibold")
    raw = (
        f"answer F1 {baseline.naive_accuracy:.3f} | {baseline.pipeline_accuracy:.3f}; "
        f"support {baseline.naive_grounding:.2f} to {baseline.pipeline_grounding:.2f}; "
        f"efficiency {baseline.naive_efficiency:.2f} to {baseline.pipeline_efficiency:.2f}"
    )
    fig.text(0.5, 0.02, raw, ha="center", fontsize=8.5, color=PALETTE["muted"])
    ax.set_ylabel("Composite metric (component-stacked)")
    ax.set_title("Full-context baseline and typed pipeline")
    totals = [baseline.naive_composite, baseline.pipeline_composite]
    ax.set_ylim(0, min(1.0, max(0.2, max(totals, default=0.0) * 1.18)))
    ax.legend(loc="upper left")
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_integrity_advantage(data: IntegrityAdvantagePayload, output_path: str | Path) -> Path:
    """Render the current integrity-advantage screen without pooling constructs.

    Binary probe effects share a proportion scale. Continuous effects use a
    separate panel because composite, token-F1, and context-policy outcomes have
    different estimands. Point-only rows use open markers; interval-backed rows use
    filled markers and error bars. The bottom panel retains each binary endpoint's
    two observed rates with Wilson intervals.
    """
    path = _prepare(output_path)
    rows = {str(row["id"]): row for row in data.comparisons}
    binary_ids = ["provenance_auditability", "poisoning_rate", "learned_retrieval_recall"]
    continuous_ids = [
        "orchestration_composite",
        "adaptive_context_policy",
        "compiler_mipro_holdout",
        "local_neural_answer_f1",
    ]
    binary_rows = [rows[key] for key in binary_ids if key in rows]
    continuous_rows = [rows[key] for key in continuous_ids if key in rows]

    def _status_color(row: dict[str, Any]) -> str:
        status = str(row.get("claim_status", ""))
        if status.startswith("strongest_"):
            return PALETTE["hybrid"]
        if status.startswith("promising_"):
            return PALETTE["semantic"]
        if status.startswith("conditional_"):
            return PALETTE["accent"]
        return PALETTE["muted"]

    def _format_p(value: object) -> str:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("p-value must be numeric")
        numeric = float(value)
        if numeric < 1e-6:
            return "< 1e−6"
        if numeric < 0.001:
            return "< 0.001"
        return f"={numeric:.3f}"

    def _p_label(row: dict[str, Any]) -> str:
        raw = row.get("p_value")
        adjusted = row.get("adjusted_p_value")
        if raw is None:
            return "point only"
        raw_label = f"raw p {_format_p(raw)}"
        if adjusted is None:
            return raw_label
        return f"{raw_label}\nexploratory Holm p {_format_p(adjusted)}"

    display_labels = {
        "provenance_auditability": "Lexical cited-excerpt\nsource-exposure proxy",
        "poisoning_rate": "Poisoning rate",
        "learned_retrieval_recall": "Paraphrase recall@1",
        "orchestration_composite": "Composite: pipeline − naive",
        "adaptive_context_policy": "Adaptive context token-F1",
        "compiler_mipro_holdout": "MIPRO held-out composite",
        "local_neural_answer_f1": "Neural − extractive token-F1",
    }

    def _draw_effect_panel(ax: Any, panel_rows: list[dict[str, Any]], title: str, xlabel: str) -> None:
        ordered = list(reversed(panel_rows))
        y = list(range(len(ordered)))
        for position, row in zip(y, ordered):
            effect = float(row["advantage_delta"])
            color = _status_color(row)
            low = row.get("low")
            high = row.get("high")
            if low is not None and high is not None:
                ax.errorbar(
                    effect,
                    position,
                    xerr=[[max(0.0, effect - float(low))], [max(0.0, float(high) - effect)]],
                    fmt="o",
                    markersize=6,
                    markerfacecolor=color,
                    markeredgecolor=PALETTE["ink"],
                    ecolor=color,
                    elinewidth=1.3,
                    capsize=3,
                    zorder=3,
                )
            else:
                ax.scatter(
                    [effect],
                    [position],
                    s=58,
                    facecolor="white",
                    edgecolor=color,
                    linewidth=1.8,
                    zorder=3,
                )
            near_right_edge = effect > 0.75
            ax.annotate(
                f"{effect:+.3f} · {_p_label(row)}",
                (effect, position),
                xytext=(-7 if near_right_edge else (7 if effect >= 0 else -7), 0),
                textcoords="offset points",
                ha="right" if near_right_edge else ("left" if effect >= 0 else "right"),
                va="center",
                fontsize=7.4,
                color=PALETTE["ink"],
            )
        ax.axvline(0.0, color=PALETTE["ink"], linewidth=0.9)
        ax.set_yticks(y)
        ax.set_yticklabels([display_labels.get(str(row["id"]), str(row["label"])) for row in ordered])
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.grid(axis="y", visible=False)

    fig = plt.figure(figsize=(12.0, 8.2))
    grid = fig.add_gridspec(2, 2, height_ratios=(1.0, 1.25), hspace=0.55, wspace=0.50)
    binary_ax = fig.add_subplot(grid[0, 0])
    continuous_ax = fig.add_subplot(grid[0, 1])
    rate_ax = fig.add_subplot(grid[1, :])

    _draw_effect_panel(
        binary_ax,
        binary_rows,
        "Binary integrity endpoints",
        "Direction-normalized paired rate difference",
    )
    binary_ax.set_xlim(-0.10, 1.13)

    _draw_effect_panel(
        continuous_ax,
        continuous_rows,
        "Continuous and aggregate endpoints",
        "Direction-normalized effect on native 0–1 metric",
    )
    continuous_values = [float(row["advantage_delta"]) for row in continuous_rows]
    interval_values = [
        float(value)
        for row in continuous_rows
        for value in (row.get("low"), row.get("high"))
        if value is not None
    ]
    extent = continuous_values + interval_values + [0.0]
    span = max(max(extent) - min(extent), 0.02)
    margin = max(0.04, span * 0.18)
    continuous_ax.set_xlim(min(extent) - margin, max(extent) + margin)

    rate_rows = [row for row in binary_rows if row.get("left_rate") and row.get("right_rate")]
    ordered_rates = list(reversed(rate_rows))
    y = list(range(len(ordered_rates)))
    bar_height = 0.30
    for position, row in zip(y, ordered_rates):
        left = row["left_rate"]
        right = row["right_rate"]
        left_rate = float(left["rate"])
        right_rate = float(right["rate"])
        rate_ax.barh(position + bar_height / 2, left_rate, height=bar_height, color=PALETTE["hybrid"], label="left condition" if position == 0 else None)
        rate_ax.barh(position - bar_height / 2, right_rate, height=bar_height, color=PALETTE["muted"], label="comparator" if position == 0 else None)
        rate_ax.errorbar(
            left_rate,
            position + bar_height / 2,
            xerr=[
                [max(0.0, left_rate - float(left["low"]))],
                [max(0.0, float(left["high"]) - left_rate)],
            ],
            fmt="none",
            ecolor=PALETTE["ink"],
            capsize=3,
            linewidth=1.0,
        )
        rate_ax.errorbar(
            right_rate,
            position - bar_height / 2,
            xerr=[
                [max(0.0, right_rate - float(right["low"]))],
                [max(0.0, float(right["high"]) - right_rate)],
            ],
            fmt="none",
            ecolor=PALETTE["ink"],
            capsize=3,
            linewidth=1.0,
        )
        rate_ax.text(min(1.01, left_rate + 0.03), position + bar_height / 2, f"{left_rate:.2f}", va="center", fontsize=8)
        rate_ax.text(min(1.01, right_rate + 0.03), position - bar_height / 2, f"{right_rate:.2f}", va="center", fontsize=8)
    rate_ax.set_yticks(y)
    rate_ax.set_yticklabels(
        [display_labels.get(str(row["id"]), str(row["label"])) for row in ordered_rates]
    )
    rate_ax.set_xlim(0, 1.12)
    rate_ax.set_xlabel(f"Observed rate with {int(data.confidence * 100)}% Wilson interval")
    rate_ax.set_title("Observed rates retained beside the direction-normalized effects")
    rate_ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2)
    rate_ax.grid(axis="y", visible=False)

    fig.suptitle("Endpoint-specific integrity evidence screen", y=0.995, fontsize=15, fontweight="semibold")
    fig.text(
        0.5,
        0.015,
        "Positive effects favor the left condition after direction normalization. "
        "Open markers are point-only; filled markers carry recorded intervals. "
        "Rows retain native units and are not pooled.\n"
        "Legacy injection auditability is a lexical cited-excerpt/source-exposure proxy; "
        "Holm values are exploratory.",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color=PALETTE["muted"],
    )
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_paraphrase_retrieval(data: LearnedRetrievalPayload, output_path: str | Path) -> Path:
    """Exact counts: hashing surrogate vs real learned embedder recall@1.

    Makes the manuscript's second scope boundary measurable: a learned embedder
    supplies a distinct paraphrase-retrieval capability alongside the hashing
    surrogate. Data from
    :func:`src.retrieval.learned.paraphrase_retrieval_probe`
    (``data/learned_retrieval.json``).
    """
    path = _prepare(output_path)
    labels = ["Hashing surrogate\n(char-trigram)", f"Learned embedder\n({data.model})"]
    values = [data.surrogate_recall_at_1, data.learned_recall_at_1]
    n = data.n_probes
    counts = [round(v * n) for v in values]
    colors = [PALETTE["muted"], PALETTE["semantic"]]

    fig, ax = plt.subplots(figsize=(5.4, 4.0))
    errors = None
    if data.surrogate_recall_ci is not None and data.learned_recall_ci is not None:
        complete_intervals = [data.surrogate_recall_ci, data.learned_recall_ci]
        errors = [
            [value - float(interval[1]) for value, interval in zip(values, complete_intervals)],
            [float(interval[2]) - value for value, interval in zip(values, complete_intervals)],
        ]
    bars = ax.bar(labels, values, yerr=errors, capsize=4, color=colors, edgecolor=PALETTE["ink"], linewidth=0.6, width=0.6, error_kw={"elinewidth": 1.1})
    ax.set_ylabel(f"Recall@1 over {data.n_probes} paraphrase probes")
    ax.set_title("Paraphrase retrieval exact counts")
    ax.set_ylim(0, 1.16)
    for bar, count, value in zip(bars, counts, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{count}/{n}\n({value:.2f})",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    if data.paired_comparison:
        ax.annotate(
            f"paired Δ={float(data.paired_comparison.get('delta', values[1] - values[0])):+.2f}; "
            f"exact McNemar p={float(data.paired_comparison.get('p_value', 1.0)):.3f}",
            (0.5, 0.98),
            xycoords="axes fraction",
            ha="center",
            va="top",
            fontsize=8.5,
            color=PALETTE["ink"],
        )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_category_components(
    breakdown: dict[str, dict[str, float]],
    output_path: str | Path,
) -> Path:
    """Horizontal stacked bar chart: weighted component breakdown per task category.

    Each row is one :class:`~src.signatures.TaskCategory`.  The three stacked
    segments show the weighted contribution to the composite:

    * answer token-F1 (blue / lexical)
    * citation-support proxy (green / hybrid)
    * efficiency (pink / accent)

    so the total bar length equals the per-category composite metric.

    Args:
        breakdown: Dict mapping category name to ``{"accuracy", "grounding",
            "efficiency"}`` (e.g. from :func:`~src.evaluation.category_component_breakdown`).
        output_path: Destination path for the 300-dpi PNG.

    Returns:
        The resolved output :class:`~pathlib.Path`.
    """
    path = _prepare(output_path)
    # Sort ascending by composite so the weakest categories sit at the top of
    # a horizontal bar chart (reading order: weakest top, strongest bottom).
    items = sorted(
        breakdown.items(),
        key=lambda kv: (
            ACCURACY_WEIGHT * kv[1]["accuracy"]
            + GROUNDING_WEIGHT * kv[1]["grounding"]
            + EFFICIENCY_WEIGHT * kv[1]["efficiency"]
        ),
    )
    labels = [_pretty(cat) for cat, _ in items]
    acc_w = [ACCURACY_WEIGHT * v["accuracy"] for _, v in items]
    grd_w = [GROUNDING_WEIGHT * v["grounding"] for _, v in items]
    eff_w = [EFFICIENCY_WEIGHT * v["efficiency"] for _, v in items]
    y = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.barh(y, acc_w, color=PALETTE["lexical"], edgecolor=PALETTE["ink"], linewidth=0.5, label=f"{ACCURACY_WEIGHT:.1f} · answer token-F1")
    ax.barh(y, grd_w, left=acc_w, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label=f"{GROUNDING_WEIGHT:.1f} · citation support")
    left2 = [a + g for a, g in zip(acc_w, grd_w)]
    ax.barh(y, eff_w, left=left2, color=PALETTE["accent"], edgecolor=PALETTE["ink"], linewidth=0.5, label=f"{EFFICIENCY_WEIGHT:.1f} · efficiency")

    # Annotate total composite at the end of each bar
    for i, (aw, gw, ew) in enumerate(zip(acc_w, grd_w, eff_w)):
        total = aw + gw + ew
        ax.text(total + 0.005, i, f"{total:.3f}", va="center", fontsize=8.5)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Weighted component contribution (sums to composite)")
    ax.set_title("Per-category component breakdown")
    ax.legend(loc="lower right")
    ax.grid(axis="x")
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_metric_construct_audit(audit: dict[str, object], output_path: str | Path) -> Path:
    """Heatmap the declared proxy and adjacent citation diagnostics.

    The panel makes construct separation inspectable: the blended support proxy
    shares a scale with its source-index precision/recall decomposition and the
    separate exposure and efficiency diagnostics. Values are finite demo means,
    so the plot carries no sampling interval.
    """
    path = _prepare(output_path)
    raw_names = audit.get("metric_names")
    raw_by_category = audit.get("by_category")
    n_examples = audit.get("n_examples")
    if not isinstance(raw_names, list) or not raw_names or not all(isinstance(name, str) for name in raw_names):
        raise ValueError("metric construct audit requires a non-empty metric_names list")
    if not isinstance(raw_by_category, dict) or not raw_by_category:
        raise ValueError("metric construct audit requires by_category data")
    names = [str(name) for name in raw_names]
    category_rows = {str(category): row for category, row in raw_by_category.items()}
    categories = sorted(category_rows)
    matrix: list[list[float]] = []
    for category in categories:
        row = category_rows[category]
        if not isinstance(row, dict):
            raise ValueError("metric construct audit category rows must be mappings")
        try:
            values = [float(row[name]) for name in names]
        except KeyError as exc:
            raise ValueError(f"metric construct audit row is missing {exc.args[0]!r}") from exc
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("metric construct audit values must be in [0, 1]")
        matrix.append(values)

    fig, ax = plt.subplots(figsize=(8.0, 4.3))
    image = ax.imshow(matrix, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
    display_names = {
        "answer_token_f1": "answer\nF1",
        "citation_support_proxy": "support\nproxy",
        "citation_precision": "citation\nprecision",
        "source_recall": "source\nrecall",
        "session_reachability": "session\nreachability",
        "evidence_efficiency": "evidence\nefficiency",
    }
    ax.set_xticks(range(len(names)), [display_names.get(name, name.replace("_", " ")) for name in names])
    ax.set_yticks(range(len(categories)), [_pretty(category) for category in categories])
    ax.set_xlabel("Declared diagnostic construct")
    ax.set_ylabel("Task category")
    title_n = n_examples if isinstance(n_examples, int) and not isinstance(n_examples, bool) else "finite demo"
    ax.set_title(f"Metric construct audit across task categories (n={title_n})")
    for row_index, values in enumerate(matrix):
        for column_index, value in enumerate(values):
            ax.text(
                column_index,
                row_index,
                f"{value:.2f}",
                ha="center",
                va="center",
                color="white" if value < 0.58 else PALETTE["ink"],
                fontsize=9,
            )
    colorbar = fig.colorbar(image, ax=ax, pad=0.02, fraction=0.04)
    colorbar.set_label("Mean diagnostic score (0–1)")
    ax.text(
        0.0,
        -0.28,
        "Source-index diagnostics expose the support proxy's components; entailment remains unmeasured.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color=PALETTE["muted"],
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_gepa_trajectory(
    trajectory: list[dict],
    output_path: str | Path,
) -> Path:
    """Multi-line component trajectory from a GEPA evolution run.

    Plots the per-component scores (answer token-F1, citation support, efficiency) at each
    GEPA iteration, plus markers indicating which component was the weakest
    (and therefore targeted by the optimizer) at each step.

    Args:
        trajectory: List of dicts from :func:`~src.evaluation.gepa_component_trajectory`,
            each with keys ``iteration``, ``composite``, ``accuracy``,
            ``grounding``, ``efficiency``, ``weakest_component``.
        output_path: Destination PNG path (parent dir created if needed).

    Returns:
        The output :class:`~pathlib.Path`.
    """
    path = _prepare(output_path)
    iterations = [r["iteration"] for r in trajectory]
    accuracy = [r["accuracy"] for r in trajectory]
    grounding = [r["grounding"] for r in trajectory]
    efficiency = [r["efficiency"] for r in trajectory]
    composite = [r["composite"] for r in trajectory]

    # Color mapping: lexical for answer token-F1, hybrid for citation support, accent for efficiency
    component_color = {
        "accuracy": PALETTE["lexical"],
        "grounding": PALETTE["hybrid"],
        "efficiency": PALETTE["accent"],
    }

    fig, ax = plt.subplots()
    ax.plot(iterations, accuracy, marker="o", color=PALETTE["lexical"], linewidth=1.8,
            label="answer token-F1", zorder=2)
    ax.plot(iterations, grounding, marker="s", color=PALETTE["hybrid"], linewidth=1.8,
            label="citation support", zorder=2)
    ax.plot(iterations, efficiency, marker="^", color=PALETTE["accent"], linewidth=1.8,
            label="efficiency", zorder=2)
    ax.plot(iterations, composite, color=PALETTE["muted"], linewidth=1.2,
            linestyle=(0, (4, 3)), label="composite", zorder=1)

    # Mark the weakest component at each step with a larger halo marker
    for record in trajectory:
        it = record["iteration"]
        weakest = record["weakest_component"]
        component_values = {
            "accuracy": record["accuracy"],
            "grounding": record["grounding"],
            "efficiency": record["efficiency"],
        }
        val = component_values[weakest]
        ax.scatter(
            [it], [val],
            s=120,
            facecolor="none",
            edgecolor=component_color[weakest],
            linewidth=2.0,
            zorder=4,
        )
        # Small text annotation above the halo
        ax.annotate(
            weakest[0].upper(),  # first letter: A / G / E
            (it, val),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=7,
            color=component_color[weakest],
        )

    ax.set_xlabel("GEPA iteration")
    ax.set_ylabel("Component score (0–1)")
    ax.set_title("GEPA component trajectory and mutation targets")
    ax.set_ylim(0, 1)
    ax.set_xticks(iterations)
    ax.legend(loc="lower right", fontsize=8)
    ax.text(
        0.02,
        0.98,
        "open halo + letter = weakest component",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color=PALETTE["muted"],
    )
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path
