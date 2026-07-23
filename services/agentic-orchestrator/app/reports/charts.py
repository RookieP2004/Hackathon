"""
Real chart generation (matplotlib, Agg backend -- no display server needed)
for the PDF renderer. Each function writes a PNG to a temp path and returns
it; callers embed it into the PDF, then the caller is responsible for
cleanup once the PDF has been written (charts.py doesn't know the PDF's
lifetime).
"""

from __future__ import annotations

import tempfile
import uuid

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CHART_DIR = tempfile.gettempdir()


def _chart_path(prefix: str) -> str:
    return f"{CHART_DIR}/aegis-chart-{prefix}-{uuid.uuid4().hex[:8]}.png"


def bar_chart(*, title: str, labels: list[str], values: list[float], ylabel: str = "") -> str:
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.bar(labels, values, color="#2a5d9f")
    ax.set_title(title, fontsize=11)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=30, ha="right", fontsize=8)
    fig.tight_layout()
    path = _chart_path("bar")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def line_chart(*, title: str, x_labels: list[str], series: dict[str, list[float]], ylabel: str = "") -> str:
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    for name, values in series.items():
        ax.plot(x_labels, values, marker="o", label=name)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel(ylabel)
    if len(series) > 1:
        ax.legend(fontsize=8)
    plt.xticks(rotation=30, ha="right", fontsize=8)
    fig.tight_layout()
    path = _chart_path("line")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def pie_chart(*, title: str, labels: list[str], values: list[float]) -> str:
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.pie(values, labels=labels, autopct="%1.0f%%", textprops={"fontsize": 8})
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    path = _chart_path("pie")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
