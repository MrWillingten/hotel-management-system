"""Locale-aware display helpers shared by templates and views."""

from __future__ import annotations

from decimal import Decimal

from flask_babel import format_decimal, get_locale
from markupsafe import Markup, escape

from hotel.domain.money import Money


def money(amount: Money | None) -> str:
    """180500 millimes -> "180.500 DT" (en), "180,500 DT" (fr), "180.500 د.ت" (ar)."""
    if amount is None:
        return "—"
    number = format_decimal(amount.to_decimal(), format="#,##0.000")
    symbol = "د.ت" if str(get_locale()).startswith("ar") else "DT"
    return f"{number} {symbol}"


def money_html(amount: Money | None) -> Markup:
    """money() for templates, isolated with <bdi>.

    In an Arabic sentence, "180.500 DT" written right-to-left could have its
    parts reordered by the browser's bidirectional algorithm; <bdi> keeps the
    amount in one piece and in reading order. Python messages (flashes) use
    plain money(), so no tag ever appears as text.
    """
    return Markup("<bdi>%s</bdi>") % escape(money(amount))


def percent(basis_points: int) -> str:
    """2000 basis points -> "20 %" (en), "20 %" (fr); 750 -> "7.5 %" / "7,5 %"."""
    # A non-breaking space, like money(): "20" and "%" never end up on two lines.
    return f"{format_decimal(Decimal(basis_points) / 100, format='#,##0.##')}\u00a0%"
