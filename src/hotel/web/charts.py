"""Bar charts drawn as SVG on the server (story 5.2).

No JavaScript and no chart library: Python computes rectangles in a fixed
coordinate system (the SVG viewBox), the template writes them out, and the
stylesheet colours them with the theme's variables, so a chart follows the
light/dark theme like any other element. The CSP forbids inline styles, so
only geometry attributes (x, y, width, height) are written in the markup.

Charts are pictures for a quick look; every chart has the same numbers in a
table next to it, which is also what screen readers use.
"""

from __future__ import annotations

from dataclasses import dataclass

WIDTH = 600
HEIGHT = 220
PLOT_TOP = 10
PLOT_BOTTOM = 190  # x-axis labels below this line
MAX_LABELS = 12  # time axes show at most this many labels
BAR_WIDTH = 320  # horizontal charts sit in half-width panels: a narrower drawing keeps text legible


@dataclass(frozen=True, slots=True)
class Bar:
    x: float
    y: float
    width: float
    height: float
    label: str  # axis label (may be empty when labels are thinned out)
    title: str  # tooltip / accessible text: "12 Oct: 75 %"


@dataclass(frozen=True, slots=True)
class Chart:
    title: str
    bars: list[Bar]
    width: int = WIDTH
    height: int = HEIGHT
    label_y: int = HEIGHT - 8


def column_chart(
    title: str, points: list[tuple[str, int, str]], *, maximum: int, rtl: bool = False
) -> Chart:
    """Vertical bars over time: points are (axis label, value, tooltip).

    `maximum` is the value of a full-height bar (10 000 for a percentage in
    basis points). In right-to-left languages time runs from right to left,
    so the bars are simply placed in reverse order.
    """
    if not points:
        return Chart(title, [])
    slot = WIDTH / len(points)
    gap = slot * 0.2 if slot > 4 else 0
    every = max(1, -(-len(points) // MAX_LABELS))  # ceiling division
    plot = PLOT_BOTTOM - PLOT_TOP
    bars = []
    for index, (label, value, tooltip) in enumerate(points):
        position = len(points) - 1 - index if rtl else index
        height = plot * min(max(value, 0), maximum) / maximum if maximum else 0
        bars.append(
            Bar(
                x=round(position * slot + gap / 2, 2),
                y=round(PLOT_BOTTOM - height, 2),
                width=round(slot - gap, 2),
                height=round(height, 2),
                label=label if index % every == 0 else "",
                title=tooltip,
            )
        )
    return Chart(title, bars)


def bar_chart(title: str, rows: list[tuple[str, int, str]], *, rtl: bool = False) -> Chart:
    """Horizontal bars for categories: rows are (label, value, tooltip).

    The longest bar fills the width; labels are written above each bar. In
    right-to-left languages bars grow from the right edge.
    """
    if not rows:
        return Chart(title, [])
    biggest = max(max(value for _, value, _ in rows), 1)
    row_height = 34
    bars = []
    for index, (label, value, tooltip) in enumerate(rows):
        width = BAR_WIDTH * max(value, 0) / biggest
        bars.append(
            Bar(
                x=round(BAR_WIDTH - width, 2) if rtl else 0,
                y=index * row_height + 16,
                width=round(width, 2),
                height=12,
                label=label,
                title=tooltip,
            )
        )
    return Chart(title, bars, width=BAR_WIDTH, height=len(rows) * row_height + 4, label_y=0)
