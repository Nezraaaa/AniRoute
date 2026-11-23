"""Matplotlib figures for the report, the Evaluation page and the slides."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

CLASS_COLORS = {
    "pothole": "#F59E0B",
    "severe_road_damage": "#DC2626",
    "standing_water": "#2563EB",
    "road_obstruction": "#7C3AED",
}
NEUTRAL = "#4F5A51"
ACCENT = "#1D6548"
ACCENT_LIGHT = "#9CC9AE"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.bbox": "tight", "font.size": 10, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 12,
})


def _color(name: str, index: int) -> str:
    fallback = ["#1D6548", "#2563EB", "#DC2626", "#F59E0B", "#7C3AED"]
    return CLASS_COLORS.get(name, fallback[index % len(fallback)])


def pretty(name: str) -> str:
    return name.replace("_", " ").capitalize()


def confusion_matrix(matrix: np.ndarray, names: list[str], path: Path, normalize: bool = False) -> None:
    labels = [pretty(n) for n in names] + ["Background"]
    data = matrix.astype(float)
    if normalize:
        data = data / np.maximum(data.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(1.6 + 1.25 * len(labels), 1.2 + 1.1 * len(labels)))
    image = ax.imshow(data, cmap="Greens", vmin=0, vmax=1 if normalize else max(1, data.max()))
    ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("True class")
    ax.set_title("Confusion matrix" + (" (row-normalised)" if normalize else " (counts)"))
    threshold = (1 if normalize else data.max()) * 0.55
    for i in range(len(labels)):
        for j in range(len(labels)):
            if i == len(labels) - 1 and j == len(labels) - 1:
                continue
            value = f"{data[i, j]:.2f}" if normalize else f"{int(data[i, j])}"
            ax.text(j, i, value, ha="center", va="center", color="white" if data[i, j] > threshold else "#1E241F")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.savefig(path)
    plt.close(fig)


def pr_curves(curves: dict, names: list[str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4.6))
    for class_id, name in enumerate(names):
        c = curves[class_id]
        if c.n_gt == 0 or c.pr_recall.size == 0:
            continue
        precision = np.flip(np.maximum.accumulate(np.flip(c.pr_precision)))
        ax.plot(c.pr_recall, precision, color=_color(name, class_id), lw=2,
                label=f"{pretty(name)}  AP50 {c.ap[0]:.2f}")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-recall curve (IoU 0.5)")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower left", frameon=False)
    fig.savefig(path)
    plt.close(fig)


def f1_curve(conf_grid: np.ndarray, f1_at: dict, mean_f1: np.ndarray, names: list[str], best: float, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4.2))
    for class_id, values in f1_at.items():
        ax.plot(conf_grid, values, color=_color(names[class_id], class_id), lw=1.4, alpha=0.8, label=pretty(names[class_id]))
    ax.plot(conf_grid, mean_f1, color="#1E241F", lw=2.6, label="All classes")
    ax.axvline(best, color=ACCENT, ls="--", lw=1.4)
    ax.annotate(f"chosen threshold {best:.2f}\nF1 {mean_f1.max():.2f}", (best, mean_f1.max()),
                xytext=(10, -30), textcoords="offset points", color=ACCENT, fontsize=9)
    ax.set_xlabel("Confidence threshold")
    ax.set_ylabel("F1 score")
    ax.set_ylim(0, 1)
    ax.set_title("F1 vs confidence: choosing the operating threshold")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="lower center")
    fig.savefig(path)
    plt.close(fig)


def grouped_bars(groups: list[str], series: dict[str, list[float]], path: Path, title: str, ylabel: str,
                 colors: list[str] | None = None, ylim: tuple[float, float] | None = (0, 1)) -> None:
    colors = colors or [ACCENT_LIGHT, ACCENT, NEUTRAL, "#2563EB"]
    fig, ax = plt.subplots(figsize=(max(5.5, 1.3 * len(groups) * len(series) ** 0.5 + 2), 4.2))
    width = 0.8 / max(1, len(series))
    x = np.arange(len(groups))
    for index, (label, values) in enumerate(series.items()):
        bars = ax.bar(x + (index - (len(series) - 1) / 2) * width, values, width * 0.92, label=label,
                      color=colors[index % len(colors)])
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.2f}" if value < 10 else f"{value:.0f}",
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, groups)
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_title(title)
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.savefig(path)
    plt.close(fig)


def optimization_chart(rows: list[dict], path: Path) -> None:
    """mAP@0.5 bars per experiment with CPU FPS as a line on a second axis."""
    rows = [row for row in rows if row.get("map50") is not None]
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(rows) + 2), 4.4))
    x = np.arange(len(rows))
    best = max(range(len(rows)), key=lambda i: rows[i]["map50"])
    colors = [ACCENT if i == best else ACCENT_LIGHT for i in range(len(rows))]
    bars = ax.bar(x, [row["map50"] for row in rows], color=colors)
    for bar, row in zip(bars, rows):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{row['map50']:.3f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, [row["id"] for row in rows])
    ax.set_ylabel("mAP@0.5 (validation)")
    ax.set_ylim(0, 1)
    ax.set_title("Optimisation experiments")
    fps = [row.get("fps") for row in rows]
    if any(value for value in fps):
        twin = ax.twinx()
        twin.plot(x, [value or np.nan for value in fps], color=NEUTRAL, marker="o", lw=1.6, label="CPU FPS")
        twin.set_ylim(0, max(v for v in fps if v) * 1.3)   # from zero, so small timing noise looks small
        twin.set_ylabel("Frames per second (laptop CPU)")
        twin.spines["top"].set_visible(False)
        twin.legend(frameon=False, loc="upper right")
    fig.savefig(path)
    plt.close(fig)


def speed_chart(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    labels = [f"{row['model']}\n{row['format']} @{row['imgsz']}" for row in rows]
    fig, ax = plt.subplots(figsize=(max(6, 1.15 * len(rows) + 2), 4.2))
    values = [row["fps"] for row in rows]
    bars = ax.bar(range(len(rows)), values, color=[ACCENT if row["format"] != "pt" else ACCENT_LIGHT for row in rows])
    for bar, row in zip(bars, rows):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{row['fps']:.1f} fps\n{row['mean_ms']:.0f} ms",
                ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(rows)), labels, fontsize=8)
    ax.set_ylim(0, max(values) * 1.22)
    ax.set_ylabel("Frames per second (higher is better)")
    ax.set_title("Inference speed on this laptop CPU")
    ax.grid(axis="y", alpha=0.25)
    fig.savefig(path)
    plt.close(fig)
