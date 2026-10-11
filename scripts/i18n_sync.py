"""Update the French and Arabic catalogues after changing interface text.

    python scripts/i18n_sync.py                    # extract, merge, report missing strings
    python scripts/i18n_sync.py new_strings.json   # ...and fill them from a JSON file

The JSON file maps each English msgid to [french, arabic]:

    {"Save changes": ["Enregistrer", "حفظ التغييرات"]}

Existing translations are kept; the .mo files are compiled at the end. Exits
with status 1 and lists the strings that still need a translation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "src" / "hotel" / "translations"
LANGUAGES = ("fr", "ar")


def _babel(*args: str) -> None:
    subprocess.run(  # noqa: S603 - fixed arguments
        [sys.executable, "-m", "babel.messages.frontend", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )


def main(argv: list[str]) -> int:
    new = json.loads(Path(argv[0]).read_text("utf-8")) if argv else {}
    pot = TRANSLATIONS / "messages.pot"
    _babel(
        "extract",
        "-F",
        "babel.cfg",
        "-k",
        "_l",
        "-k",
        "lazy_gettext",
        "--no-location",
        "--sort-output",
        "--project=hotel",
        "-o",
        str(pot),
        ".",
    )
    _babel(
        "update",
        "-i",
        str(pot),
        "-d",
        str(TRANSLATIONS),
        "--ignore-obsolete",
        "--no-fuzzy-matching",
    )
    missing: set[str] = set()
    for index, language in enumerate(LANGUAGES):
        po = TRANSLATIONS / language / "LC_MESSAGES" / "messages.po"
        with open(po, "rb") as handle:
            catalog = read_po(handle, locale=language)
        for message in catalog:
            if not message.id:
                continue
            if message.id in new:
                message.string = new[message.id][index]
                message.flags.discard("fuzzy")
            elif not message.string or message.fuzzy:
                missing.add(message.id)
        with open(po, "wb") as handle:
            write_po(handle, catalog, width=100, no_location=True, sort_output=True)
        with open(po.with_suffix(".mo"), "wb") as handle:
            write_mo(handle, catalog)
    if missing:
        print("Missing translations:")
        print(json.dumps(sorted(missing), ensure_ascii=False, indent=1))
        return 1
    print("Catalogues complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
