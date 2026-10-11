"""Locale-aware display helpers shared by templates and views."""

from __future__ import annotations

from flask_babel import format_decimal, get_locale

from hotel.domain.money import Money


def money(amount: Money | None) -> str:
    """180500 millimes -> "180.500 DT" (en), "180,500 DT" (fr), "180.500 د.ت" (ar)."""
    if amount is None:
        return "—"
    number = format_decimal(amount.to_decimal(), format="#,##0.000")
    symbol = "د.ت" if str(get_locale()).startswith("ar") else "DT"
    return f"{number} {symbol}"
