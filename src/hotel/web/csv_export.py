"""CSV downloads of the report tables (story 5.3).

Spreadsheet programs treat a cell that starts with = + - @ (or a tab / line
break) as a formula, so a guest called "=HYPERLINK(...)" could run something
when a manager opens the file (CSV injection, threat I5). Every *text* cell
that starts that way is prefixed with an apostrophe, which makes Excel and
LibreOffice show it as plain text. Numbers we produce ourselves are written
unchanged, so -12.500 stays a number.

The files never contain identity documents, phone numbers or e-mail addresses.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from hotel.domain.money import Money

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r", "\n")


def safe_cell(value: object) -> str:
    if isinstance(value, Money):
        return str(value)  # "180.500": a plain number with three decimals
    if isinstance(value, int | float):
        return str(value)
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_DANGEROUS) else text


def to_csv(header: list[str], rows: Iterable[Iterable[object]]) -> str:
    """UTF-8 text with a byte-order mark, so Excel reads accents and Arabic correctly."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([safe_cell(h) for h in header])
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return "﻿" + buffer.getvalue()
