"""Review the French and Arabic texts in a spreadsheet (story 5.5).

    python scripts/i18n_review.py export translations-review.csv
    python scripts/i18n_review.py import translations-review.csv

`export` writes every interface text with its current French and Arabic
translation and two empty columns, "french_correction" and
"arabic_correction". Open the file in LibreOffice Calc or Excel (UTF-8,
comma-separated), fill in only the cells you want to change, save as CSV.

`import` applies the corrections to the catalogues and compiles them. A
correction whose placeholders differ from the English text (for example
"%(name)s" missing or misspelt) is refused, because the page would fail to
display it; the script lists those rows and changes nothing.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "src" / "hotel" / "translations"
COLUMNS = ["english", "french", "arabic", "french_correction", "arabic_correction"]
_PLACEHOLDER = re.compile(r"%\([a-z_]+\)s|%%")


def placeholders(text: str) -> list[str]:
    """The %(name)s markers and literal %% of a text, in a comparable form."""
    return sorted(_PLACEHOLDER.findall(text))


def _catalog(language: str):
    with open(TRANSLATIONS / language / "LC_MESSAGES" / "messages.po", "rb") as handle:
        return read_po(handle, locale=language)


def _save(language: str, catalog) -> None:
    po = TRANSLATIONS / language / "LC_MESSAGES" / "messages.po"
    with open(po, "wb") as handle:
        write_po(handle, catalog, width=100, no_location=True, sort_output=True)
    with open(po.with_suffix(".mo"), "wb") as handle:
        write_mo(handle, catalog)


def export(path: Path) -> int:
    french, arabic = _catalog("fr"), _catalog("ar")
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for message in french:
            if message.id:
                writer.writerow([message.id, message.string, arabic.get(message.id).string, "", ""])
    print(f"Wrote {path}. Fill in the correction columns, save as CSV, then run `import`.")
    return 0


def import_corrections(path: Path) -> int:
    catalogs = {"fr": _catalog("fr"), "ar": _catalog("ar")}
    changes: list[tuple[str, str, str]] = []
    problems: list[str] = []
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            english = row.get("english", "")
            for language, column in (("fr", "french_correction"), ("ar", "arabic_correction")):
                correction = (row.get(column) or "").strip()
                if not correction:
                    continue
                if catalogs[language].get(english) is None:
                    problems.append(f"line {line}: unknown English text {english!r}")
                elif placeholders(correction) != placeholders(english):
                    problems.append(
                        f"line {line} ({language}): placeholders {placeholders(correction)} "
                        f"do not match {placeholders(english)}"
                    )
                else:
                    changes.append((language, english, correction))
    if problems:
        print("Nothing was changed. Fix these rows first:")
        print("\n".join(problems))
        return 1
    for language, english, correction in changes:
        catalogs[language].get(english).string = correction
    for language, catalog in catalogs.items():
        _save(language, catalog)
    print(f"Applied {len(changes)} corrections. Restart the application to see them.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in {"export", "import"}:
        print(__doc__)
        return 2
    path = Path(argv[1])
    return export(path) if argv[0] == "export" else import_corrections(path)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
