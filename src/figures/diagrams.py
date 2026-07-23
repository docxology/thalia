"""Architectural diagram figures (intro, foundations, harness design)."""

from __future__ import annotations

from pathlib import Path

from ..figure_style import EXPORT_DPI, PALETTE, plt, prepare as _prepare


_DIAGRAM_PAPER = "#FBF8F2"
_COMPILER_PURPLE = "#5B4B8A"
_COVER_PAPER = "#F5E6D3"
_COVER_CHARCOAL = "#2D2D2D"
_COVER_TEAL = "#00796B"


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


def _stage_icon(ax, x, y, kind, color="white"):
    """Draw a small stage-specific glyph without introducing image assets."""
    from matplotlib.patches import Circle, FancyBboxPatch

    if kind == "inspect":
        ax.add_patch(Circle((x, y), 0.16, fill=False, edgecolor=color, linewidth=1.8, zorder=5))
        ax.add_patch(Circle((x, y), 0.055, facecolor=color, edgecolor="none", zorder=6))
        ax.plot([x - 0.30, x - 0.20], [y - 0.22, y - 0.22], color=color, linewidth=1.5, zorder=5)
        ax.plot([x - 0.08, x + 0.30], [y - 0.22, y - 0.22], color=color, linewidth=1.5, zorder=5)
    elif kind == "retrieve":
        for offset, width in ((0.16, 0.27), (0.0, 0.20), (-0.16, 0.13)):
            ax.add_patch(Circle((x - 0.26, y + offset), 0.035, facecolor=color, edgecolor="none", zorder=5))
            ax.plot([x - 0.17, x + width], [y + offset, y + offset], color=color, linewidth=2.0, zorder=5)
    elif kind == "reason":
        for dx, dy in ((-0.22, 0.14), (0.22, 0.14), (0.0, -0.18)):
            ax.plot([x, x + dx], [y, y + dy], color=color, linewidth=1.4, zorder=5)
            ax.add_patch(Circle((x + dx, y + dy), 0.045, facecolor=color, edgecolor="none", zorder=6))
        ax.add_patch(Circle((x, y), 0.07, facecolor=color, edgecolor="none", zorder=6))
    elif kind == "memory":
        for offset, width in ((0.14, 0.36), (0.0, 0.30), (-0.14, 0.24)):
            ax.add_patch(
                FancyBboxPatch(
                    (x - width / 2, y + offset - 0.045),
                    width,
                    0.09,
                    boxstyle="round,pad=0.02",
                    facecolor="none",
                    edgecolor=color,
                    linewidth=1.4,
                    zorder=5,
                )
            )
    else:
        raise ValueError(f"unknown stage icon: {kind}")


_STAGES = [
    ("Inspector", 0, PALETTE["lexical"], "inspect", "scan / narrow"),
    ("Retriever", 1, PALETTE["hybrid"], "retrieve", "rank / fuse"),
    ("Reasoner", 2, PALETTE["semantic"], "reason", "verify / answer"),
    ("Memory Gate", 3, PALETTE["accent"], "memory", "append / gate"),
]


def plot_thalia_overview(output_path: str | Path) -> Path:
    """Graphical abstract: evidence moves through four typed stages and a compiler loop."""
    path = _prepare(output_path)
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    fig.patch.set_facecolor(_DIAGRAM_PAPER)
    ax.set_facecolor(_DIAGRAM_PAPER)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    ax.text(
        5,
        3.82,
        "THALIA / evidence > action > memory",
        ha="center",
        va="top",
        fontsize=17,
        fontweight="bold",
        color=PALETTE["ink"],
    )
    ax.text(
        5,
        3.52,
        "A typed, inspectable path from a query to a cited answer",
        ha="center",
        va="top",
        fontsize=8.5,
        color=PALETTE["muted"],
        fontstyle="italic",
    )

    xs = [0.65, 2.95, 5.25, 7.55]
    card_y, bw, bh = 2.18, 1.08, 1.0
    for i, (name, idx, color, icon, verb) in enumerate(_STAGES):
        _box(ax, xs[i], card_y, bw, bh, "", color=color)
        _stage_icon(ax, xs[i] + bw / 2, card_y + 0.76, icon)
        ax.text(
            xs[i] + bw / 2,
            card_y + 0.40,
            f"Stage {idx}\n{name}",
            ha="center",
            va="center",
            fontsize=8.8,
            color="white",
            zorder=5,
        )
        ax.text(
            xs[i] + bw / 2,
            card_y - 0.16,
            verb,
            ha="center",
            va="top",
            fontsize=7.2,
            color=color,
            fontweight="bold",
        )

    for i in range(len(xs) - 1):
        _arrow(ax, xs[i] + bw, card_y + 0.54, xs[i + 1], card_y + 0.54, color=PALETTE["ink"])

    _arrow(ax, 0.05, card_y + 0.54, xs[0], card_y + 0.54, head=0.15, color=PALETTE["ink"])
    ax.text(0.05, 3.12, "Query +\nHistory", ha="center", va="bottom", fontsize=8, fontstyle="italic", color=PALETTE["muted"])

    _arrow(ax, xs[-1] + bw, card_y + 0.54, 9.95, card_y + 0.54, head=0.15, color=PALETTE["ink"])
    ax.text(9.95, 3.12, "Answer +\nCitations", ha="center", va="bottom", fontsize=8, fontstyle="italic", color=PALETTE["muted"])

    compiler_x, compiler_y, compiler_w, compiler_h = 2.35, 0.54, 5.3, 0.72
    loop_y = 1.48
    _arrow(ax, xs[-1] + bw / 2, card_y, xs[-1] + bw / 2, loop_y, style="--", head=0.08, color=_COMPILER_PURPLE)
    _arrow(ax, xs[-1] + bw / 2, loop_y, compiler_x + compiler_w, loop_y, style="--", head=0.08, color=_COMPILER_PURPLE)
    _arrow(ax, compiler_x, loop_y, xs[0] + bw / 2, loop_y, style="--", head=0.08, color=_COMPILER_PURPLE)
    _arrow(ax, xs[0] + bw / 2, loop_y, xs[0] + bw / 2, card_y, style="--", head=0.08, color=_COMPILER_PURPLE)
    _box(
        ax,
        compiler_x,
        compiler_y,
        compiler_w,
        compiler_h,
        "Stage 4: Compiler   ·   MIPRO search / GEPA evolution",
        color=_COMPILER_PURPLE,
        alpha=0.92,
        fontsize=8.2,
        bold=True,
    )
    ax.text(
        compiler_x + compiler_w / 2,
        0.35,
        "offline optimization loop · full trace recorded",
        ha="center",
        va="center",
        fontsize=7,
        fontstyle="italic",
        color=PALETTE["muted"],
    )

    ax.text(
        0.12,
        0.07,
        "THALIA: Typed Harness with Analytical Lexical-Integrated Architecture",
        ha="left",
        va="bottom",
        fontsize=6.8,
        color=PALETTE["muted"],
        fontstyle="italic",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=EXPORT_DPI)
    plt.close(fig)
    return path


def plot_thalia_cover(output_path: str | Path) -> Path:
    """Create the manuscript cover visual abstract from the typed stage contract."""
    from matplotlib.patches import FancyBboxPatch

    path = _prepare(output_path)
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    fig.patch.set_facecolor(_COVER_PAPER)
    ax.set_facecolor(_COVER_PAPER)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8)
    ax.axis("off")

    ax.text(0.55, 7.48, "THALIA", ha="left", va="top", fontsize=25, fontweight="bold", color=_COMPILER_PURPLE)
    ax.text(
        0.58,
        6.93,
        "A typed harness for inspectable, evidence-grounded memory experiments",
        ha="left",
        va="top",
        fontsize=10.5,
        color=_COVER_CHARCOAL,
    )
    ax.text(15.45, 7.38, "VISUAL ABSTRACT / 2026", ha="right", va="top", fontsize=7.2, fontweight="bold", color=_COVER_TEAL)
    ax.plot([0.58, 15.42], [6.58, 6.58], color=_COVER_CHARCOAL, linewidth=0.8, alpha=0.45)

    card_y, card_w, card_h = 3.25, 3.15, 1.85
    card_xs = [0.55, 4.35, 8.15, 11.95]
    stage_data = [
        ("0 / INSPECTOR", "scan + narrow", "session history", PALETTE["lexical"], "selected windows"),
        ("1 / RETRIEVER", "rank + fuse", "lexical + surrogate", PALETTE["hybrid"], "ranked evidence"),
        ("2 / REASONER", "verify + answer", "LM behind protocol", PALETTE["semantic"], "cited answer"),
        ("3 / MEMORY GATE", "append + gate", "raw episode first", PALETTE["accent"], "derived memory"),
    ]
    for index, (x, (label, verb, detail, color, result)) in enumerate(zip(card_xs, stage_data)):
        card = FancyBboxPatch(
            (x, card_y), card_w, card_h, boxstyle="round,pad=0.08", facecolor="#FFFDF8", edgecolor=_COVER_CHARCOAL, linewidth=1.1, zorder=3
        )
        ax.add_patch(card)
        ax.add_patch(
            FancyBboxPatch(
                (x, card_y + card_h - 0.24), card_w, 0.24, boxstyle="round,pad=0.02", facecolor=color, edgecolor=color, linewidth=0, zorder=4
            )
        )
        ax.text(x + 0.18, card_y + card_h - 0.12, label, ha="left", va="center", fontsize=7.2, fontweight="bold", color="white", zorder=5)
        ax.text(x + 0.18, card_y + 1.18, verb, ha="left", va="center", fontsize=12, fontweight="bold", color=_COVER_CHARCOAL, zorder=5)
        ax.text(x + 0.18, card_y + 0.78, detail, ha="left", va="center", fontsize=8.2, color="#555555", zorder=5)
        ax.text(x + 0.18, card_y + 0.32, f"out: {result}", ha="left", va="center", fontsize=8.2, fontstyle="italic", color=color, zorder=5)
        for row in range(3):
            line_width = 0.78 - row * 0.14
            yy = card_y + 0.90 + row * 0.16
            ax.plot([x + 2.35, x + 2.35 + line_width], [yy, yy], color=color, linewidth=1.6, zorder=5)
            ax.add_patch(plt.Circle((x + 2.18, yy), 0.035, facecolor=color, edgecolor="none", zorder=5))
        if index < len(card_xs) - 1:
            next_x = card_xs[index + 1]
            ax.annotate(
                "",
                xy=(next_x - 0.16, card_y + card_h / 2),
                xytext=(x + card_w + 0.16, card_y + card_h / 2),
                arrowprops=dict(arrowstyle="->", color=_COVER_TEAL, linewidth=1.5),
            )

    ax.text(0.55, 5.55, "RAW EVIDENCE", ha="left", va="center", fontsize=7.2, fontweight="bold", color=_COVER_CHARCOAL)
    ax.text(15.45, 5.55, "AUDITABLE OUTPUT", ha="right", va="center", fontsize=7.2, fontweight="bold", color=_COVER_CHARCOAL)
    ax.plot([0.78, 15.22], [5.38, 5.38], color=_COVER_TEAL, linewidth=1.2, alpha=0.75)
    for x in (1.05, 4.85, 8.65, 12.45, 15.0):
        ax.add_patch(plt.Circle((x, 5.38), 0.07, facecolor=_COVER_TEAL, edgecolor=_COVER_PAPER, linewidth=1.0, zorder=5))

    compiler = FancyBboxPatch(
        (2.15, 1.34), 11.7, 0.92, boxstyle="round,pad=0.10", facecolor=_COMPILER_PURPLE, edgecolor=_COVER_CHARCOAL, linewidth=1.0, zorder=3
    )
    ax.add_patch(compiler)
    ax.text(2.55, 1.93, "4 / COMPILER", ha="left", va="center", fontsize=8, fontweight="bold", color="white", zorder=4)
    ax.text(2.55, 1.62, "bounded offline search", ha="left", va="center", fontsize=9.3, color="white", zorder=4)
    ax.text(13.45, 1.78, "MIPRO-style  ·  GEPA-style  ·  full trace", ha="right", va="center", fontsize=8.4, color=_COVER_PAPER, fontstyle="italic", zorder=4)
    ax.annotate("", xy=(12.1, 3.12), xytext=(12.1, 2.28), arrowprops=dict(arrowstyle="->", linestyle="--", color=_COMPILER_PURPLE, linewidth=1.2))
    ax.annotate("", xy=(3.25, 2.28), xytext=(3.25, 3.12), arrowprops=dict(arrowstyle="->", linestyle="--", color=_COMPILER_PURPLE, linewidth=1.2))

    ax.text(0.55, 0.72, "SCOPE", ha="left", va="center", fontsize=7.2, fontweight="bold", color=_COMPILER_PURPLE)
    ax.text(
        1.55,
        0.72,
        "default responder: extractive  /  semantic lane: hashing surrogate  /  raw episodes: append-only",
        ha="left",
        va="center",
        fontsize=7.7,
        color=_COVER_CHARCOAL,
    )
    ax.text(15.45, 0.22, "Typed contracts · deterministic core · reproducible artifacts", ha="right", va="center", fontsize=7.2, color="#666666", fontstyle="italic")

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(path, dpi=EXPORT_DPI, facecolor=_COVER_PAPER)
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
    # Keep generous horizontal and vertical margins: this figure is embedded at
    # 80% manuscript width, so long labels that fit on the source canvas can
    # otherwise be clipped by the box or the axes edge after PDF scaling.
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.4)
    ax.axis("off")

    ax.text(6, 3.25, "Memory Lifecycle", ha="center", va="top", fontsize=13, fontweight="bold", color=PALETTE["ink"])
    _box(
        ax,
        0.4,
        1.35,
        2.5,
        0.95,
        "Raw Episode\n(query, answer,\ncitations)",
        color=PALETTE["accent"],
        fontsize=8,
    )
    _arrow(ax, 2.9, 1.83, 3.6, 1.83)
    _box(ax, 3.6, 1.05, 2.8, 1.55, "", color=PALETTE["muted"])
    ax.text(5.0, 2.22, "Memory Gate", ha="center", va="center", fontsize=9, color="white", zorder=5)
    ax.text(
        5.0,
        1.48,
        "requires flag AND\n(session-end / novel class\n/ explicit request)",
        ha="center",
        va="center",
        fontsize=7,
        color="white",
        zorder=5,
    )
    _arrow(ax, 6.4, 1.83, 7.4, 1.83)
    ax.text(6.9, 1.48, "no", ha="center", va="bottom", fontsize=7, color=PALETTE["muted"], fontstyle="italic")
    _box(
        ax,
        7.4,
        1.35,
        2.5,
        0.95,
        "EpisodicStore\n(SQLite,\nappend-only)",
        color=PALETTE["accent"],
        alpha=0.7,
        fontsize=8,
    )
    _arrow(ax, 6.4, 1.05, 7.4, 0.62, style="--")
    ax.text(6.9, 0.92, "yes", ha="center", va="bottom", fontsize=7, color=PALETTE["semantic"], fontstyle="italic")
    _box(
        ax,
        7.4,
        0.18,
        3.2,
        0.82,
        "Consolidate to\nMEMORY.md\n(derived, never mutates)",
        color=PALETTE["semantic"],
        alpha=0.7,
        fontsize=7.5,
    )
    ax.text(
        0.4,
        0.08,
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
    "plot_thalia_cover",
    "plot_thalia_overview",
    "plot_foundations_map",
    "plot_memory_lifecycle",
    "plot_gepa_evolution_loop",
]
