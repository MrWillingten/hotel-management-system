"""Country names for the nationality field (story 6.15).

The field is a text box with suggestions (an HTML <datalist>: the browser
shows matching countries while you type, no JavaScript needed). People type
a name in any of the three languages ("Tunisia", "Tunisie", "تونس") or a
code ("TN"); `country_code` turns it into the ISO code the domain checks.
Names come from Babel's CLDR data, the same source as the translations.
"""

from __future__ import annotations

from functools import cache

from babel import Locale

from hotel.config import LANGUAGES
from hotel.domain.guests import COUNTRY_CODES, search_key


@cache
def country_options(locale: str) -> tuple[tuple[str, str], ...]:
    """(code, name) for every country, sorted by name in that language."""
    names = Locale.parse(locale).territories
    pairs = [(code, names.get(code, code)) for code in COUNTRY_CODES]
    return tuple(sorted(pairs, key=lambda pair: search_key(pair[1])))


@cache
def _index() -> dict[str, str]:
    """Every known spelling (each language, without accents or case) -> code."""
    index: dict[str, str] = {}
    for language in LANGUAGES:
        for code, name in country_options(language):
            index.setdefault(search_key(name), code)
    for code in COUNTRY_CODES:
        index.setdefault(search_key(code), code)
    return index


def country_code(typed: str) -> str:
    """The ISO code for what was typed, or the text itself (the domain then refuses it)."""
    text = typed.strip()
    if not text:
        return ""
    return _index().get(search_key(text), text[:60])


def country_name(code: str | None, locale: str) -> str:
    if not code:
        return ""
    return dict(country_options(locale)).get(code, code)
