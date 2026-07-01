"""Shared plotting style helpers for THALIA figures."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt

PALETTE = {
    "lexical": "#0072B2",
    "semantic": "#E69F00",
    "hybrid": "#009E73",
    "accent": "#CC79A7",
    "muted": "#999999",
    "ink": "#222222",
}
EXPORT_DPI = 300
FIGSIZE = (6.2, 4.0)


def apply_style() -> None:
    """Apply one shared publication style to every figure."""
    mpl.rcParams.update(
        {
            "figure.figsize": FIGSIZE,
            "savefig.dpi": EXPORT_DPI,
            "savefig.bbox": "tight",
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 9,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#444444",
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": "#DDDDDD",
            "grid.linewidth": 0.6,
            "grid.alpha": 0.7,
            "text.color": PALETTE["ink"],
            "axes.labelcolor": PALETTE["ink"],
            "axes.titlecolor": PALETTE["ink"],
            "xtick.color": "#444444",
            "ytick.color": "#444444",
        }
    )


def prepare(output_path: str | Path) -> Path:
    """Ensure the parent directory exists and return a Path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def zoomed_ylim(values: list[float], pad: float = 0.04) -> tuple[float, float]:
    """Return a tight y-range around values so small structure is visible."""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return max(0.0, lo - 0.1), min(1.0, hi + 0.1)
    return max(0.0, lo - pad), min(1.0, hi + pad)


def pretty(label: str) -> str:
    """Turn a snake_case task category into a display label."""
    return label.replace("_", " ").capitalize()


def annotate_bars(ax, bars, values, fmt: str = "{:.3f}", dy: float = 0.0) -> None:
    """Write value labels above vertical bars."""
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + dy,
            fmt.format(value),
            ha="center",
            va="bottom",
            fontsize=9,
        )


apply_style()

__all__ = [
    "PALETTE",
    "EXPORT_DPI",
    "FIGSIZE",
    "annotate_bars",
    "apply_style",
    "mpl",
    "plt",
    "prepare",
    "pretty",
    "zoomed_ylim",
]
