"""Figure generators for the THALIA manuscript (matplotlib, headless).

Thin, deterministic plotting helpers driven by :mod:`src.evaluation`. Each
function takes computed data plus an output path, writes a 300-dpi PNG, and
returns the path. No business logic lives here — the numbers come from the
evaluation module so figures and prose share a single source of truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evaluation import (
    RetrieverComparison,
    category_component_breakdown,
    consolidation_simulation,
    evidence_funnel,
    gepa_component_trajectory,
    method_ablation,
    mmr_lambda_sweep,
    noise_scaling_experiment,
    pipeline_evidence_flow,
    rrf_weight_sweep,
)
from .figure_style import EXPORT_DPI, PALETTE, annotate_bars as _annotate_bars
from .figure_style import plt, prepare as _prepare, pretty as _pretty, zoomed_ylim as _zoomed_ylim



def plot_retriever_comparison(comparison: RetrieverComparison, output_path: str | Path) -> Path:
    """Bar chart of lexical vs. semantic vs. hybrid composite metric."""
    path = _prepare(output_path)
    labels = ["Lexical\n(BM25/grep)", "Semantic\n(hashing)", "Hybrid\n(RRF)"]
    values = [comparison.lexical, comparison.semantic, comparison.hybrid]
    colors = [PALETTE["lexical"], PALETTE["semantic"], PALETTE["hybrid"]]

    fig, ax = plt.subplots()
    bars = ax.bar(labels, values, color=colors, edgecolor=PALETTE["ink"], linewidth=0.6)
    ax.set_ylabel("Composite metric (0–1)")
    ax.set_title("Retrieval mode comparison (slack budget, inline delivery)")
    ax.set_ylim(0, 1)
    _annotate_bars(ax, bars, values, dy=0.02)
    # On the clean set at a slack budget all three lanes tie; say so on the figure so
    # the identical bars read as the (real) finding, not a broken render.
    if max(values) - min(values) < 1e-9:
        ax.annotate(
            "all lanes tie — gold evidence is unambiguous at a slack budget\n(see noise-scaling figure for where they diverge)",
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
    # Draw the optimum on top with a halo so it is visible even where it sits under
    # the line; annotate the non-monotonic midpoint dip the caption refers to.
    ax.scatter([best_w], [best_s], s=90, facecolor=PALETTE["accent"], edgecolor="white", linewidth=1.4, zorder=5, label=f"optimum @ w_lex={best_w:.2f}")
    dip_i = min(range(len(scores)), key=lambda i: scores[i])
    if 0 < dip_i < len(scores) - 1:
        ax.annotate(
            "balanced fusion:\nneither lane dominates",
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
    ax.set_title("RRF lane-weight sensitivity")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_compiler_convergence(trace: list[tuple[object, float]], output_path: str | Path, components: dict | None = None) -> Path:
    """Compiler search trace, with the component decomposition that explains the tie.

    The composite-vs-candidate curve is flat on the easy dataset; rather than leave a
    bare flat line, the inset bars show the three weighted metric components are each
    pinned (accuracy/grounding/efficiency constant across candidates), so the flatness
    is a *proven* structural tie, not a rendering accident. ``components`` is a
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
    ax.set_title("Compiler search: a structural tie, decomposed")
    ax.set_ylim(0, 1)
    if tied:
        ax.annotate(
            f"all {len(scores)} candidates tie at {scores[0]:.3f}\n(optimum is a tie-break, not a win)",
            (x[len(x) // 2], scores[0]),
            textcoords="offset points", xytext=(0, 20), ha="center", fontsize=8, color=PALETTE["muted"],
        )
    # Inset: the weighted components that sum to the (constant) composite — proving the tie.
    if components:
        labels = ["0.6·acc", "0.3·grnd", "0.1·eff"]
        vals = [0.6 * components["accuracy"], 0.3 * components["grounding"], 0.1 * components["efficiency"]]
        colors = [PALETTE["lexical"], PALETTE["hybrid"], PALETTE["accent"]]
        inset = ax.inset_axes([0.6, 0.1, 0.36, 0.42])
        pos = list(range(len(labels)))
        bars = inset.bar(pos, vals, color=colors, edgecolor=PALETTE["ink"], linewidth=0.4)
        for bar, v in zip(bars, vals):
            inset.text(bar.get_x() + bar.get_width() / 2, v + 0.006, f"{v:.2f}", ha="center", va="bottom", fontsize=7)
        inset.set_xticks(pos)
        inset.set_xticklabels(labels, fontsize=7)
        inset.set_ylim(0, max(vals) * 1.35)
        inset.set_title("weighted components\n(constant across candidates)", fontsize=7.5)
        inset.tick_params(axis="y", labelsize=6)
        inset.set_yticks([])
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_consolidation_curve(output_path: str | Path, turns: int = 12) -> Path:
    """Schematic utility curves: forced consolidation vs. episodic-first.

    Illustrative (not empirical) — communicates the consolidation-fault mechanism
    from Zhang et al. (2026).
    """
    path = _prepare(output_path)
    sim = consolidation_simulation(turns=turns)
    x = list(range(1, turns + 1))

    fig, ax = plt.subplots()
    ax.plot(x, sim["forced"], marker="s", color=PALETTE["accent"], label="forced consolidation")
    ax.plot(x, sim["episodic_first"], marker="o", color=PALETTE["hybrid"], label="episodic-first (gated)")
    ax.axhline(0.5, color=PALETTE["muted"], linestyle="--", linewidth=1.0, label="no-memory baseline")
    ax.set_xlabel("Turn")
    ax.set_ylabel("Memory utility (schematic)")
    ax.set_title("Consolidation regimes (conceptual schematic)")
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
    # Colour the two weakest categories distinctly so the bimodal spread (the weak
    # code/multi-session classes vs the strong rest) reads at a glance.
    colors = [PALETTE["accent"] if i < 2 else PALETTE["hybrid"] for i in range(len(values))]

    fig, ax = plt.subplots()
    ax.barh(labels, values, color=colors, edgecolor=PALETTE["ink"], linewidth=0.6)
    ax.set_xlabel("Composite metric (0–1)")
    ax.set_title("Per-task-category performance")
    ax.set_xlim(0, 1)
    ax.grid(axis="x")
    for i, value in enumerate(values):
        ax.text(value + 0.01, i, f"{value:.3f}", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_evidence_funnel(output_path: str | Path) -> Path:
    """Funnel of mean evidence counts: session lines -> windows -> ranked -> cited."""
    path = _prepare(output_path)
    funnel = evidence_funnel()
    stages = ["session\nlines", "inspector\nwindows", "ranked\nevidence", "cited\nsources"]
    values = [funnel["session_lines"], funnel["windows"], funnel["ranked"], funnel["cited"]]
    colors = [PALETTE["muted"], PALETTE["lexical"], PALETTE["hybrid"], PALETTE["accent"]]

    fig, ax = plt.subplots()
    bars = ax.bar(stages, values, color=colors, edgecolor="black", linewidth=0.6)
    ax.set_ylabel("Mean count per query")
    ax.set_title("Evidence narrowing funnel")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.05, f"{value:.1f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_pipeline_flow(
    flow_data: list[dict],
    output_path: str | Path,
) -> Path:
    """Grouped bar chart of per-example evidence counts at each Pipeline stage.

    Shows how evidence narrows from Inspector windows → Retriever ranked →
    Reasoner citations for every demo example.  Three bars per group:

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
    # Label each group by its task category (one demo example per category) rather
    # than a truncated query string — informative, untruncated, and consistent with
    # the category framing used throughout the evaluation.
    labels = [_pretty(str(row.get("task_category", row.get("query", "")))).replace("_", " ") for row in flow_data]

    fig, ax = plt.subplots(figsize=(max(6.2, n * 1.4), 4.4))
    ax.bar([xi - width for xi in x], windows, width=width, color=PALETTE["lexical"], edgecolor=PALETTE["ink"], linewidth=0.5, label="inspector windows")
    ax.bar(x, ranked, width=width, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label="retriever ranked")
    ax.bar([xi + width for xi in x], cited, width=width, color=PALETTE["accent"], edgecolor=PALETTE["ink"], linewidth=0.5, label="reasoner cited")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Evidence count per example")
    ax.set_title("Per-example evidence narrowing across pipeline stages")
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
    # The hybrid lane tracks the lexical lane exactly on this dataset (the default
    # RRF weights let the lexical signal dominate the weak sub-word semantic
    # surrogate), so a solid hybrid line would render invisibly under lexical. Give
    # each lane a distinct style/marker and dodge the end-of-line value labels so
    # the overlap is legible rather than hidden.
    style = {
        "lexical": dict(linestyle="-", marker="o", linewidth=1.8, zorder=2),
        "semantic": dict(linestyle="-", marker="s", linewidth=1.8, zorder=2),
        "hybrid": dict(linestyle="--", marker="x", linewidth=1.8, zorder=3),
    }
    label_dy = {"lexical": -11, "semantic": 4, "hybrid": 7}
    for mode in ("lexical", "semantic", "hybrid"):
        levels = [lvl for lvl, _ in experiment[mode]]
        scores = [s for _, s in experiment[mode]]
        ax.plot(levels, scores, color=PALETTE[mode], label=mode, **style[mode])
        # Label each lane's value at the noisiest level so the lexical-vs-surrogate
        # divergence (semantic > lexical under noise) is readable on the figure
        # itself, matching the value-annotation style of the bar charts. Vertical
        # offsets keep overlapping lanes' labels from colliding.
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
    ax.set_title("Robustness to session noise by lane")
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
    ax.set_title("MMR relevance/diversity tradeoff")
    # The single real finding is the penalty at λ=0 (pure diversity evicts the
    # discriminative span); on a 0–1 axis it is invisible, so zoom and call it out.
    if len(scores) > 1 and scores[0] < scores[1]:
        ax.annotate(
            f"pure diversity evicts gold span\n(-{scores[1] - scores[0]:.3f})",
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
    ax.set_title("Added-method ablation (single-turn dataset, tight budget)")
    ax.set_ylim(lo, hi)
    _annotate_bars(ax, bars, values, dy=(hi - lo) * 0.01)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_backend_comparison(data: dict, output_path: str | Path) -> Path:
    """Per-example extractive vs real neural Reasoner token-F1.

    The comparison has only six examples, so paired points are more honest than
    grouped category bars. Data comes from ``data/neural_eval.json``.
    """
    path = _prepare(output_path)
    rows = data.get("rows") or [
        {"category": c, "extractive_f1": data["category_extractive_f1"][c], "neural_f1": data["category_neural_f1"][c]}
        for c in sorted(data["category_neural_f1"])
    ]
    rows = sorted(rows, key=lambda r: (r["neural_f1"] - r["extractive_f1"], str(r["category"])))
    labels = [_pretty(str(r["category"])) for r in rows]
    ext = [float(r["extractive_f1"]) for r in rows]
    neu = [float(r["neural_f1"]) for r in rows]
    x = list(range(len(rows)))

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for i, (e, n) in enumerate(zip(ext, neu)):
        ax.plot([i, i], [e, n], color="#BBBBBB", linewidth=1.2, zorder=1)
    ax.scatter(x, ext, color=PALETTE["muted"], edgecolor=PALETTE["ink"], linewidth=0.5, s=48, label="extractive")
    ax.scatter(x, neu, color=PALETTE["semantic"], edgecolor=PALETTE["ink"], linewidth=0.5, s=56, marker="s", label=f"neural ({data['model']})")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("Token-F1 vs gold answer")
    ax.set_ylim(0, 1)
    ax.set_title(f"Backend comparison by example (n={data['n']})")
    me, mn = data["mean_extractive_f1"], data["mean_neural_f1"]
    ax.axhline(me, color=PALETTE["muted"], linestyle=":", linewidth=1.0, zorder=0)
    ax.axhline(mn, color=PALETTE["semantic"], linestyle=":", linewidth=1.0, zorder=0)
    ax.annotate(
        f"mean token-F1: extractive {me:.3f} -> neural {mn:.3f}",
        (0.02, 0.95),
        xycoords="axes fraction",
        ha="left",
        va="top",
        fontsize=9,
        color=PALETTE["ink"],
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#DDDDDD", alpha=0.9),
    )
    ax.grid(axis="y")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_bottleneck(data: dict, output_path: str | Path) -> Path:
    """The Inspector is the bottleneck, and widening it is the fix (real LongMemEval).

    Extractive grounding and neural accuracy both climb as ``max_windows`` relaxes the
    Inspector's narrowing; the subtitle reports the localisation (full-haystack ranking
    recall vs Inspector recall). Data from
    :func:`src.evaluation.longmemeval.bottleneck_analysis`.
    """
    path = _prepare(output_path)
    sweep = data["extractive_grounding_by_maxwindows"]
    mws = sorted(int(k) for k in sweep)
    grounding = [sweep[str(k)] if str(k) in sweep else sweep[k] for k in mws]
    neural = data["neural_by_maxwindows"]

    def _n(mw, field):
        d = neural.get(str(mw), neural.get(mw, {}))
        return d.get(field)

    nmws = sorted(int(k) for k in neural)
    neural_acc = [_n(mw, "accuracy") for mw in nmws]

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(mws, grounding, marker="o", color=PALETTE["hybrid"], linewidth=1.8, label="extractive grounding")
    ax.plot(nmws, neural_acc, marker="s", color=PALETTE["semantic"], linewidth=1.8, label=f"neural accuracy ({data['neural_model']})")
    if len(neural_acc) == 2:
        ax.annotate(f"+{neural_acc[1] - neural_acc[0]:.3f} accuracy", (nmws[1], neural_acc[1]), textcoords="offset points", xytext=(-6, 10), fontsize=9, color=PALETTE["semantic"], ha="right")
    # The shipped fix: the adaptive Inspector reaches the manual best with no tuning.
    adaptive = data.get("neural_adaptive")
    if adaptive:
        ax.axhline(adaptive["accuracy"], color=PALETTE["accent"], linestyle=":", linewidth=1.4, zorder=1)
        ax.scatter([mws[-1]], [adaptive["accuracy"]], marker="*", s=200, color=PALETTE["accent"], edgecolor="white", linewidth=0.8, zorder=6, label=f"adaptive Inspector (auto-tuned): {adaptive['accuracy']:.3f}")
    ax.set_xlabel("Inspector max_windows (context-narrowing budget)")
    ax.set_ylabel("Rate")
    ax.set_ylim(0, max(max(grounding), max(v for v in neural_acc if v is not None)) + 0.12)
    ax.set_title("Widening the Inspector recovers grounding and accuracy")
    mode = data.get("ranking_recall_by_mode") or {}
    if mode.get("available"):
        mode_text = (
            f"lex {mode['lexical']:.2f} / dense {mode['dense']:.2f} / hybrid {mode['hybrid']:.2f}"
            f" (n={mode['n']}, k={mode.get('k', 10)})"
        )
    else:
        mode_text = "dense/hybrid mode rows unavailable"
    ax.text(
        0.03,
        0.47,
        f"localisation (n={data['n_ranking']}):\nfull ranking {data['ranking_recall_at_10']:.2f} vs Inspector {data['inspector_recall']:.2f}\n{mode_text}\nneural sweep n={data.get('n_neural', 'NA')}",
        transform=ax.transAxes,
        ha="left",
        va="center",
        fontsize=8,
        color=PALETTE["muted"],
    )
    ax.grid(True)
    ax.legend(loc="center right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_longmemeval(data: dict, output_path: str | Path) -> Path:
    """Real LongMemEval_S: extractive vs neural accuracy + session grounding, with CIs.

    The headline real-data result: accuracy collapses versus the synthetic set, the
    neural advantage becomes statistically real (CIs barely overlap), and session
    grounding caps both — retrieval is the bottleneck on real long-context data. Data
    from :func:`src.evaluation.longmemeval.longmemeval_eval` (committed aggregates).
    """
    path = _prepare(output_path)
    backends = ["Extractive", f"Neural\n({data['neural_model']})"]
    acc = [data["extractive_accuracy"], data["neural_accuracy"]]
    grnd = [data["extractive_grounding"], data["neural_grounding"]]
    x = range(len(backends))
    w = 0.38

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    am = [t[0] for t in acc]
    ae = [[t[0] - t[1] for t in acc], [t[2] - t[0] for t in acc]]
    gm = [t[0] for t in grnd]
    ge = [[t[0] - t[1] for t in grnd], [t[2] - t[0] for t in grnd]]
    ax.bar([i - w / 2 for i in x], am, width=w, yerr=ae, capsize=4, color=PALETTE["semantic"], edgecolor=PALETTE["ink"], linewidth=0.5, label="answer accuracy", error_kw={"elinewidth": 1.1})
    ax.bar([i + w / 2 for i in x], gm, width=w, yerr=ge, capsize=4, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label="session grounding", error_kw={"elinewidth": 1.1})
    for i, t in zip([i - w / 2 for i in x], acc):
        ax.text(i, t[2] + 0.015, f"{t[0]:.3f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(backends)
    ax.set_ylim(0, max(0.55, max(gm) + 0.12))
    ax.set_ylabel("Rate (95% bootstrap CI)")
    ax.set_title(f"Real benchmark: LongMemEval_S (n={data['n_extractive']} ext, {data['n_neural']} neural)")
    ax.annotate(
        "grounding is session-level upper bound",
        (0.5, -0.18),
        xycoords="axes fraction",
        ha="center",
        fontsize=8.5,
        color=PALETTE["muted"],
    )
    ax.grid(axis="y")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_scaling_ci(data: dict, output_path: str | Path) -> Path:
    """Per-category accuracy with 95% bootstrap CIs on the seeded large dataset.

    The first figure in the paper with real error bars: the demo set is n=6 point
    estimates, this is n per category with dispersion. Data from
    :func:`src.evaluation.large_dataset_eval`.
    """
    path = _prepare(output_path)
    items = sorted(data["category_accuracy"].items(), key=lambda kv: kv[1][0])
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
    ax.set_xlabel("Token-F1 accuracy (95% bootstrap CI)")
    ax.set_title(f"Per-category accuracy at scale (n={data['n']}, {data['per_category']}/category)")
    overall_accuracy = sum(means) / len(means)
    ax.axvline(overall_accuracy, color=PALETTE["accent"], linestyle="--", linewidth=1.0, zorder=1, label=f"mean accuracy {overall_accuracy:.3f}")
    ax.grid(axis="x")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_injection_resistance(data: dict, output_path: str | Path) -> Path:
    """Context-poisoning exact-case grid over a small probe set."""
    path = _prepare(output_path)
    rows = data.get("rows") or []
    n = int(data["n_probes"])
    if not rows:
        rows = [
            {
                "probe": i + 1,
                "harness_poisoned": i < round(data["harness_poison_rate"] * n),
                "harness_auditable": i < round(data["harness_audit_rate"] * n),
                "naive_poisoned": i < round(data["naive_poison_rate"] * n),
                "naive_auditable": False,
            }
            for i in range(n)
        ]
    conditions = [
        ("Harness", "harness_poisoned", "harness_auditable"),
        ("Naive", "naive_poisoned", "naive_auditable"),
    ]
    if data.get("neural_poison_rate") is not None:
        neural_rows = {r["probe"]: r for r in data.get("neural_rows", [])}
        for row in rows:
            nr = neural_rows.get(row["probe"], {})
            row["neural_poisoned"] = bool(nr.get("neural_poisoned", False))
            row["neural_auditable"] = bool(nr.get("neural_auditable", False))
        conditions.append((f"Neural\n({data['neural_model']})", "neural_poisoned", "neural_auditable"))

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for y, (_label, poison_key, audit_key) in enumerate(conditions):
        for x, row in enumerate(rows):
            poisoned = bool(row.get(poison_key))
            auditable = bool(row.get(audit_key))
            face = PALETTE["accent"] if poisoned else PALETTE["hybrid"]
            marker = "X" if poisoned else "o"
            ax.scatter(x, y, s=280, marker=marker, color=face, edgecolor=PALETTE["ink"], linewidth=0.8, zorder=3)
            ax.text(
                x,
                y,
                "A" if auditable else "no cite",
                ha="center",
                va="center",
                fontsize=7.5,
                color="white" if auditable else PALETTE["ink"],
                zorder=4,
            )
    ax.set_xticks(list(range(len(rows))))
    ax.set_xticklabels([f"Probe {r['probe']}" for r in rows])
    ax.set_yticks(list(range(len(conditions))))
    ax.set_yticklabels([c[0] for c in conditions])
    ax.set_xlim(-0.55, len(rows) - 0.45)
    ax.set_ylim(-0.6, len(conditions) - 0.4)
    ax.invert_yaxis()
    ax.grid(False)
    ax.set_title(f"Context-poisoning exact cases (n={n}; X = poisoned, A = true source cited)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_orchestration_value(baseline: dict, output_path: str | Path) -> Path:
    """Stacked composite decomposition: naive full-context baseline vs full pipeline.

    Each bar stacks the weighted metric components (0.6·accuracy, 0.3·grounding,
    0.1·efficiency) so they sum to the composite. Shows that the orchestration's lift
    is entirely grounding + efficiency — raw accuracy ties. Data from
    :func:`src.evaluation.no_harness_baseline`.
    """
    path = _prepare(output_path)
    labels = ["Naive\n(full context to LM)", "Full pipeline\n(5 stages)"]
    acc = [0.6 * baseline["naive_accuracy"], 0.6 * baseline["pipeline_accuracy"]]
    grd = [0.3 * baseline["naive_grounding"], 0.3 * baseline["pipeline_grounding"]]
    eff = [0.1 * baseline["naive_efficiency"], 0.1 * baseline["pipeline_efficiency"]]

    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    b1 = ax.bar(labels, acc, color=PALETTE["lexical"], edgecolor=PALETTE["ink"], linewidth=0.5, label="0.6 · accuracy")
    b2 = ax.bar(labels, grd, bottom=acc, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label="0.3 · grounding")
    bottom2 = [a + g for a, g in zip(acc, grd)]
    ax.bar(labels, eff, bottom=bottom2, color=PALETTE["accent"], edgecolor=PALETTE["ink"], linewidth=0.5, label="0.1 · efficiency")
    for i, total in enumerate([baseline["naive_composite"], baseline["pipeline_composite"]]):
        ax.text(i, total + 0.012, f"{total:.3f}", ha="center", va="bottom", fontsize=10, fontweight="semibold")
    raw = (
        f"raw acc {baseline['naive_accuracy']:.3f} = {baseline['pipeline_accuracy']:.3f}; "
        f"grounding {baseline['naive_grounding']:.2f} -> {baseline['pipeline_grounding']:.2f}; "
        f"eff {baseline['naive_efficiency']:.2f} -> {baseline['pipeline_efficiency']:.2f}"
    )
    ax.annotate(raw, (0.5, -0.18), xycoords="axes fraction", ha="center", fontsize=8.5, color=PALETTE["muted"])
    ax.set_ylabel("Composite metric (component-stacked)")
    ax.set_title("Where the orchestration adds value")
    ax.set_ylim(0, 0.72)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_paraphrase_retrieval(data: dict, output_path: str | Path) -> Path:
    """Exact counts: hashing surrogate vs real learned embedder recall@1.

    Makes the manuscript's second scope boundary measurable: a learned embedder
    captures paraphrase meaning the sub-word surrogate structurally cannot. Data from
    :func:`src.retrieval.learned.paraphrase_retrieval_probe`
    (``data/learned_retrieval.json``).
    """
    path = _prepare(output_path)
    labels = ["Hashing surrogate\n(char-trigram)", f"Learned embedder\n({data['model']})"]
    values = [data["surrogate_recall_at_1"], data["learned_recall_at_1"]]
    n = int(data["n_probes"])
    counts = [round(v * n) for v in values]
    colors = [PALETTE["muted"], PALETTE["semantic"]]

    fig, ax = plt.subplots(figsize=(5.4, 4.0))
    bars = ax.bar(labels, values, color=colors, edgecolor=PALETTE["ink"], linewidth=0.6, width=0.6)
    ax.set_ylabel(f"Recall@1 over {data['n_probes']} paraphrase probes")
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

    * **0.6 · accuracy** (blue / lexical)
    * **0.3 · grounding** (green / hybrid)
    * **0.1 · efficiency** (pink / accent)

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
            0.6 * kv[1]["accuracy"] + 0.3 * kv[1]["grounding"] + 0.1 * kv[1]["efficiency"]
        ),
    )
    labels = [_pretty(cat) for cat, _ in items]
    acc_w = [0.6 * v["accuracy"] for _, v in items]
    grd_w = [0.3 * v["grounding"] for _, v in items]
    eff_w = [0.1 * v["efficiency"] for _, v in items]
    y = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    b1 = ax.barh(y, acc_w, color=PALETTE["lexical"], edgecolor=PALETTE["ink"], linewidth=0.5, label="0.6 · accuracy")
    b2 = ax.barh(y, grd_w, left=acc_w, color=PALETTE["hybrid"], edgecolor=PALETTE["ink"], linewidth=0.5, label="0.3 · grounding")
    left2 = [a + g for a, g in zip(acc_w, grd_w)]
    ax.barh(y, eff_w, left=left2, color=PALETTE["accent"], edgecolor=PALETTE["ink"], linewidth=0.5, label="0.1 · efficiency")

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


def plot_gepa_trajectory(
    trajectory: list[dict],
    output_path: str | Path,
) -> Path:
    """Multi-line component trajectory from a GEPA evolution run.

    Plots the per-component scores (accuracy, grounding, efficiency) at each
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

    # Color mapping: lexical for accuracy, hybrid for grounding, accent for efficiency
    component_color = {
        "accuracy": PALETTE["lexical"],
        "grounding": PALETTE["hybrid"],
        "efficiency": PALETTE["accent"],
    }

    fig, ax = plt.subplots()
    ax.plot(iterations, accuracy, marker="o", color=PALETTE["lexical"], linewidth=1.8,
            label="accuracy", zorder=2)
    ax.plot(iterations, grounding, marker="s", color=PALETTE["hybrid"], linewidth=1.8,
            label="grounding", zorder=2)
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
    ax.set_title("GEPA component trajectory (weakest-targeted mutations)")
    ax.set_ylim(0, 1)
    ax.set_xticks(iterations)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Early-section architectural figures (intro, foundations, harness design)
# ---------------------------------------------------------------------------


def _box(ax, x, y, w, h, text, color="#0072B2", edge="#222222", alpha=0.9, fontsize=9, bold=False):
    """Draw a labelled rounded box with optional bold."""
    from matplotlib.patches import FancyBboxPatch
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08", facecolor=color, edgecolor=edge, linewidth=1.2, alpha=alpha, zorder=3)
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, fontweight=weight, color="white", zorder=4)


def _arrow(ax, x1, y1, x2, y2, color="#444444", lw=1.8, style="-", head=0.12):
    """Draw an arrow between two points."""
    dx, dy = x2 - x1, y2 - y1
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=f"->,head_length={head},head_width={head}", color=color, lw=lw, linestyle=style))


_STAGES = [
    ("Inspector", 0, PALETTE["lexical"]),
    ("Retriever", 1, PALETTE["hybrid"]),
    ("Reasoner",  2, PALETTE["semantic"]),
    ("Memory Gate", 3, PALETTE["accent"]),
]

_STAGE_COLORS = {name: color for name, _, color in _STAGES}


def plot_thalia_overview(output_path: str | Path) -> Path:
    """Graphical abstract / cover figure: 5-stage pipeline as a labelled loop."""
    path = _prepare(output_path)
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    ax.text(5, 3.65, "THALIA Pipeline Overview", ha="center", va="top",
            fontsize=18, fontweight="bold", color=PALETTE["ink"])

    xs = [0.8, 3.0, 5.2, 7.4]
    bw, bh = 1.6, 0.9
    for i, (name, idx, color) in enumerate(_STAGES):
        _box(ax, xs[i], 2.3, bw, bh, f"Stage {idx}\n{name}", color=color)

    for i in range(len(xs) - 1):
        _arrow(ax, xs[i] + bw, 2.75, xs[i + 1], 2.75)

    _arrow(ax, 0.0, 2.75, xs[0], 2.75, head=0.15)
    ax.text(0.0, 3.15, "Query +\nHistory", ha="center", va="bottom", fontsize=8, fontstyle="italic", color=PALETTE["muted"])

    _arrow(ax, xs[-1] + bw, 2.75, 9.8, 2.75, head=0.15)
    ax.text(9.8, 3.15, "Answer +\nCitations", ha="center", va="bottom", fontsize=8, fontstyle="italic", color=PALETTE["muted"])

    compiler_y = 0.6
    _arrow(ax, xs[-1] + bw / 2, compiler_y, xs[-1] + bw / 2, 2.3, style="--", head=0.08)
    _arrow(ax, xs[-1] + bw / 2, compiler_y, xs[0] + bw / 2, compiler_y, style="--", head=0.1)
    _arrow(ax, xs[0] + bw / 2, compiler_y, xs[0] + bw / 2, 2.3, style="--", head=0.08)
    _box(ax, 3.6, compiler_y - 0.55, 2.8, 0.7, "Stage 4: Compiler\n(MIPRO search / GEPA evolution)", color=PALETTE["muted"], alpha=0.85)
    ax.text(5.0, compiler_y - 0.15, "offline optimization loop", ha="center", va="center", fontsize=7, fontstyle="italic", color="white", fontweight="bold")

    ax.text(0.2, 0.05, "THALIA: Typed Harness with Analytical Lexical-Integrated Architecture",
            ha="left", va="bottom", fontsize=7, color=PALETTE["muted"], fontstyle="italic")
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_foundations_map(output_path: str | Path) -> Path:
    """2x2 grid mapping the four foundation works to THALIA stages."""
    path = _prepare(output_path)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")

    ax.text(5, 4.85, "Foundations to THALIA Stage Map",
            ha="center", va="top", fontsize=14, fontweight="bold", color=PALETTE["ink"])

    foundations = [
        ("DSPy", "Prompts as typed code\nCompiler-optimized pipelines", "Reasoner, Compiler", PALETTE["semantic"]),
        ("Recursive\nLanguage Models", "Context as external state\nREPL-style narrowing", "Inspector", PALETTE["lexical"]),
        ("Memory\nConsolidation Faults", "Append-only episodes\nGated consolidation", "Memory Gate", PALETTE["accent"]),
        ("Agentic Search\n(Grep All You Need)", "Lexical-first hybrid\nRRF fusion", "Retriever", PALETTE["hybrid"]),
    ]
    positions = [(0.5, 2.6), (5.2, 2.6), (0.5, 0.3), (5.2, 0.3)]
    bw, bh = 4.2, 2.0
    for (fx, fy), (title, desc, maps_to, color) in zip(positions, foundations):
        _box(ax, fx, fy, bw, bh, title, color=color, fontsize=10)
        ax.text(fx + bw / 2, fy + bh / 2 - 0.2, desc, ha="center", va="center", fontsize=7, color="white", zorder=5)
        ax.text(fx + bw / 2, fy + 0.2, f"Links to: {maps_to}", ha="center", va="center",
                fontsize=7.5, fontweight="bold", color="white", zorder=5)
    ax.text(5, 4.3, "THALIA", ha="center", va="center", fontsize=16, fontweight="bold", color=PALETTE["ink"])
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_memory_lifecycle(output_path: str | Path) -> Path:
    """Episode to Memory Gate (dual-key) to Consolidation to MEMORY.md."""
    path = _prepare(output_path)
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")

    ax.text(5, 2.85, "Memory Lifecycle", ha="center", va="top", fontsize=13, fontweight="bold", color=PALETTE["ink"])
    _box(ax, 0.3, 1.1, 1.8, 0.8, "Raw Episode\n(query, answer, citations)", color=PALETTE["accent"])
    _arrow(ax, 2.1, 1.5, 3.5, 1.5)
    _box(ax, 3.5, 0.8, 2.2, 1.4, "Memory Gate\n", color=PALETTE["muted"])
    ax.text(4.6, 1.3, "requires flag AND\n(session-end / novel class\n/ explicit request)", ha="center", va="center", fontsize=6.5, color="white", zorder=5)
    _arrow(ax, 5.7, 1.5, 6.8, 1.5)
    ax.text(6.25, 1.2, "no", ha="center", va="bottom", fontsize=7, color=PALETTE["muted"], fontstyle="italic")
    _box(ax, 6.8, 1.1, 1.8, 0.8, "EpisodicStore\n(SQLite, append-only)", color=PALETTE["accent"], alpha=0.7)
    _arrow(ax, 5.7, 0.8, 6.8, 0.3, style="--")
    ax.text(6.25, 0.85, "yes", ha="center", va="bottom", fontsize=7, color=PALETTE["semantic"], fontstyle="italic")
    _box(ax, 6.8, 0.0, 2.2, 0.7, "Consolidate to MEMORY.md\n(derived, never mutates)", color=PALETTE["semantic"], alpha=0.7)
    ax.text(0.2, 0.05, "Every turn: append always. Consolidation requires both conditions.",
            ha="left", va="bottom", fontsize=6.5, color=PALETTE["muted"], fontstyle="italic")
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_gepa_evolution_loop(output_path: str | Path) -> Path:
    """GEPA-style trace-reflective evolution: config to evaluate to reflect to mutate."""
    path = _prepare(output_path)
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.2)
    ax.axis("off")

    ax.text(5, 3.05, "GEPA Evolution Loop", ha="center", va="top", fontsize=13, fontweight="bold", color=PALETTE["ink"])
    _box(ax, 0.3, 1.5, 1.8, 0.8, "Config\n(parameter vector)", color=PALETTE["lexical"])
    _arrow(ax, 2.1, 1.9, 3.0, 1.9)
    ax.text(2.55, 2.15, "build_fn", ha="center", va="bottom", fontsize=7, color=PALETTE["muted"], fontstyle="italic")
    _box(ax, 3.0, 1.5, 1.8, 0.8, "Evaluate\n(composite score)", color=PALETTE["hybrid"])
    _arrow(ax, 4.8, 1.9, 5.7, 1.9)
    ax.text(5.25, 2.15, "trace", ha="center", va="bottom", fontsize=7, color=PALETTE["muted"], fontstyle="italic")
    _box(ax, 5.7, 1.5, 1.8, 0.8, "Reflect\n(find weakest component)", color=PALETTE["semantic"])
    _arrow(ax, 7.5, 1.9, 8.4, 1.9)
    _box(ax, 8.4, 1.5, 1.4, 0.8, "Mutate", color=PALETTE["accent"])
    _arrow(ax, 9.8, 1.9, 9.8, 0.5, color=PALETTE["muted"])
    _arrow(ax, 9.8, 0.5, 0.3, 0.5, color=PALETTE["muted"])
    _arrow(ax, 0.3, 0.5, 0.3, 1.5, color=PALETTE["muted"])
    ax.text(5.0, 0.25, "Full trace recorded (seed + every candidate)", ha="center", va="center",
            fontsize=7.5, fontstyle="italic", color=PALETTE["muted"])
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


__all__ = [
    "PALETTE",
    "EXPORT_DPI",
    "plot_backend_comparison",
    "plot_category_components",
    "plot_injection_resistance",
    "plot_longmemeval",
    "plot_bottleneck",
    "plot_scaling_ci",
    "plot_orchestration_value",
    "plot_paraphrase_retrieval",
    "plot_retriever_comparison",
    "plot_rrf_weight_sensitivity",
    "plot_compiler_convergence",
    "plot_consolidation_curve",
    "plot_category_breakdown",
    "plot_evidence_funnel",
    "plot_pipeline_flow",
    "plot_noise_scaling",
    "plot_mmr_tradeoff",
    "plot_method_ablation",
    "plot_gepa_trajectory",
    "plot_thalia_overview",
    "plot_foundations_map",
    "plot_memory_lifecycle",
    "plot_gepa_evolution_loop",
]
