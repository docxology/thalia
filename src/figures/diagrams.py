"""Architectural diagram figures (intro, foundations, harness design)."""

from __future__ import annotations

from pathlib import Path

from ..figure_style import EXPORT_DPI, PALETTE, plt, prepare as _prepare


def _box(ax, x, y, w, h, text, color="#0072B2", edge="#222222", alpha=0.9, fontsize=9, bold=False):
    """Draw a labelled rounded box with optional bold."""
    from matplotlib.patches import FancyBboxPatch

    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.08",
        facecolor=color,
        edgecolor=edge,
        linewidth=1.2,
        alpha=alpha,
        zorder=3,
    )
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color="white",
        zorder=4,
    )


def _arrow(ax, x1, y1, x2, y2, color="#444444", lw=1.8, style="-", head=0.12):
    """Draw an arrow between two points."""
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle=f"->,head_length={head},head_width={head}",
            color=color,
            lw=lw,
            linestyle=style,
        ),
    )


_STAGES = [
    ("Inspector", 0, PALETTE["lexical"]),
    ("Retriever", 1, PALETTE["hybrid"]),
    ("Reasoner", 2, PALETTE["semantic"]),
    ("Memory Gate", 3, PALETTE["accent"]),
]


def plot_thalia_overview(output_path: str | Path) -> Path:
    """Graphical abstract / cover figure: 5-stage pipeline as a labelled loop."""
    path = _prepare(output_path)
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    ax.text(
        5,
        3.65,
        "THALIA Pipeline Overview",
        ha="center",
        va="top",
        fontsize=18,
        fontweight="bold",
        color=PALETTE["ink"],
    )

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
    _box(
        ax,
        3.6,
        compiler_y - 0.55,
        2.8,
        0.7,
        "Stage 4: Compiler\n(MIPRO search / GEPA evolution)",
        color=PALETTE["muted"],
        alpha=0.85,
    )
    ax.text(
        5.0,
        compiler_y - 0.15,
        "offline optimization loop",
        ha="center",
        va="center",
        fontsize=7,
        fontstyle="italic",
        color="white",
        fontweight="bold",
    )

    ax.text(
        0.2,
        0.05,
        "THALIA: Typed Harness with Analytical Lexical-Integrated Architecture",
        ha="left",
        va="bottom",
        fontsize=7,
        color=PALETTE["muted"],
        fontstyle="italic",
    )
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

    ax.text(
        5,
        4.85,
        "Foundations to THALIA Stage Map",
        ha="center",
        va="top",
        fontsize=14,
        fontweight="bold",
        color=PALETTE["ink"],
    )

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
        ax.text(
            fx + bw / 2,
            fy + 0.2,
            f"Links to: {maps_to}",
            ha="center",
            va="center",
            fontsize=7.5,
            fontweight="bold",
            color="white",
            zorder=5,
        )
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
    ax.text(
        4.6,
        1.3,
        "requires flag AND\n(session-end / novel class\n/ explicit request)",
        ha="center",
        va="center",
        fontsize=6.5,
        color="white",
        zorder=5,
    )
    _arrow(ax, 5.7, 1.5, 6.8, 1.5)
    ax.text(6.25, 1.2, "no", ha="center", va="bottom", fontsize=7, color=PALETTE["muted"], fontstyle="italic")
    _box(ax, 6.8, 1.1, 1.8, 0.8, "EpisodicStore\n(SQLite, append-only)", color=PALETTE["accent"], alpha=0.7)
    _arrow(ax, 5.7, 0.8, 6.8, 0.3, style="--")
    ax.text(6.25, 0.85, "yes", ha="center", va="bottom", fontsize=7, color=PALETTE["semantic"], fontstyle="italic")
    _box(
        ax,
        6.8,
        0.0,
        2.2,
        0.7,
        "Consolidate to MEMORY.md\n(derived, never mutates)",
        color=PALETTE["semantic"],
        alpha=0.7,
    )
    ax.text(
        0.2,
        0.05,
        "Every turn: append always. Consolidation requires both conditions.",
        ha="left",
        va="bottom",
        fontsize=6.5,
        color=PALETTE["muted"],
        fontstyle="italic",
    )
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
    ax.text(
        5.0,
        0.25,
        "Full trace recorded (seed + every candidate)",
        ha="center",
        va="center",
        fontsize=7.5,
        fontstyle="italic",
        color=PALETTE["muted"],
    )
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


__all__ = [
    "plot_thalia_overview",
    "plot_foundations_map",
    "plot_memory_lifecycle",
    "plot_gepa_evolution_loop",
]
