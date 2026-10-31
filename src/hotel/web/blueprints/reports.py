"""Management statistics, kept for managers (story 5.1, brief §4.8)."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, Response, abort, render_template, request
from flask_babel import format_date, get_locale
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l

from hotel.domain.enums import Role
from hotel.domain.errors import HotelError
from hotel.web import forms
from hotel.web.charts import bar_chart, column_chart
from hotel.web.context import current_actor, services
from hotel.web.csv_export import to_csv
from hotel.web.formatting import money, percent
from hotel.web.preferences import text_direction
from hotel.web.security import roles_required

bp = Blueprint("reports", __name__, url_prefix="/reports")

DAILY_TABLE_LIMIT = 62  # longer ranges are shown per month


def presets(today: date) -> list[tuple[object, date, date]]:
    """Story 7.9: the ranges managers ask for most, one click instead of two dates."""
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    yesterday = today - timedelta(days=1)
    return [
        (_l("Yesterday"), yesterday, yesterday),
        (_l("This month"), month_start, next_month - timedelta(days=1)),
        (_l("Last month"), last_month_end.replace(day=1), last_month_end),
        (_l("Next 30 days"), today, today + timedelta(days=29)),
        (_l("Year to date"), today.replace(month=1, day=1), today),
    ]


@bp.get("/")
@roles_required(Role.MANAGER)
def index():
    reports = services().reports
    default_first, default_last = reports.default_range()
    args = request.args
    values = {
        "first": args.get("first", default_first.isoformat()),
        "last": args.get("last", default_last.isoformat()),
        "day": args.get("day", services().clock.today().isoformat()),
    }
    report, errors = None, forms.FormErrors()
    try:
        report = reports.report(
            current_actor(),
            forms.calendar_date(values, "first"),
            forms.calendar_date(values, "last"),
            availability_day=forms.calendar_date(values, "day"),
        )
    except HotelError as exc:
        errors = forms.FormErrors.from_error(exc)
    daily = report is not None and len(report.days) <= DAILY_TABLE_LIMIT
    return render_template(
        "reports/index.html",
        report=report,
        values=values,
        errors=errors,
        daily=daily,
        presets=presets(services().clock.today()),
        charts=_charts(report, daily) if report else None,
    ), (400 if errors else 200)


def _charts(report, daily: bool) -> dict:
    """Story 5.2: occupancy over time, revenue by type, nights per category."""
    rtl = text_direction(str(get_locale() or "en")) == "rtl"
    if daily:
        points = [
            (
                format_date(d.night, "d/M"),
                d.occupancy_bp,
                f"{format_date(d.night, 'medium')}: {percent(d.occupancy_bp)}",
            )
            for d in report.days
        ]
    else:
        points = [
            (
                format_date(m.month, "MMM yy"),
                m.occupancy_bp,
                f"{format_date(m.month, 'MMMM yyyy')}: {percent(m.occupancy_bp)}",
            )
            for m in report.months()
        ]
    revenue = [
        (_("Accommodation (after discounts)"), report.accommodation),
        (_("Extra services"), report.services),
        (_("Cancellation and no-show fees"), report.fees),
        (_("Taxes"), report.taxes),
    ]
    return {
        "occupancy": column_chart(_("Occupancy"), points, maximum=10_000, rtl=rtl),
        "revenue": bar_chart(
            _("Revenue"),
            [(label, amount.millimes, money(amount)) for label, amount in revenue],
            rtl=rtl,
        ),
        "categories": bar_chart(
            _("Nights sold"),
            [(c.name, c.nights, str(c.nights)) for c in report.categories],
            rtl=rtl,
        ),
        "rtl": rtl,
    }


# ---------------------------------------------------------------- CSV (story 5.3)
def _occupancy_rows(report):
    return (
        ["night", "sold", "sellable", "occupancy_percent", "room_value_dt"],
        [
            (d.night.isoformat(), d.sold, d.sellable, d.occupancy_bp / 100, d.room_value)
            for d in report.days
        ],
    )


def _revenue_rows(report):
    rows = [(kind, amount) for kind, amount in sorted(report.invoiced.items())]
    rows += [(f"cash_{method}", amount) for method, amount in sorted(report.cash.items())]
    return ["item", "amount_dt"], rows


def _category_rows(report):
    return (
        ["category", "nights_sold", "room_value_dt"],
        [(c.name, c.nights, c.room_value) for c in report.categories],
    )


def _outstanding_rows(report):
    rows = [("in_house", "", "", report.in_house_due)]
    rows += [("invoice", number, guest, due) for _, number, guest, due in report.unpaid]
    return ["kind", "invoice", "guest", "due_dt"], rows


_TABLES = {
    "occupancy": _occupancy_rows,
    "revenue": _revenue_rows,
    "categories": _category_rows,
    "outstanding": _outstanding_rows,
}


@bp.get("/<table>.csv")
@roles_required(Role.MANAGER)
def export(table: str):
    if table not in _TABLES:
        abort(404)
    actor = current_actor()
    first = forms.calendar_date(request.args, "first")
    last = forms.calendar_date(request.args, "last")
    report = services().reports.report(actor, first, last)
    header, rows = _TABLES[table](report)
    services().reports.record_export(actor, table, first, last)
    filename = f"hotel-{table}-{first.isoformat()}-{last.isoformat()}.csv"
    return Response(
        to_csv(header, rows),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
