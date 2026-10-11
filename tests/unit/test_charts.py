"""SVG chart geometry (story 5.2)."""

from hotel.web.charts import (
    BAR_WIDTH,
    HEIGHT,
    PLOT_BOTTOM,
    PLOT_TOP,
    WIDTH,
    bar_chart,
    column_chart,
)


def test_columns_scale_to_the_maximum_and_never_overflow():
    chart = column_chart(
        "Occupancy", [("1", 10_000, ""), ("2", 5_000, ""), ("3", 12_000, "")], maximum=10_000
    )
    full, half, capped = chart.bars
    plot = PLOT_BOTTOM - PLOT_TOP
    assert (full.height, full.y) == (plot, PLOT_TOP)
    assert half.height == plot / 2
    assert capped.height == plot  # values above the maximum are capped
    assert all(b.x >= 0 and b.x + b.width <= WIDTH for b in chart.bars)
    assert chart.height == HEIGHT


def test_time_runs_right_to_left_in_rtl():
    points = [("a", 1, ""), ("b", 2, ""), ("c", 3, "")]
    ltr = column_chart("x", points, maximum=3)
    rtl = column_chart("x", points, maximum=3, rtl=True)
    assert ltr.bars[0].x < ltr.bars[2].x
    assert rtl.bars[0].x > rtl.bars[2].x


def test_long_ranges_thin_out_the_labels():
    chart = column_chart("x", [(str(i), i, "") for i in range(60)], maximum=60)
    labels = [b.label for b in chart.bars if b.label]
    assert 1 < len(labels) <= 12


def test_horizontal_bars_are_relative_to_the_largest():
    chart = bar_chart("Nights", [("Deluxe", 10, "10"), ("Suite", 5, "5")])
    assert [b.width for b in chart.bars] == [BAR_WIDTH, BAR_WIDTH / 2]
    rtl = bar_chart("Nights", [("Deluxe", 10, "10"), ("Suite", 5, "5")], rtl=True)
    assert rtl.bars[1].x == BAR_WIDTH / 2  # grows from the right edge


def test_empty_data_gives_an_empty_chart():
    assert column_chart("x", [], maximum=1).bars == []
    assert bar_chart("x", []).bars == []
    assert bar_chart("x", [("a", 0, "0")]).bars[0].width == 0
